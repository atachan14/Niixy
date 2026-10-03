from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    FieldDefinition,
    FieldType,
    Interface,
    InterfaceDraft,
    InterfaceDraftField,
    ThreadInterfaceImplementation,
    ThreadDirectField,
)
from .services import (
    expand_field_definition_ids,
    prepare_thread_interfaces,
    prepare_thread_fields,
    publish_draft,
    publish_field_definition,
    save_thread_interfaces,
    save_thread_fields,
    thread_interface_catalog,
)
from events.models import Thread


def create_field(user, name='値', field_type=FieldType.SHORT_TEXT, settings=None):
    return publish_field_definition(
        creator=user,
        name=name,
        field_type=field_type,
        settings=settings or {},
    )[0]


class PublishDraftTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('interface_owner', password='eightchars')

    def make_draft(self, name='Event'):
        return InterfaceDraft.objects.create(creator=self.user, kind=Interface.THREAD, name=name)

    def publish_interface(self, name):
        draft = self.make_draft(name)
        return publish_draft(draft.pk)[0]

    def test_publish_creates_immutable_version_and_removes_draft(self):
        draft = self.make_draft()
        self.assertEqual(draft.publication_version_number, 1)
        definition = create_field(self.user, '開始日時', FieldType.DATETIME)
        field = InterfaceDraftField.objects.create(
            draft=draft,
            definition=definition,
            required=True,
            position=0,
        )

        interface, version = publish_draft(draft.pk)

        self.assertEqual(version.version_number, 1)
        self.assertEqual(interface.current_version, version)
        self.assertEqual(version.fields.get().field_key, field.field_key)
        self.assertFalse(InterfaceDraft.objects.filter(pk=draft.pk).exists())

    def test_publish_pins_current_field_version(self):
        definition = create_field(self.user, '共通Field')
        draft = self.make_draft('Field user')
        InterfaceDraftField.objects.create(draft=draft, definition=definition, position=0)

        _, version = publish_draft(draft.pk)

        self.assertEqual(version.fields.get().field_version, definition.current_version)

    def test_published_definition_cannot_be_changed(self):
        interface = self.publish_interface('Locked')
        version = interface.current_version
        version.name = 'Changed'

        with self.assertRaises(ValidationError):
            version.save()

    def test_publish_rejects_deleted_field(self):
        definition = create_field(self.user, 'Deleted')
        definition.status = definition.DELETED
        definition.save(update_fields=['status'])
        draft = self.make_draft('Field user')
        InterfaceDraftField.objects.create(draft=draft, definition=definition, position=0)

        with self.assertRaises(ValidationError):
            publish_draft(draft.pk)

        self.assertTrue(InterfaceDraft.objects.filter(pk=draft.pk).exists())

    def test_choice_field_requires_unique_options(self):
        with self.assertRaises(ValidationError):
            publish_field_definition(
                creator=self.user,
                name='種別',
                field_type=FieldType.SINGLE_CHOICE,
                settings={'options': ['募集', '募集']},
            )

    def test_name_is_unique_per_creator_case_insensitively(self):
        self.publish_interface('Event')
        duplicate = self.make_draft('event')

        with self.assertRaises(ValidationError):
            publish_draft(duplicate.pk)


class InterfaceManagementViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('interface_editor', password='eightchars')
        self.definition = create_field(self.user, '開催日時', FieldType.DATETIME)
        self.client.force_login(self.user)

    def field_payload(self, **overrides):
        payload = {
            'name': 'Event',
            'description': '日時を扱うInterface',
            'fields-TOTAL_FORMS': '1',
            'fields-INITIAL_FORMS': '0',
            'fields-MIN_NUM_FORMS': '0',
            'fields-MAX_NUM_FORMS': '1000',
            'fields-0-field_id': '',
            'fields-0-definition_id': str(self.definition.pk),
            'fields-0-required': 'on',
            'fields-0-DELETE': '',
            'action': 'save',
        }
        payload.update(overrides)
        return payload

    def test_my_page_shows_unified_module_management(self):
        response = self.client.get(reverse('mypage'), {'section': 'module', '_panes': '1'})

        self.assertContains(response, 'data-mypage-pane="module-list"')
        self.assertContains(response, 'data-module-type="element"')
        self.assertContains(response, 'data-module-type="interface"')
        self.assertContains(response, 'data-module-type="layout"')
        self.assertContains(response, 'data-module-subtypes="element"')
        self.assertContains(response, 'data-module-subtype="field"')
        self.assertContains(response, 'data-module-subtype="computed_field"')
        self.assertContains(response, 'data-module-subtype="action"')
        self.assertContains(response, 'data-module-collection="search"')
        self.assertContains(response, 'data-module-collection="self"')
        self.assertContains(response, 'data-module-collection="editing"')
        self.assertContains(response, reverse('interfaces:draft-create'))

    def test_module_list_combines_field_and_interface_sources(self):
        draft = InterfaceDraft.objects.create(
            creator=self.user,
            kind=Interface.ACCOUNT,
            name='Account module',
        )

        response = self.client.get(reverse('interfaces:module-management-list'))

        self.assertContains(response, 'data-mypage-pane="module-list"')
        self.assertContains(response, self.definition.name)
        self.assertContains(response, draft.name)
        self.assertContains(response, 'data-module-subtype="account"')
        html = response.content.decode()
        self_panel = html.split('data-module-panel="interface:self"', 1)[1].split(
            'data-module-panel="interface:editing"', 1
        )[0]
        editing_panel = html.split('data-module-panel="interface:editing"', 1)[1].split(
            'data-module-panel="interface:saved"', 1
        )[0]
        self.assertNotIn(draft.name, self_panel)
        self.assertIn(draft.name, editing_panel)

    def test_new_interface_uses_selected_module_subtype(self):
        response = self.client.post(
            reverse('interfaces:draft-create'),
            {'kind': Interface.ACCOUNT},
        )

        draft = InterfaceDraft.objects.get(creator=self.user)
        self.assertEqual(draft.kind, Interface.ACCOUNT)
        self.assertRedirects(
            response,
            f'/mypage/?section=module&type=interface&subtype=account&collection=editing&draft={draft.pk}',
        )

    def test_module_list_is_served_without_a_detail_pane(self):
        response = self.client.get(reverse('interfaces:module-management-list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-mypage-pane="module-list"')
        self.assertNotContains(response, 'data-mypage-pane="interface-detail"')

    def test_published_detail_is_served_without_interface_list(self):
        draft = InterfaceDraft.objects.create(creator=self.user, kind=Interface.THREAD, name='Pane')
        interface, _ = publish_draft(draft.pk)

        response = self.client.get(reverse('interfaces:published-detail', args=[interface.pk]))

        self.assertContains(response, 'data-mypage-pane="interface-detail"')
        self.assertNotContains(response, 'data-mypage-pane="interface-list"')
        self.assertContains(response, 'Pane@interface_editor v1/ThreadIF', count=1)
        self.assertContains(response, 'aria-label="Action"')
        self.assertNotContains(response, '>Action<')
        self.assertContains(response, 'Interfaceを削除')
        self.assertContains(response, 'data-refresh-interface-list')

    def test_deleted_published_detail_shows_restore_action(self):
        draft = InterfaceDraft.objects.create(creator=self.user, kind=Interface.THREAD, name='Restore action')
        interface, _ = publish_draft(draft.pk)
        interface.status = Interface.DELETED
        interface.save(update_fields=['status'])

        response = self.client.get(reverse('interfaces:published-detail', args=[interface.pk]))

        self.assertContains(response, 'aria-label="Action"')
        self.assertNotContains(response, '>Action<')
        self.assertContains(response, 'Interfaceを復元')
        self.assertContains(response, 'data-refresh-interface-list')
        self.assertNotContains(response, 'Interfaceを削除')

    def test_definition_detail_is_reusable_without_management_actions(self):
        draft = InterfaceDraft.objects.create(creator=self.user, kind=Interface.THREAD, name='Reusable')
        InterfaceDraftField.objects.create(
            draft=draft,
            definition=create_field(self.user, '参加人数', FieldType.INTEGER),
            required=True,
            position=0,
        )
        interface, _ = publish_draft(draft.pk)

        response = self.client.get(reverse('interfaces:definition-detail', args=[interface.pk]))

        self.assertContains(response, 'class="interface-definition-detail')
        self.assertNotContains(response, 'Reusable@interface_editor')
        self.assertContains(response, '参加人数')
        self.assertNotContains(response, '定義を編集')

    def test_deleted_definition_detail_is_visible_only_to_owner(self):
        draft = InterfaceDraft.objects.create(creator=self.user, kind=Interface.THREAD, name='Deleted')
        interface, _ = publish_draft(draft.pk)
        interface.status = Interface.DELETED
        interface.save(update_fields=['status'])

        owner_response = self.client.get(reverse('interfaces:definition-detail', args=[interface.pk]))
        self.client.logout()
        public_response = self.client.get(reverse('interfaces:definition-detail', args=[interface.pk]))

        self.assertContains(owner_response, '削除済み')
        self.assertEqual(public_response.status_code, 404)

    def test_add_field_panes_are_loaded_separately(self):
        draft = InterfaceDraft.objects.create(creator=self.user, kind=Interface.THREAD, name='Child')

        list_response = self.client.get(reverse('interfaces:add-field-list', args=[draft.pk]))
        detail_response = self.client.get(reverse('interfaces:add-field-detail', args=[draft.pk, self.definition.pk]))

        self.assertContains(list_response, 'data-mypage-pane="add-field-list"')
        self.assertNotContains(list_response, 'data-mypage-pane="add-field-detail"')
        self.assertContains(detail_response, 'data-mypage-pane="add-field-detail"')
        self.assertContains(detail_response, '開催日時@interface_editor v1/Field', count=1)

    def test_create_and_save_draft_with_field(self):
        create_response = self.client.post(reverse('interfaces:draft-create'))
        draft = InterfaceDraft.objects.get(creator=self.user)

        self.assertRedirects(create_response, f'/mypage/?section=module&type=interface&subtype=thread&collection=editing&draft={draft.pk}')
        save_response = self.client.post(
            reverse('interfaces:draft-update', args=[draft.pk]),
            self.field_payload(),
        )
        draft.refresh_from_db()
        self.assertRedirects(save_response, f'/mypage/?section=module&type=interface&subtype=thread&collection=editing&draft={draft.pk}')
        self.assertEqual(draft.name, 'Event')
        self.assertEqual(draft.fields.get().definition, self.definition)

    def test_definition_editor_header_uses_interface_identity(self):
        draft = InterfaceDraft.objects.create(creator=self.user, kind=Interface.THREAD, name='Editing')

        response = self.client.get(reverse('interfaces:draft-detail', args=[draft.pk]))

        self.assertContains(response, 'Editing@interface_editor v1/ThreadIF', count=1)
        self.assertContains(response, 'aria-label="Action"')
        self.assertNotContains(response, '>Action<')
        self.assertContains(response, 'form="interface-draft-form"', count=2)
        self.assertContains(response, '>中断<')
        self.assertContains(response, '>公開<')
        self.assertContains(response, '>破棄<')

    def test_publish_saves_submitted_values_and_creates_v1(self):
        draft = InterfaceDraft.objects.create(creator=self.user, kind=Interface.THREAD, name='Draft')
        response = self.client.post(
            reverse('interfaces:draft-update', args=[draft.pk]),
            self.field_payload(action='publish'),
        )

        interface = Interface.objects.get(creator=self.user)
        self.assertRedirects(response, '/mypage/?section=module&type=interface&subtype=thread')
        self.assertEqual(interface.name, 'Event')
        self.assertEqual(interface.current_version.version_number, 1)
        self.assertEqual(interface.current_version.fields.get().definition, self.definition)
        self.assertFalse(InterfaceDraft.objects.filter(pk=draft.pk).exists())

    def test_edit_definition_clones_current_version_into_draft(self):
        draft = InterfaceDraft.objects.create(creator=self.user, kind=Interface.THREAD, name='Event')
        source_field = InterfaceDraftField.objects.create(
            draft=draft,
            definition=self.definition,
            required=True,
            position=0,
        )
        interface, _ = publish_draft(draft.pk)

        response = self.client.post(reverse('interfaces:draft-edit', args=[interface.pk]))

        edit_draft = InterfaceDraft.objects.get(interface=interface)
        self.assertRedirects(response, f'/mypage/?section=module&type=interface&subtype=thread&collection=editing&draft={edit_draft.pk}')
        self.assertEqual(edit_draft.name, 'Event')
        self.assertEqual(edit_draft.publication_version_number, 2)
        self.assertEqual(edit_draft.fields.get().field_key, source_field.field_key)

    def test_edit_definition_publishes_next_version_with_renamed_interface(self):
        draft = InterfaceDraft.objects.create(creator=self.user, kind=Interface.THREAD, name='Event')
        interface, first_version = publish_draft(draft.pk)
        self.client.post(reverse('interfaces:draft-edit', args=[interface.pk]))
        edit_draft = InterfaceDraft.objects.get(interface=interface)

        response = self.client.post(
            reverse('interfaces:draft-update', args=[edit_draft.pk]),
            self.field_payload(name='Renamed Event', action='publish'),
        )

        interface.refresh_from_db()
        self.assertRedirects(response, '/mypage/?section=module&type=interface&subtype=thread')
        self.assertEqual(interface.pk, first_version.interface_id)
        self.assertEqual(interface.name, 'Renamed Event')
        self.assertEqual(interface.current_version.version_number, 2)
        self.assertEqual(interface.versions.get(version_number=1).name, 'Event')

    def test_edit_definition_reuses_existing_draft(self):
        draft = InterfaceDraft.objects.create(creator=self.user, kind=Interface.THREAD, name='Event')
        interface, _ = publish_draft(draft.pk)

        self.client.post(reverse('interfaces:draft-edit', args=[interface.pk]))
        first_draft = InterfaceDraft.objects.get(interface=interface)
        response = self.client.post(reverse('interfaces:draft-edit', args=[interface.pk]))

        self.assertRedirects(response, f'/mypage/?section=module&type=interface&subtype=thread&collection=editing&draft={first_draft.pk}')
        self.assertEqual(InterfaceDraft.objects.filter(interface=interface).count(), 1)

    def test_user_cannot_edit_another_users_draft(self):
        other = get_user_model().objects.create_user('other_editor', password='eightchars')
        draft = InterfaceDraft.objects.create(creator=other, kind=Interface.THREAD, name='Other')

        response = self.client.post(
            reverse('interfaces:draft-update', args=[draft.pk]),
            self.field_payload(),
        )

        self.assertEqual(response.status_code, 404)

    def test_draft_can_save_and_publish_multiple_fields(self):
        second = create_field(self.user, '終了日時', FieldType.DATETIME)
        draft = InterfaceDraft.objects.create(creator=self.user, kind=Interface.THREAD, name='Child')
        payload = self.field_payload(name='Child', action='publish')
        payload.update({
            'fields-TOTAL_FORMS': '2',
            'fields-1-field_id': '',
            'fields-1-definition_id': str(second.pk),
            'fields-1-required': '',
            'fields-1-DELETE': '',
        })
        response = self.client.post(
            reverse('interfaces:draft-update', args=[draft.pk]),
            payload,
        )

        self.assertRedirects(response, '/mypage/?section=module&type=interface&subtype=thread')
        child = Interface.objects.get(name='Child')
        self.assertEqual(child.current_version.fields.count(), 2)

    def test_removing_first_field_compacts_positions(self):
        second = create_field(self.user, '終了日時', FieldType.DATETIME)
        draft = InterfaceDraft.objects.create(creator=self.user, kind=Interface.THREAD, name='Compact')
        first_binding = InterfaceDraftField.objects.create(
            draft=draft, definition=self.definition, position=0
        )
        second_binding = InterfaceDraftField.objects.create(
            draft=draft, definition=second, position=1
        )
        payload = self.field_payload(name='Compact')
        payload.update({
            'fields-TOTAL_FORMS': '2',
            'fields-INITIAL_FORMS': '2',
            'fields-0-field_id': str(first_binding.pk),
            'fields-0-definition_id': str(self.definition.pk),
            'fields-0-required': '',
            'fields-0-DELETE': 'on',
            'fields-1-field_id': str(second_binding.pk),
            'fields-1-definition_id': str(second.pk),
            'fields-1-required': '',
            'fields-1-DELETE': '',
        })

        response = self.client.post(reverse('interfaces:draft-update', args=[draft.pk]), payload)

        self.assertRedirects(response, f'/mypage/?section=module&type=interface&subtype=thread&collection=editing&draft={draft.pk}')
        remaining = draft.fields.get()
        self.assertEqual(remaining.definition, second)
        self.assertEqual(remaining.position, 0)

    def test_owner_can_soft_delete_and_restore_interface(self):
        draft = InterfaceDraft.objects.create(creator=self.user, kind=Interface.THREAD, name='Temporary')
        interface, _ = publish_draft(draft.pk)

        delete_response = self.client.post(reverse('interfaces:delete', args=[interface.pk]))
        interface.refresh_from_db()
        self.assertRedirects(delete_response, '/mypage/?section=module&type=interface&subtype=thread')
        self.assertEqual(interface.status, Interface.DELETED)

        restore_response = self.client.post(reverse('interfaces:restore', args=[interface.pk]))
        interface.refresh_from_db()
        self.assertRedirects(restore_response, f'/mypage/?section=module&type=interface&subtype=thread&interface={interface.pk}')
        self.assertEqual(interface.status, Interface.ACTIVE)
        self.assertEqual(interface.current_version.version_number, 1)

    def test_user_cannot_delete_another_users_interface(self):
        other = get_user_model().objects.create_user('interface_owner_2', password='eightchars')
        draft = InterfaceDraft.objects.create(creator=other, kind=Interface.THREAD, name='Protected')
        interface, _ = publish_draft(draft.pk)

        response = self.client.post(reverse('interfaces:delete', args=[interface.pk]))

        self.assertEqual(response.status_code, 404)
        interface.refresh_from_db()
        self.assertEqual(interface.status, Interface.ACTIVE)

    def test_user_cannot_restore_another_users_interface(self):
        other = get_user_model().objects.create_user('interface_owner_3', password='eightchars')
        draft = InterfaceDraft.objects.create(creator=other, kind=Interface.THREAD, name='Protected restore')
        interface, _ = publish_draft(draft.pk)
        interface.status = Interface.DELETED
        interface.save(update_fields=['status'])

        response = self.client.post(reverse('interfaces:restore', args=[interface.pk]))

        self.assertEqual(response.status_code, 404)
        interface.refresh_from_db()
        self.assertEqual(interface.status, Interface.DELETED)


class ThreadInterfaceServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('thread_interface_owner', password='eightchars')

    def publish(self, name, field_type=FieldType.SHORT_TEXT, required=False, settings=None):
        draft = InterfaceDraft.objects.create(creator=self.user, kind=Interface.THREAD, name=name)
        definition = create_field(self.user, f'{name} value', field_type, settings)
        field = InterfaceDraftField.objects.create(
            draft=draft,
            definition=definition,
            required=required,
            position=0,
        )
        interface, _ = publish_draft(draft.pk)
        return interface, field.field_key

    def test_prepare_and_save_thread_interface_values(self):
        interface, field_key = self.publish('Text', required=True)
        prepared = prepare_thread_interfaces(
            [interface.pk],
            {(interface.pk, str(field_key)): ['入力値']},
        )
        thread = Thread.objects.create(title='Interface付きThread')

        save_thread_interfaces(thread, prepared)

        implementation = ThreadInterfaceImplementation.objects.get(thread=thread)
        self.assertEqual(implementation.version, interface.current_version)
        self.assertEqual(implementation.values.get().value, '入力値')

    def test_required_field_rejects_missing_value(self):
        interface, _ = self.publish('Required', required=True)

        with self.assertRaises(ValidationError):
            prepare_thread_interfaces([interface.pk], {})

    def test_direct_field_and_interface_share_one_value(self):
        definition = create_field(self.user, 'Shared')
        draft = InterfaceDraft.objects.create(creator=self.user, kind=Interface.THREAD, name='Shared IF')
        draft_field = InterfaceDraftField.objects.create(
            draft=draft,
            definition=definition,
            required=True,
            position=0,
        )
        interface, _ = publish_draft(draft.pk)
        prepared_direct, prepared_interfaces = prepare_thread_fields(
            [definition.pk],
            {str(definition.key): ['Directの値']},
            [interface.pk],
            {(interface.pk, str(draft_field.field_key)): ['Interfaceの値']},
        )
        thread = Thread.objects.create(title='共有Thread')

        save_thread_fields(thread, prepared_direct, prepared_interfaces)

        direct = ThreadDirectField.objects.select_related('binding__value').get(thread=thread)
        interface_value = ThreadInterfaceImplementation.objects.get(thread=thread).values.get()
        self.assertEqual(thread.field_values.count(), 1)
        self.assertEqual(direct.binding.value_id, interface_value.binding.value_id)
        self.assertEqual(direct.value, 'Directの値')

    def test_direct_synonym_fields_share_first_direct_value(self):
        target = create_field(self.user, 'Target')
        source, _ = publish_field_definition(
            creator=self.user,
            name='Source',
            field_type=FieldType.SHORT_TEXT,
            synonym_target_ids=[target.pk],
        )
        prepared_direct, prepared_interfaces = prepare_thread_fields(
            [target.pk, source.pk],
            {
                str(target.key): ['先の値'],
                str(source.key): ['後の値'],
            },
            [],
            {},
        )
        thread = Thread.objects.create(title='片同義DirectField')

        save_thread_fields(thread, prepared_direct, prepared_interfaces)

        direct_fields = list(ThreadDirectField.objects.select_related('binding__value'))
        self.assertEqual(thread.field_values.count(), 1)
        self.assertEqual({item.binding.value_id for item in direct_fields}, {thread.field_values.get().pk})
        self.assertEqual({item.value for item in direct_fields}, {'先の値'})

    def test_shared_field_is_resolved_for_each_interface_without_extra_interface(self):
        definition = create_field(self.user, 'Shared')
        children = []
        for name in ('Child A', 'Child B'):
            draft = InterfaceDraft.objects.create(creator=self.user, kind=Interface.THREAD, name=name)
            InterfaceDraftField.objects.create(draft=draft, definition=definition, position=0)
            children.append(publish_draft(draft.pk)[0])

        prepared = prepare_thread_interfaces([item.pk for item in children], {})

        self.assertEqual([version.interface.name for version, _ in prepared], ['Child A', 'Child B'])

    def test_catalog_provides_reusable_definition_detail_url(self):
        interface, _ = self.publish('Catalog')

        item = thread_interface_catalog()[0]

        self.assertEqual(item['id'], interface.pk)
        self.assertEqual(item['detail_url'], reverse('interfaces:definition-detail', args=[interface.pk]))
        self.assertEqual(item['kind'], 'ThreadIF')


class IndependentFieldTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('field_owner', password='eightchars')

    def make_interface(self, name, definition, required=False):
        draft = InterfaceDraft.objects.create(creator=self.user, kind=Interface.THREAD, name=name)
        draft_field = InterfaceDraftField.objects.create(
            draft=draft,
            definition=definition,
            required=required,
            position=0,
        )
        interface, _ = publish_draft(draft.pk)
        return interface, draft_field.field_key

    def test_field_update_creates_an_immutable_next_version(self):
        definition, first = publish_field_definition(
            creator=self.user,
            name='開始時刻',
            field_type=FieldType.DATETIME,
        )

        definition, second = publish_field_definition(
            creator=self.user,
            definition=definition,
            name='開始日時',
            field_type=FieldType.DATETIME,
        )

        self.assertEqual((first.version_number, second.version_number), (1, 2))
        self.assertEqual(definition.current_version, second)
        first.name = '変更不可'
        with self.assertRaises(ValidationError):
            first.save()

    def test_field_type_cannot_change_between_versions(self):
        definition, _ = publish_field_definition(
            creator=self.user,
            name='人数',
            field_type=FieldType.INTEGER,
        )

        with self.assertRaises(ValidationError):
            publish_field_definition(
                creator=self.user,
                definition=definition,
                name='人数',
                field_type=FieldType.SHORT_TEXT,
            )

    def test_one_way_synonym_expands_search_only_from_source(self):
        target, _ = publish_field_definition(
            creator=self.user,
            name='好きなポケモン',
            field_type=FieldType.SHORT_TEXT,
        )
        source, _ = publish_field_definition(
            creator=self.user,
            name='好みのポケモン',
            field_type=FieldType.SHORT_TEXT,
            synonym_target_ids=[target.pk],
        )

        self.assertEqual(expand_field_definition_ids([source.pk]), {source.pk, target.pk})
        self.assertEqual(expand_field_definition_ids([target.pk]), {target.pk})

    def test_thread_catalog_includes_field_identity_and_synonym_targets(self):
        target = create_field(self.user, 'Target')
        source, _ = publish_field_definition(
            creator=self.user,
            name='Source',
            field_type=FieldType.SHORT_TEXT,
            synonym_target_ids=[target.pk],
        )
        interface, _ = self.make_interface('Catalog', source)

        item = next(entry for entry in thread_interface_catalog() if entry['id'] == interface.pk)
        field = item['implementations'][0]['fields'][0]

        self.assertEqual(field['definition_id'], source.pk)
        self.assertEqual(field['synonym_target_ids'], [target.pk])

    def test_synonymous_fields_share_one_thread_value(self):
        target, _ = publish_field_definition(
            creator=self.user,
            name='好きなポケモン',
            field_type=FieldType.SHORT_TEXT,
        )
        source, _ = publish_field_definition(
            creator=self.user,
            name='好みのポケモン',
            field_type=FieldType.SHORT_TEXT,
            synonym_target_ids=[target.pk],
        )
        first, first_key = self.make_interface('First', target)
        second, second_key = self.make_interface('Second', source)
        prepared = prepare_thread_interfaces(
            [first.pk, second.pk],
            {
                (first.pk, str(first_key)): ['ピカチュウ'],
                (second.pk, str(second_key)): ['ミュウ'],
            },
        )
        thread = Thread.objects.create(title='片同義Thread')

        save_thread_interfaces(thread, prepared)

        interface_values = [
            item
            for implementation in thread.interface_implementations.order_by('position')
            for item in implementation.values.select_related('binding__value')
        ]
        self.assertEqual(thread.field_values.count(), 1)
        self.assertEqual(thread.field_bindings.count(), 2)
        self.assertEqual({item.binding.value_id for item in interface_values}, {thread.field_values.get().pk})
        self.assertEqual({item.binding.value.value for item in interface_values}, {'ピカチュウ'})


class FieldManagementViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('field_editor', password='eightchars')
        self.client.force_login(self.user)

    def payload(self, **overrides):
        payload = {
            'name': '開催日時',
            'description': 'イベントの開始日時',
            'field_type': FieldType.DATETIME,
            'options': '',
            'synonym_targets': [],
        }
        payload.update(overrides)
        return payload

    def test_field_can_be_created_without_a_draft(self):
        response = self.client.post(reverse('interfaces:field-publish-new'), self.payload())

        definition = self.user.field_definitions.get()
        self.assertRedirects(
            response,
            f'/mypage/?section=module&type=element&subtype=field&field={definition.pk}',
        )
        self.assertEqual(definition.current_version.version_number, 1)

    def test_field_list_and_detail_are_separate_panes(self):
        definition, _ = publish_field_definition(
            creator=self.user,
            name='一覧Field',
            field_type=FieldType.DATETIME,
            description='一覧Fieldの詳細',
        )

        list_response = self.client.get(reverse('interfaces:module-management-list'))
        detail_response = self.client.get(reverse('interfaces:field-detail', args=[definition.pk]))

        self.assertContains(list_response, 'data-mypage-pane="module-list"')
        self.assertNotContains(list_response, 'data-mypage-pane="field-detail"')
        self.assertContains(detail_response, 'data-mypage-pane="field-detail"')
        self.assertContains(detail_response, '一覧Field@field_editor v1/Field', count=1)
        self.assertContains(detail_response, '<dt>詳細：</dt><dd>一覧Fieldの詳細</dd>')
        self.assertContains(detail_response, '<dt>型：</dt><dd>日時</dd>')
        self.assertContains(detail_response, 'class="interface-action-buttons"')
        self.assertContains(detail_response, 'class="button event-delete-button"')

    def test_field_search_uses_and_partial_matches_and_excludes_deleted_fields(self):
        other = get_user_model().objects.create_user('AccountA', password='eightchars')
        match = create_field(other, '開始日時', FieldType.DATETIME)
        publish_field_definition(
            creator=other,
            definition=match,
            name='開始日時',
            field_type=FieldType.DATETIME,
            description='地域イベントの開始時刻',
        )
        wrong_description = create_field(other, '終了日時', FieldType.DATETIME)
        deleted = create_field(other, '削除日時', FieldType.DATETIME)
        deleted.status = deleted.DELETED
        deleted.save(update_fields=['status', 'updated_at'])

        response = self.client.get(reverse('interfaces:field-search'), {
            'name': '@accounta',
            'description': 'イベント',
            'field_type': FieldType.DATETIME,
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '開始日時@AccountA v2/Field')
        self.assertNotContains(response, wrong_description.name)
        self.assertNotContains(response, deleted.name)

    def test_field_search_is_newest_first_and_paginated_by_ten(self):
        fields = [create_field(self.user, f'検索Field{i:02}') for i in range(11)]
        now = timezone.now()
        for index, field in enumerate(fields):
            FieldDefinition.objects.filter(pk=field.pk).update(
                updated_at=now - timedelta(minutes=index),
            )

        first_page = self.client.get(reverse('interfaces:field-search'))
        second_page = self.client.get(reverse('interfaces:field-search'), {'page': 2})
        first_html = first_page.content.decode()

        self.assertEqual(first_html.count('data-detail-url='), 10)
        self.assertLess(first_html.index('検索Field00'), first_html.index('検索Field01'))
        self.assertNotContains(first_page, '検索Field10')
        self.assertContains(second_page, '検索Field10')

    def test_module_field_search_panel_is_open_and_has_expected_filters(self):
        response = self.client.get(reverse('interfaces:module-management-list'))

        self.assertContains(response, 'class="field-search-controls" open')
        self.assertContains(response, 'name="name"')
        self.assertContains(response, 'name="description"')
        self.assertContains(response, 'name="field_type"')
        self.assertNotContains(response, 'name="sort"')

    def test_field_update_marks_referencing_interface_as_stale(self):
        definition = create_field(self.user, '更新Field')
        draft = InterfaceDraft.objects.create(creator=self.user, kind=Interface.THREAD, name='Stale')
        InterfaceDraftField.objects.create(draft=draft, definition=definition, position=0)
        interface, _ = publish_draft(draft.pk)

        publish_field_definition(
            creator=self.user,
            definition=definition,
            name='更新Field',
            field_type=FieldType.SHORT_TEXT,
            description='v2',
        )

        response = self.client.get(reverse('interfaces:module-management-list'))
        self.assertContains(response, '更新が必要')
        with self.assertRaises(ValidationError):
            prepare_thread_interfaces([interface.pk], {})

    def test_field_update_with_synonym_is_displayed(self):
        target = create_field(self.user, 'Target')
        source = create_field(self.user, 'Source')

        response = self.client.post(
            reverse('interfaces:field-publish', args=[source.pk]),
            self.payload(name='Source', field_type=FieldType.SHORT_TEXT, synonym_targets=[str(target.pk)]),
        )
        source.refresh_from_db()

        self.assertRedirects(
            response,
            f'/mypage/?section=module&type=element&subtype=field&field={source.pk}',
        )
        self.assertEqual(source.current_version.synonyms.get().target, target)
