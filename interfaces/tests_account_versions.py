"""Latest-version edits and no-data-loss freeze/recovery regression (SQLite)."""
import json

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .account_applications import change_application, application_payload, MergeConfirmationRequired
from .models import (AccountFieldBinding, AccountFieldValue, InterfaceDraft, InterfaceDraftField,
                     ThreadInterfaceImplementation)
from .services import (publish_field_definition, publish_draft, prepare_thread_fields, save_thread_fields)
from .versioning import active_account_interfaces, interface_availability, refresh_account_interfaces
from events.models import Thread


class AccountVersionTests(TestCase):
    def setUp(self):
        self.account = get_user_model().objects.create_user('version_owner')
        self.other = get_user_model().objects.create_user('version_other')
        self.field, self.v1 = self.field_version('Text')

    def field_version(self, name, definition=None, field_type='short_text', **kwargs):
        return publish_field_definition(creator=self.account, name=name, definition=definition,
                                        field_type=field_type, **kwargs)

    def interface_version(self, fields, interface=None, name='Account IF', kind='account'):
        draft = InterfaceDraft.objects.create(creator=self.account, name=name, kind=kind, interface=interface)
        for position, (definition, required) in enumerate(fields):
            InterfaceDraftField.objects.create(draft=draft, definition=definition, required=required, position=position)
        return publish_draft(draft.pk)

    def add(self, interface=None, field=None, value='kept'):
        field = field or self.field
        change_application(self.account, {'operation': 'add_interface' if interface else 'add_field',
            'id': interface.pk if interface else field.pk, 'values': {str(field.key): [value]}})

    def preview(self, payload):
        with self.assertRaises(MergeConfirmationRequired) as pending:
            change_application(self.account, payload)
        return pending.exception

    def edit(self, field=None, value='changed'):
        binding = self.account.field_bindings.get(definition=field or self.field)
        return {'operation': 'edit_value', 'id': binding.pk, 'values': [value]}

    def test_value_edit_requires_latest_preview_and_preserves_old_display_until_confirmed(self):
        self.add()
        _, latest = self.field_version('New label', self.field)
        payload = self.edit()
        preview = self.preview(payload)
        binding = self.account.field_bindings.get()
        self.assertEqual((binding.version_id, binding.value.value), (self.v1.pk, 'kept'))
        self.assertEqual(application_payload(self.account)['fields'][0]['name'], 'Text')
        self.assertTrue(any(c['kind'] == 'value' and c['before'] == 'kept' and c['after'] == 'changed' for c in preview.changes))
        change_application(self.account, payload, preview.token)
        binding.refresh_from_db(); binding.value.refresh_from_db()
        self.assertEqual((binding.version_id, binding.value.value), (latest.pk, 'changed'))
        self.assertEqual(self.account.direct_fields.get().version_id, latest.pk)

    def test_frozen_if_cannot_edit_or_count_but_field_can_update_shared_value(self):
        interface, old = self.interface_version([(self.field, True)])
        self.add(interface)
        _, latest = self.field_version('New', self.field)
        item = self.account.interface_implementations.get()
        self.assertEqual(item.state, 'frozen')
        self.assertFalse(interface_availability(item.interface).usable)
        self.assertEqual(active_account_interfaces(self.account), [])
        for payload in [{'operation': 'update_interface', 'id': item.pk, 'values': {}},
                        {**self.edit(), 'interface_id': item.pk}]:
            with self.assertRaises(ValidationError): change_application(self.account, payload)
        payload = self.edit(value='current value')
        change_application(self.account, payload, self.preview(payload).token)
        result = application_payload(self.account)
        self.assertEqual(result['interfaces'][0]['state'], 'frozen')
        self.assertEqual(result['interfaces'][0]['version'], old.version_number)
        self.assertEqual(result['interfaces'][0]['values'][0]['value'], 'current value')
        self.assertEqual(result['fields'][0]['field']['version'], latest.version_number)
        self.assertEqual(self.account.direct_fields.count(), 0)

    def test_republish_auto_recovers_only_already_current_fields_with_unchanged_values(self):
        interface, _ = self.interface_version([(self.field, True)])
        self.add(interface)
        self.field_version('Latest', self.field)
        payload = self.edit(value='kept')
        change_application(self.account, payload, self.preview(payload).token)
        binding = self.account.field_bindings.get(); timestamp = binding.value.updated_at
        _, latest_if = self.interface_version([(self.field, True)], interface)
        item = self.account.interface_implementations.get()
        binding.value.refresh_from_db()
        self.assertEqual((item.state, item.version_id), ('active', latest_if.pk))
        self.assertEqual((binding.value.value, binding.value.updated_at), ('kept', timestamp))
        self.assertEqual(len(active_account_interfaces(self.account)), 1)
        self.assertEqual(self.account.field_bindings.count(), 1)

    def test_republish_waits_for_field_version_confirmation_then_recovers(self):
        interface, _ = self.interface_version([(self.field, True)])
        self.add(interface)
        self.field_version('Latest', self.field)
        _, latest_if = self.interface_version([(self.field, True)], interface)
        self.assertEqual(self.account.interface_implementations.get().state, 'pending')
        self.assertEqual(active_account_interfaces(self.account), [])
        payload = self.edit(value='kept')
        change_application(self.account, payload, self.preview(payload).token)
        item = self.account.interface_implementations.get()
        self.assertEqual((item.state, item.version_id), ('active', latest_if.pk))

    def test_missing_field_with_default_stays_pending_without_automatic_addition(self):
        interface, _ = self.interface_version([(self.field, True)])
        self.add(interface)
        self.field_version('Latest', self.field)
        payload = self.edit(value='kept'); change_application(self.account, payload, self.preview(payload).token)
        extra, _ = self.field_version('Extra', field_type='single_choice', settings={'options': ['default'], 'default': 'default'})
        _, latest_if = self.interface_version([(self.field, True), (extra, True)], interface)
        item = self.account.interface_implementations.get()
        self.assertEqual(item.state, 'pending')
        self.assertFalse(self.account.field_bindings.filter(definition=extra).exists())
        refresh_account_interfaces(self.account)
        self.assertEqual(self.account.field_bindings.count(), 1)
        payload = {'operation': 'update_interface', 'id': item.pk,
                   'values': {str(self.field.key): ['kept'], str(extra.key): ['default']}}
        preview = self.preview(payload)
        self.assertTrue(any(c['kind'] == 'value' and c['field'] == 'Extra' and c['before'] is None
                            and c['after'] == 'default' for c in preview.changes))
        self.assertEqual(self.account.field_bindings.count(), 1)
        change_application(self.account, payload, preview.token)
        item.refresh_from_db()
        self.assertEqual((item.state, item.version_id), ('active', latest_if.pk))

    def test_missing_optional_field_also_requires_confirmation(self):
        interface, _ = self.interface_version([(self.field, True)])
        self.add(interface); self.field_version('Latest', self.field)
        payload = self.edit(value='kept'); change_application(self.account, payload, self.preview(payload).token)
        extra, _ = self.field_version('Optional')
        self.interface_version([(self.field, True), (extra, False)], interface)
        self.assertEqual(self.account.interface_implementations.get().state, 'pending')
        self.assertFalse(self.account.field_bindings.filter(definition=extra).exists())

    def test_choice_contradiction_does_not_rewrite_and_frozen_constraint_does_not_block(self):
        choice, v1 = self.field_version('Choice', field_type='single_choice', settings={'options': ['old']})
        interface, _ = self.interface_version([(choice, True)])
        self.add(interface, choice, 'old')
        _, v2 = self.field_version('Choice', choice, 'single_choice', settings={'options': ['new']})
        self.interface_version([(choice, True)], interface)
        self.assertEqual(self.account.interface_implementations.get().state, 'pending')
        binding = self.account.field_bindings.get()
        self.assertEqual((binding.version_id, binding.value.value), (v1.pk, 'old'))
        with self.assertRaises(ValidationError): change_application(self.account, self.edit(choice, 'old'))
        payload = self.edit(choice, 'new')
        change_application(self.account, payload, self.preview(payload).token)
        binding.refresh_from_db(); binding.value.refresh_from_db()
        self.assertEqual((binding.version_id, binding.value.value), (v2.pk, 'new'))
        self.assertEqual(self.account.interface_implementations.get().state, 'active')

    def test_multiple_refs_ignore_frozen_required_but_keep_active_required_constraint(self):
        frozen, _ = self.interface_version([(self.field, True)], name='Frozen')
        self.add(frozen)
        self.field_version('Latest', self.field)
        active, _ = self.interface_version([(self.field, True)], name='Active')
        payload = {'operation': 'add_interface', 'id': active.pk, 'values': {}}
        change_application(self.account, payload, self.preview(payload).token)
        binding = self.account.field_bindings.get()
        with self.assertRaises(ValidationError):
            change_application(self.account, {'operation': 'edit_value', 'id': binding.pk, 'values': []})
        active_item = self.account.interface_implementations.get(interface=active)
        change_application(self.account, {'operation': 'remove_interface', 'id': active_item.pk})
        change_application(self.account, {'operation': 'edit_value', 'id': binding.pk, 'values': []})
        self.assertIsNone(application_payload(self.account)['fields'][0]['value'])
        self.assertEqual(self.account.interface_implementations.get().state, 'frozen')

    def test_removal_never_returns_after_definition_publication(self):
        interface, _ = self.interface_version([(self.field, True)])
        self.add(interface); self.field_version('Latest', self.field)
        item = self.account.interface_implementations.get()
        change_application(self.account, {'operation': 'remove_interface', 'id': item.pk})
        self.interface_version([(self.field, True)], interface)
        self.assertFalse(self.account.interface_implementations.exists())

    def test_dropped_fields_are_retained_and_editable_without_orphan_deletion(self):
        extra, _ = self.field_version('Retained')
        interface, old = self.interface_version([(self.field, True), (extra, False)])
        self.add(interface)
        binding = self.account.field_bindings.get(definition=extra)
        self.interface_version([(self.field, True)], interface)
        item = self.account.interface_implementations.get()
        payload = {'operation': 'update_interface', 'id': item.pk, 'values': {str(self.field.key): ['kept']}}
        change_application(self.account, payload, self.preview(payload).token)
        self.assertTrue(AccountFieldBinding.objects.filter(pk=binding.pk).exists())
        change_application(self.account, self.edit(extra, 'still here'))
        self.assertEqual(len(application_payload(self.account)['fields']), 2)

    def test_stale_preview_rechecks_value_latest_version_and_refs(self):
        self.add(); self.field_version('v2', self.field)
        payload = self.edit(); preview = self.preview(payload)
        self.field_version('v3', self.field)
        with self.assertRaises(MergeConfirmationRequired) as renewed:
            change_application(self.account, payload, preview.token)
        self.assertTrue(any(c.get('after') == 3 for c in renewed.exception.changes))
        self.assertEqual(self.account.field_values.get().value, 'kept')
        second, _ = self.field_version('Second'); self.add(field=second, value='second')
        with self.assertRaises(MergeConfirmationRequired):
            change_application(self.account, payload, renewed.exception.token)

    def test_synonym_version_merge_keeps_earliest_value_with_confirmation(self):
        second, _ = self.field_version('Second')
        self.add(field=second, value='earliest'); self.add(value='later')
        self.field_version('Joined', self.field, synonym_target_ids=[second.pk])
        payload = self.edit(value='request')
        preview = self.preview(payload)
        self.assertEqual(self.account.field_values.count(), 2)
        change_application(self.account, payload, preview.token)
        self.assertEqual(self.account.field_values.count(), 1)
        self.assertEqual({f['value'] for f in application_payload(self.account)['fields']}, {'earliest'})

    def test_other_account_update_remove_and_preview_tokens_are_rejected(self):
        interface, _ = self.interface_version([(self.field, True)])
        self.add(interface); self.field_version('v2', self.field)
        payload = self.edit(); preview = self.preview(payload)
        with self.assertRaises(ValidationError): change_application(self.other, payload, preview.token)
        item = self.account.interface_implementations.get()
        for operation in ['update_interface', 'remove_interface']:
            with self.assertRaises(ValidationError):
                change_application(self.other, {'operation': operation, 'id': item.pk, 'values': {}})
        url = reverse('accounts:applied-change', args=[self.account.username])
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(url, json.dumps(payload), content_type='application/json').status_code, 403)
        self.assertEqual(self.account.field_values.get().value, 'kept')

    def test_thread_historical_display_unchanged_and_new_creation_is_latest_only(self):
        interface, old = self.interface_version([(self.field, True)], kind='thread')
        prepared = prepare_thread_fields([], {}, [interface.pk], {(interface.pk, str(self.field.key)): ['old value']})
        thread = Thread.objects.create(title='Historical')
        save_thread_fields(thread, *prepared)
        self.field_version('v2', self.field)
        with self.assertRaises(ValidationError): prepare_thread_fields([], {}, [interface.pk], {})
        _, latest = self.interface_version([(self.field, True)], interface, kind='thread')
        item = ThreadInterfaceImplementation.objects.get(thread=thread)
        self.assertEqual(item.version_id, old.pk)
        self.assertEqual(item.values.get().value, 'old value')
        new = prepare_thread_fields([], {}, [interface.pk], {(interface.pk, str(self.field.key)): ['new value']})
        self.assertEqual(new[1][0][0].pk, latest.pk)

    def test_same_definition_type_change_remains_rejected(self):
        with self.assertRaises(ValidationError): self.field_version('Number', self.field, 'integer')
        self.field.refresh_from_db()
        self.assertEqual(self.field.current_version_id, self.v1.pk)

    def test_nullable_rollout_binding_is_read_without_mutation_and_upgraded_on_edit(self):
        self.add()
        binding = self.account.field_bindings.get()
        AccountFieldBinding.objects.filter(pk=binding.pk).update(version=None)
        self.assertEqual(application_payload(self.account)['fields'][0]['version'], 1)
        self.assertIsNone(AccountFieldBinding.objects.get(pk=binding.pk).version_id)
        change_application(self.account, self.edit())
        self.assertEqual(AccountFieldBinding.objects.get(pk=binding.pk).version_id, self.v1.pk)

    def test_api_preview_is_explicit_and_does_not_save(self):
        self.add(); self.field_version('Latest', self.field)
        self.client.force_login(self.account)
        response = self.client.post(reverse('accounts:applied-change', args=[self.account.username]),
            json.dumps(self.edit()), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['needs_confirmation'])
        self.assertContains(self.client.get(reverse('mypage')), 'accounts/applied.js?v=20261006-account-if-fix', count=1)
        self.assertEqual(self.account.field_values.get().value, 'kept')

    def test_preview_invalidated_when_incoming_if_version_alone_changes(self):
        self.add(value='existing')
        second, _ = self.field_version('Second'); self.add(field=second, value='later')
        bridge, _ = self.field_version('Bridge', synonym_target_ids=[self.field.pk, second.pk])
        interface, _ = self.interface_version([(bridge, True)])
        payload = {'operation': 'add_interface', 'id': interface.pk, 'values': {}}
        preview = self.preview(payload)
        self.interface_version([(bridge, True)], interface, name='Revised IF')
        with self.assertRaises(MergeConfirmationRequired) as current:
            change_application(self.account, payload, preview.token)
        self.assertTrue(any(c['kind'] == 'application' and c['after'] == 2 for c in current.exception.changes))
        self.assertEqual(self.account.interface_implementations.count(), 0)
        self.assertEqual(self.account.field_values.count(), 2)

    def test_stale_confirmation_cannot_overwrite_a_newly_confirmed_edit(self):
        self.add(); self.field_version('Latest', self.field)
        old_payload = self.edit(value='old request'); old = self.preview(old_payload)
        new_payload = self.edit(value='new edit')
        change_application(self.account, new_payload, self.preview(new_payload).token)
        with self.assertRaises(MergeConfirmationRequired) as renewed:
            change_application(self.account, old_payload, old.token)
        self.assertTrue(any(c['kind'] == 'value' and c['before'] == 'new edit' and c['after'] == 'old request'
                            for c in renewed.exception.changes))
        self.assertEqual(self.account.field_values.get().value, 'new edit')

    def test_legacy_canonical_version_mismatch_is_pending_and_not_effective(self):
        self.add()
        self.field_version('Latest', self.field)
        interface, _ = self.interface_version([(self.field, True)])
        payload = {'operation': 'add_interface', 'id': interface.pk, 'values': {}}
        change_application(self.account, payload, self.preview(payload).token)
        AccountFieldBinding.objects.filter(account=self.account).update(version=self.v1)
        self.assertEqual(application_payload(self.account)['interfaces'][0]['state'], 'pending')
        self.assertEqual(active_account_interfaces(self.account), [])
