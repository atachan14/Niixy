import json
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .account_applications import change_application, application_payload, MergeConfirmationRequired
from .models import (AccountDirectField, AccountFieldBinding, AccountFieldValue,
    AccountInterfaceImplementation, InterfaceDraft, InterfaceDraftField, ThreadFieldValue)
from .services import publish_field_definition, publish_draft
from events.models import Thread


class AccountApplicationTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user('applied_owner')
        self.other = get_user_model().objects.create_user('applied_other')
        self.field, self.version = self.new_field('First')

    def new_field(self, name, field_type='short_text', **kwargs):
        return publish_field_definition(creator=self.owner, name=name, field_type=field_type, **kwargs)

    def interface(self, name, fields, kind='account'):
        draft = InterfaceDraft.objects.create(creator=self.owner, kind=kind, name=name)
        for position, (field, required) in enumerate(fields):
            InterfaceDraftField.objects.create(draft=draft, definition=field, position=position, required=required)
        return publish_draft(draft.pk)

    def add_field(self, field=None, value='first', account=None):
        field = field or self.field
        change_application(account or self.owner, {'operation': 'add_field', 'id': field.pk,
            'values': {str(field.key): [value]}})

    def add_interface(self, interface, values=None, confirmation=None):
        return change_application(self.owner, {'operation': 'add_interface', 'id': interface.pk,
            'values': values or {}}, confirmation)

    def test_direct_required_duplicate_and_version_fixed(self):
        with self.assertRaises(ValidationError): self.add_field(value='')
        self.assertEqual(AccountDirectField.objects.count(), 0)
        self.add_field()
        with self.assertRaises(ValidationError): self.add_field()
        _, latest = self.new_field('Renamed', definition=self.field)
        applied = self.owner.direct_fields.get()
        self.assertEqual(applied.version_id, self.version.pk)
        self.assertNotEqual(applied.version_id, latest.pk)
        self.assertEqual(application_payload(self.owner)['fields'][0]['name'], 'First')

    def test_interface_required_kind_and_current_dependency_checks(self):
        account_if, version = self.interface('Account applied', [(self.field, True)])
        with self.assertRaises(ValidationError): self.add_interface(account_if)
        thread_if, _ = self.interface('Wrong kind', [(self.field, True)], kind='thread')
        with self.assertRaises(ValidationError): self.add_interface(thread_if, {str(self.field.key): ['value']})
        self.add_interface(account_if, {str(self.field.key): ['value']})
        with self.assertRaises(ValidationError): self.add_interface(account_if)
        self.new_field('Updated', definition=self.field)
        new_owner = self.other
        with self.assertRaises(ValidationError):
            change_application(new_owner, {'operation': 'add_interface', 'id': account_if.pk, 'values': {str(self.field.key): ['value']}})
        self.assertEqual(self.owner.interface_implementations.get().version_id, version.pk)
        binding = self.owner.field_bindings.get()
        payload = {'operation': 'edit_value', 'id': binding.pk, 'values': ['latest edit']}
        with self.assertRaises(MergeConfirmationRequired) as preview:
            change_application(self.owner, payload)
        change_application(self.owner, payload, preview.exception.token)
        self.assertEqual(application_payload(self.owner)['interfaces'][0]['values'][0]['value'], 'latest edit')
        self.assertEqual(application_payload(self.owner)['interfaces'][0]['state'], 'frozen')

    def test_direct_and_multiple_interfaces_share_one_value_and_preserve_bindings(self):
        self.add_field()
        first, _ = self.interface('One', [(self.field, True)])
        second, _ = self.interface('Two', [(self.field, False)])
        self.add_interface(first)
        self.add_interface(second)
        self.assertEqual(AccountFieldBinding.objects.count(), 1)
        self.assertEqual(AccountFieldValue.objects.count(), 1)
        binding = self.owner.field_bindings.get()
        change_application(self.owner, {'operation': 'edit_value', 'id': binding.pk, 'values': ['edited']})
        self.assertEqual([item['values'][0]['value'] for item in application_payload(self.owner)['interfaces']], ['edited', 'edited'])
        change_application(self.owner, {'operation': 'remove_field', 'id': self.owner.direct_fields.get().pk})
        self.assertTrue(AccountFieldBinding.objects.filter(pk=binding.pk).exists())
        first_entry = self.owner.interface_implementations.get(interface=first)
        change_application(self.owner, {'operation': 'remove_interface', 'id': first_entry.pk})
        self.assertEqual(self.owner.field_bindings.get().pk, binding.pk)
        change_application(self.owner, {'operation': 'remove_interface', 'id': self.owner.interface_implementations.get().pk})
        self.assertEqual(AccountFieldBinding.objects.count(), 0)
        self.assertEqual(AccountFieldValue.objects.count(), 0)

    def test_cross_account_and_thread_values_remain_isolated(self):
        self.add_field(value='owner')
        self.add_field(value='other', account=self.other)
        thread = Thread.objects.create(title='separate')
        value = ThreadFieldValue.objects.create(thread=thread, value='thread')
        other_binding = self.other.field_bindings.get()
        with self.assertRaises(ValidationError):
            change_application(self.owner, {'operation': 'edit_value', 'id': other_binding.pk, 'values': ['attack']})
        change_application(self.owner, {'operation': 'edit_value', 'id': self.owner.field_bindings.get().pk, 'values': ['changed']})
        other_binding.value.refresh_from_db(); value.refresh_from_db()
        self.assertEqual(other_binding.value.value, 'other')
        self.assertEqual(value.value, 'thread')

    def test_synonym_merge_requires_confirm_and_keeps_first_applied_not_lowest_definition(self):
        second, _ = self.new_field('Second')
        self.add_field(second, 'earliest')
        self.add_field(self.field, 'later')
        bridge, _ = self.new_field('Bridge', synonym_target_ids=[self.field.pk, second.pk])
        payload = {'operation': 'add_field', 'id': bridge.pk, 'values': {str(bridge.key): ['incoming']}}
        before = (AccountFieldBinding.objects.count(), AccountFieldValue.objects.count(), AccountDirectField.objects.count())
        with self.assertRaises(MergeConfirmationRequired) as pending: change_application(self.owner, payload)
        self.assertTrue(any(item['before'] == 'later' and item['after'] == 'earliest' for item in pending.exception.changes))
        self.assertEqual((AccountFieldBinding.objects.count(), AccountFieldValue.objects.count(), AccountDirectField.objects.count()), before)
        with self.assertRaises(MergeConfirmationRequired): change_application(self.owner, payload, 'forged')
        change_application(self.owner, payload, pending.exception.token)
        self.assertEqual(AccountFieldValue.objects.count(), 1)
        self.assertEqual({item['value'] for item in application_payload(self.owner)['fields']}, {'earliest'})
        self.assertEqual(len(application_payload(self.owner)['fields']), 3)  # Synonyms are separate display definitions.

    def test_confirm_token_is_stale_after_another_value_edit(self):
        other, _ = self.new_field('Other')
        self.add_field(value='before'); self.add_field(other, 'different')
        bridge, _ = self.new_field('Join', synonym_target_ids=[self.field.pk, other.pk])
        payload = {'operation': 'add_field', 'id': bridge.pk, 'values': {}}
        with self.assertRaises(MergeConfirmationRequired) as pending: change_application(self.owner, payload)
        change_application(self.owner, {'operation': 'edit_value', 'id': self.owner.field_bindings.get(definition=self.field).pk, 'values': ['after']})
        with self.assertRaises(MergeConfirmationRequired): change_application(self.owner, payload, pending.exception.token)
        self.assertEqual(AccountDirectField.objects.count(), 2)

    def test_fixed_choice_constraint_conflict_rejects_atomically(self):
        field, _ = self.new_field('Choice', 'single_choice', settings={'options': ['old']})
        old_if, _ = self.interface('Old IF', [(field, True)])
        self.add_interface(old_if, {str(field.key): ['old']})
        self.new_field('Choice', 'single_choice', definition=field, settings={'options': ['new']})
        payload = {'operation': 'add_field', 'id': field.pk, 'values': {str(field.key): ['new']}}
        with self.assertRaises(MergeConfirmationRequired) as preview:
            change_application(self.owner, payload)
        self.assertEqual(AccountDirectField.objects.count(), 0)
        self.assertEqual(AccountFieldValue.objects.get().value, 'old')
        change_application(self.owner, payload, preview.exception.token)
        self.assertEqual(AccountFieldValue.objects.get().value, 'new')
        self.assertEqual(application_payload(self.owner)['interfaces'][0]['state'], 'frozen')

    def test_bulk_edit_validates_all_before_write_and_shared_conflicting_input(self):
        number, _ = self.new_field('Number', 'integer')
        self.add_field(); self.add_field(number, '7')
        first = self.owner.field_bindings.get(definition=self.field)
        second = self.owner.field_bindings.get(definition=number)
        with self.assertRaises(ValidationError):
            change_application(self.owner, {'operation': 'edit_values', 'updates': [
                {'id': first.pk, 'values': ['changed']}, {'id': second.pk, 'values': ['bad']}]})
        first.value.refresh_from_db(); self.assertEqual(first.value.value, 'first')
        with self.assertRaises(ValidationError):
            change_application(self.owner, {'operation': 'edit_values', 'updates': [
                {'id': first.pk, 'values': ['a']}, {'id': first.pk, 'values': ['b']}]})

    def test_optional_field_empty_value_and_required_shared_reference(self):
        interface, _ = self.interface('Optional', [(self.field, False)])
        self.add_interface(interface)
        self.assertIsNone(AccountFieldValue.objects.get().value)
        binding = self.owner.field_bindings.get()
        change_application(self.owner, {'operation': 'edit_value', 'id': binding.pk, 'values': ['filled']})
        self.add_field(value='filled')
        with self.assertRaises(ValidationError): change_application(self.owner, {'operation': 'edit_value', 'id': binding.pk, 'values': []})

    def test_display_deduplicates_same_definition_and_retains_first_binding_order(self):
        second, _ = self.new_field('Second')
        third, _ = self.new_field('Third')
        self.add_field(self.field); self.add_field(second, 'second')
        first_if, _ = self.interface('First IF', [(self.field, True), (third, False)])
        second_if, _ = self.interface('Second IF', [(self.field, False)])
        self.add_interface(first_if); self.add_interface(second_if)
        fields = application_payload(self.owner)['fields']
        self.assertEqual(len(fields), 3)
        original_binding = self.owner.field_bindings.get(definition=self.field).pk
        change_application(self.owner, {'operation': 'remove_field', 'id': self.owner.direct_fields.get(definition=self.field).pk})
        self.add_field(value='first')
        self.assertEqual(self.owner.field_bindings.get(definition=self.field).pk, original_binding)
        self.assertEqual(len(application_payload(self.owner)['fields']), 3)

    def test_value_timestamp_sort_reference_add_no_change_save_and_account_isolation(self):
        from datetime import timedelta
        from django.utils import timezone
        second, _ = self.new_field('Timestamp Second')
        self.add_field(); self.add_field(second, 'second')
        first_binding = self.owner.field_bindings.get(definition=self.field)
        second_binding = self.owner.field_bindings.get(definition=second)
        past = timezone.now() - timedelta(days=2)
        AccountFieldValue.objects.filter(pk=first_binding.value_id).update(updated_at=past)
        first_if, _ = self.interface('Timestamp IF', [(self.field, True)])
        self.add_interface(first_if)
        first_binding.value.refresh_from_db()
        self.assertEqual(first_binding.value.updated_at, past)
        change_application(self.owner, {'operation': 'edit_value', 'id': first_binding.pk, 'values': ['first']})
        first_binding.value.refresh_from_db(); self.assertEqual(first_binding.value.updated_at, past)
        self.assertEqual([item['definition_id'] for item in application_payload(self.owner)['fields']], [second.pk, self.field.pk])
        self.add_field(account=self.other, value='isolated')
        other_value = self.other.field_values.get(); other_time = other_value.updated_at
        change_application(self.owner, {'operation': 'edit_value', 'id': first_binding.pk, 'values': ['updated']})
        first_binding.value.refresh_from_db(); other_value.refresh_from_db()
        self.assertGreater(first_binding.value.updated_at, second_binding.value.updated_at)
        self.assertEqual(other_value.updated_at, other_time)
        items = application_payload(self.owner)['fields']
        self.assertEqual([item['definition_id'] for item in items], [self.field.pk, second.pk])
        self.assertEqual(items[0]['updated_at'], first_binding.value.updated_at)

    def test_synonyms_share_update_timestamp_but_remain_distinct_display(self):
        from datetime import timedelta
        from django.utils import timezone
        synonym, _ = self.new_field('Alias', synonym_target_ids=[self.field.pk])
        self.add_field(); self.add_field(synonym, 'first')
        binding = self.owner.field_bindings.get(definition=self.field)
        past = timezone.now() - timedelta(days=1)
        AccountFieldValue.objects.filter(pk=binding.value_id).update(updated_at=past)
        change_application(self.owner, {'operation': 'edit_value', 'id': binding.pk, 'values': ['same updated']})
        fields = application_payload(self.owner)['fields']
        self.assertEqual(len(fields), 2)
        self.assertEqual(fields[0]['updated_at'], fields[1]['updated_at'])
        self.assertGreater(fields[0]['updated_at'], past)

    def test_display_if_only_direct_if_dedup_and_if_removal_keeps_original_order(self):
        second, _ = self.new_field('IF Only')
        self.add_field()
        interface, _ = self.interface('Shared display', [(self.field, True), (second, False)])
        another, _ = self.interface('Another display', [(second, False)])
        self.add_interface(interface); self.add_interface(another)
        fields = application_payload(self.owner)['fields']
        self.assertEqual(len(fields), 2)
        self.assertIsNone(next(item for item in fields if item['definition_id'] == second.pk)['direct_id'])
        binding_id = self.owner.field_bindings.get(definition=second).pk
        change_application(self.owner, {'operation': 'remove_interface', 'id': self.owner.interface_implementations.get(interface=interface).pk})
        self.assertEqual(self.owner.field_bindings.get(definition=second).pk, binding_id)
        self.assertEqual(len(application_payload(self.owner)['fields']), 2)
        change_application(self.owner, {'operation': 'remove_interface', 'id': self.owner.interface_implementations.get(interface=another).pk})
        self.assertEqual([item['definition_id'] for item in application_payload(self.owner)['fields']], [self.field.pk])

    def test_interface_sort_uses_max_shared_value_timestamp_and_empty_fallback(self):
        from datetime import timedelta
        from django.utils import timezone
        second, _ = self.new_field('IF timestamp value')
        first_if, _ = self.interface('IF one', [(self.field, True), (second, False)])
        shared_if, _ = self.interface('IF shared', [(self.field, False)])
        empty_if, _ = self.interface('IF empty', [])
        self.add_interface(first_if, {str(self.field.key): ['first'], str(second.key): ['second']})
        self.add_interface(shared_if); self.add_interface(empty_if)
        first = self.owner.field_bindings.get(definition=self.field)
        other = self.owner.field_bindings.get(definition=second)
        past = timezone.now() - timedelta(days=2)
        AccountFieldValue.objects.filter(pk=first.value_id).update(updated_at=past)
        AccountFieldValue.objects.filter(pk=other.value_id).update(updated_at=past + timedelta(days=1))
        items = application_payload(self.owner)['interfaces']
        self.assertEqual([item['definition_id'] for item in items], [empty_if.pk, first_if.pk, shared_if.pk])
        self.assertEqual(next(item for item in items if item['definition_id'] == first_if.pk)['updated_at'], past + timedelta(days=1))
        self.assertEqual([value['field']['definition_id'] for value in next(item for item in items if item['definition_id'] == first_if.pk)['values']], [self.field.pk, second.pk])
        change_application(self.owner, {'operation': 'edit_value', 'id': first.pk, 'values': ['latest']})
        items = application_payload(self.owner)['interfaces']
        self.assertEqual({item['definition_id'] for item in items[:2]}, {first_if.pk, shared_if.pk})
        self.assertEqual(items[0]['updated_at'], items[1]['updated_at'])

    def test_api_auth_scoping_public_read_and_invalid_json(self):
        url = reverse('accounts:applied-change', args=[self.owner.username])
        payload = {'operation': 'add_field', 'id': self.field.pk, 'values': {str(self.field.key): ['public']}}
        self.assertEqual(self.client.post(url, json.dumps(payload), content_type='application/json').status_code, 401)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(url, json.dumps(payload), content_type='application/json').status_code, 403)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(url, '[', content_type='application/json').status_code, 400)
        self.assertEqual(self.client.post(url, json.dumps(payload), content_type='application/json').status_code, 200)
        self.client.logout()
        public = self.client.get(reverse('accounts:applied', args=[self.owner.username]))
        self.assertContains(public, 'public'); self.assertContains(public, '>Field</button>')
        self.assertContains(public, '>AccountIF</button>'); self.assertNotContains(public, 'data-edit-applied')
        self.assertNotContains(self.client.get(reverse('accounts:applied-data', args=[self.owner.username])), 'catalog')
