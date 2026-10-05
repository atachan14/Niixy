"""v0.10 common ThreadPolicy regression tests, always run on isolated SQLite."""
import json
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from events.models import Thread, ThreadAccessRule, ThreadPlacement, ThreadPolicyCondition, ThreadPost
from events.policies import prepare_thread_policy, save_thread_policy
from rooms.models import Board, RoomMembership
from rooms.services import create_room


class ThreadPolicyTests(TestCase):
    def setUp(self):
        users = get_user_model().objects
        self.owner = users.create_user('policy_owner')
        self.member = users.create_user('policy_member')
        self.other = users.create_user('policy_other')
        self.room, _ = create_room(submission_id=uuid4(), owner=self.owner, name='Policy Room',
                                  description='', latitude='35', longitude='139')
        self.board = Board.objects.get(placement__collection__room=self.room)
        self.guest = AnonymousUser()

    def condition(self, code):
        return {'kind': 'default', 'definition': {'code': code}}

    def payload(self, **groups):
        result = {f'policy_{cap}_{decision}_groups': '[]'
                  for cap in ('view', 'write') for decision in ('allow', 'deny')}
        result.update({f'policy_{key}_groups': json.dumps(value) for key, value in groups.items()})
        return result

    def thread(self, **groups):
        thread = Thread.objects.create(creator=self.owner, title='Policy Thread')
        ThreadPost.objects.create(thread=thread, creator=self.owner, number=1, body='PRIVATE BODY')
        save_thread_policy(thread, prepare_thread_policy(self.payload(**groups), self.owner))
        return thread

    def test_or_and_deny_and_current_membership(self):
        room = {'kind': 'room', 'definition': {'room_id': self.room.pk, 'relation': 'member'}}
        account = {'kind': 'account', 'definition': {'account_id': self.other.pk}}
        thread = self.thread(view_allow=[[self.condition('account'), room], [self.condition('guest')]],
                             view_deny=[[account]])
        self.assertTrue(thread.allows(self.guest, 'view'))
        self.assertFalse(thread.allows(self.member, 'view'))
        RoomMembership.objects.create(room=self.room, account=self.member)
        self.assertTrue(thread.allows(self.member, 'view'))
        RoomMembership.objects.create(room=self.room, account=self.other)
        self.assertFalse(thread.allows(self.other, 'view'))
        RoomMembership.objects.filter(room=self.room, account=self.member).delete()
        self.assertFalse(thread.allows(self.member, 'view'))

    def test_empty_and_creator_view_exception_not_write_exception(self):
        thread = self.thread(view_deny=[[self.condition('account')]])
        self.assertTrue(thread.allows(self.owner, 'view'))
        self.assertFalse(thread.allows(self.owner, 'write'))
        self.assertFalse(thread.allows(self.other, 'view'))
        self.assertFalse(thread.allows(self.guest, 'view'))

    def test_self_is_snapshot_of_author_and_labels_are_trusted(self):
        condition = self.condition('self')
        condition['label'] = 'UNTRUSTED LABEL'
        thread = self.thread(write_allow=[[condition]])
        saved = thread.policy_conditions.get()
        self.assertEqual(saved.kind, 'account')
        self.assertEqual(saved.definition, {'account_id': self.owner.pk})
        self.assertEqual(saved.label, '@policy_owner')
        self.assertTrue(thread.allows(self.owner, 'write'))
        self.assertFalse(thread.allows(self.other, 'write'))
        with self.assertRaisesMessage(ValidationError, 'Login'):
            prepare_thread_policy(self.payload(write_allow=[[condition]]), self.guest)

    def test_invalid_policy_creation_is_atomic(self):
        url = reverse('events:thread-create')
        base = {'submission_id': str(uuid4()), 'title': 'Invalid', 'body': 'No save',
                'latitude': '35', 'longitude': '139'}
        for raw in ['null', '{}', '[[]]', '[1]', '[{"kind":"default"}]',
                    '[[{"kind":"field","definition":{}}]]',
                    '[[{"kind":"default","definition":[]}]]',
                    '[[{"kind":"default","definition":{"code":"self"}}]]']:
            with self.subTest(raw=raw):
                response = self.client.post(url, {**base, **self.payload(), 'policy_view_allow_groups': raw})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(Thread.objects.count(), 0)
                self.assertEqual(ThreadPost.objects.count(), 0)

    def test_new_thread_has_no_implicit_board_room_gate(self):
        thread = self.thread(view_allow=[[self.condition('guest')], [self.condition('account')]],
                             write_allow=[[self.condition('guest')], [self.condition('account')]])
        ThreadPlacement.objects.create(thread=thread, kind='board', board=self.board)
        # Even denying Board view does not affect an independent Thread route.
        self.board.policy_conditions.filter(capability='view').delete()
        for actor in (self.other, self.guest):
            if actor.is_authenticated:
                self.client.force_login(actor)
            else:
                self.client.logout()
            detail = self.client.get(reverse('accounts:thread-detail', args=[self.owner.username, thread.pk]))
            self.assertContains(detail, 'PRIVATE BODY')
            response = self.client.post(reverse('events:thread-post-create', args=[thread.pk]),
                                        {'submission_id': str(uuid4()), 'body': 'Allowed by Thread'})
            self.assertEqual(response.status_code, 200)

    def test_explicit_room_condition_survives_board_delete(self):
        room = {'kind': 'room', 'definition': {'room_id': self.room.pk, 'relation': 'member'}}
        thread = self.thread(view_allow=[[self.condition('account')]], write_allow=[[room]])
        ThreadPlacement.objects.create(thread=thread, kind='board', board=self.board)
        self.board.delete()
        self.assertTrue(thread.policy_conditions.filter(kind='room').exists())
        self.client.force_login(self.other)
        response = self.client.post(reverse('events:thread-post-create', args=[thread.pk]), {'body': 'Denied'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(thread.posts.count(), 1)
        self.assertTrue(thread.allows(self.owner, 'write'))

    def test_reply_requires_view_even_if_write_is_allowed(self):
        thread = self.thread(write_allow=[[self.condition('account')]])
        self.client.force_login(self.other)
        response = self.client.post(reverse('events:thread-post-create', args=[thread.pk]), {'body': 'Denied'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(thread.posts.count(), 1)

    def test_legacy_saved_rules_have_no_implicit_room_gate(self):
        thread = Thread.objects.create(creator=self.owner, title='Legacy')
        ThreadPlacement.objects.create(thread=thread, kind='board', board=self.board)
        ThreadAccessRule.objects.create(thread=thread, capability='write', audience='account')
        self.assertTrue(thread.allows(self.other, 'write'))
        self.assertTrue(thread.allows(self.owner, 'write'))
        self.assertEqual(thread.policy_conditions.count(), 0)
        self.board.delete()
        self.assertTrue(thread.allows(self.other, 'write'))
        self.assertEqual(thread.access_rules.count(), 1)

    def test_condition_history_edit_and_delete_do_not_change_snapshot(self):
        from accounts.models import AccountCondition
        history = AccountCondition.objects.create(owner=self.owner, fingerprint='thread-test',
                                                   kind='account', definition={'account_id': self.other.pk},
                                                   label='History label')
        condition = {'id': history.pk, 'kind': history.kind,
                     'definition': history.definition, 'label': history.label}
        thread = self.thread(view_allow=[[condition]])
        saved = thread.policy_conditions.get()
        history.definition = {'account_id': self.member.pk}
        history.save(update_fields=['definition'])
        history.delete()
        self.assertEqual(saved.definition, {'account_id': self.other.pk})
        self.assertTrue(thread.allows(self.other, 'view'))
        self.assertFalse(thread.allows(self.member, 'view'))

    def test_unsupported_board_policy_snapshot_rolls_back_edit(self):
        self.client.force_login(self.owner)
        original = self.board.name
        response = self.client.post(reverse('rooms:board-edit', args=[self.room.pk, self.board.pk]),
                                    {'name': 'No partial edit', 'description': '', 'policy_present': 'true',
                                     'policy_view_allow_groups': '[[{"kind":"field","definition":{}}]]'})
        self.assertEqual(response.status_code, 400)
        self.board.refresh_from_db()
        self.assertEqual(self.board.name, original)

    def test_new_denied_detail_and_response_history_exclude_post_body(self):
        thread = self.thread(view_allow=[[{'kind': 'account',
                                          'definition': {'account_id': self.member.pk}}]],
                             view_deny=[[self.condition('guest')]])
        ThreadPost.objects.create(thread=thread, number=2, creator=self.owner, body='PRIVATE RESPONSE')
        detail = self.client.get(reverse('accounts:thread-detail', args=[self.owner.username, thread.pk]))
        self.assertContains(detail, 'data-thread-view-unavailable')
        self.assertContains(detail, '閲覧不可条件')
        self.assertNotContains(detail, 'PRIVATE BODY')
        self.assertNotContains(detail, 'PRIVATE RESPONSE')
        self.assertNotContains(detail, 'thread-reply-form')
        history = self.client.get(reverse('accounts:response-pane', args=[self.owner.username]))
        self.assertNotContains(history, 'PRIVATE RESPONSE')

    def test_search_uses_new_policy_allow_deny_and_protects_body(self):
        public = self.thread(view_allow=[[self.condition('guest')]])
        denied = self.thread(view_allow=[[self.condition('guest')]], view_deny=[[self.condition('guest')]])
        for thread in (public, denied):
            ThreadPlacement.objects.create(thread=thread, kind='niimap', latitude='35', longitude='139')
        url = reverse('events:thread-search')
        data = {'policy_conditions': json.dumps([{'capability': 'view', 'decision': 'allow',
                                                 'account_groups': [[self.condition('guest')]]}])}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['thread_ids'], [public.pk])
        response = self.client.post(url, {'freeword_include': 'PRIVATE BODY'})
        self.assertEqual(response.json()['thread_ids'], [public.pk])

    def test_generic_account_search_uses_saved_deny_conditions(self):
        thread = self.thread(view_allow=[[self.condition('account')]],
                             view_deny=[[self.condition('account')]])
        thread.creator = None
        thread.save(update_fields=['creator'])
        ThreadPlacement.objects.create(thread=thread, kind='niimap', latitude='35', longitude='139')
        response = self.client.post(reverse('events:thread-search'), {
            'policy_conditions': json.dumps([{'capability': 'view', 'decision': 'allow',
                                             'account_groups': [[self.condition('account')]]}]),
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['thread_ids'], [])

    def test_denied_metadata_is_absent_from_detail_lists_markers_and_search(self):
        from interfaces.models import (FieldDefinition, FieldVersion, ThreadFieldValue, ThreadFieldBinding,
                                       ThreadDirectField, Interface, InterfaceVersion, ThreadInterfaceImplementation)
        thread = self.thread(view_allow=[[self.condition('account')]], view_deny=[[self.condition('guest')]])
        ThreadPlacement.objects.create(thread=thread, kind='niimap', latitude='35.123456', longitude='139.654321')
        field = FieldDefinition.objects.create(creator=self.owner, name='Private Bound Field')
        version = FieldVersion.objects.create(definition=field, version_number=1, name=field.name, field_type='text')
        value = ThreadFieldValue.objects.create(thread=thread, value='PRIVATE FIELD VALUE')
        binding = ThreadFieldBinding.objects.create(thread=thread, definition=field, value=value)
        ThreadDirectField.objects.create(thread=thread, definition=field, version=version, binding=binding, position=0)
        interface = Interface.objects.create(creator=self.owner, kind='thread', name='Private Bound Interface')
        iv = InterfaceVersion.objects.create(interface=interface, version_number=1, name=interface.name)
        ThreadInterfaceImplementation.objects.create(thread=thread, interface=interface, version=iv, position=0)
        ThreadPost.objects.create(thread=thread, creator=self.other, number=2, body='PRIVATE RESPONSE')
        ThreadPost.objects.create(thread=thread, creator=self.other, number=3, body='PRIVATE RESPONSE AGAIN')
        response = self.client.get(reverse('accounts:thread-detail', args=[self.owner.username, thread.pk]))
        for private in ['data-thread-post-count', 'ui-placement-row', '35.123456', '139.654321',
                        field.name, interface.name, 'PRIVATE FIELD VALUE', 'PRIVATE BODY', 'PRIVATE RESPONSE']:
            self.assertNotContains(response, private)
        self.assertContains(response, thread.title)
        self.assertContains(response, 'data-thread-view-unavailable')
        listing = self.client.get(reverse('accounts:thread-pane', args=[self.owner.username]))
        self.assertContains(listing, thread.title)
        self.assertContains(listing, '\u95b2\u89a7\u4e0d\u53ef')
        self.assertNotContains(listing, f'{thread.title} (3)')
        responses = self.client.get(reverse('accounts:response-pane', args=[self.other.username]))
        self.assertContains(responses, 'data-response-thread=', count=1)
        self.assertEqual(responses.context['response_page'].paginator.count, 1)
        self.assertNotContains(responses, 'data-response-post=')
        self.assertNotContains(responses, 'PRIVATE RESPONSE')
        map_response = self.client.get(reverse('events:map'))
        self.assertEqual(map_response.context['thread_markers'], [])
        self.assertNotContains(map_response, '35.123456')
        self.assertNotContains(map_response, '139.654321')
        for filters in [
            {'freeword_include': 'PRIVATE FIELD VALUE'},
            {'freeword_include': 'PRIVATE BODY'},
            {'creator_include': self.owner.username},
            {'creator_exclude': 'unrelated'},
            {'field_conditions': json.dumps([{'field_id': field.pk, 'operator': 'contains', 'value': 'PRIVATE'}])},
            {'interface_conditions': json.dumps([{'interface_id': interface.pk, 'operator': 'include'}])},
        ]:
            with self.subTest(filters=filters):
                search = self.client.post(reverse('events:thread-search'), filters)
                self.assertEqual(search.status_code, 200)
                self.assertNotIn(thread.pk, search.json()['thread_ids'])
        search = self.client.post(reverse('events:thread-search'), {'freeword_include': thread.title})
        self.assertIn(thread.pk, search.json()['thread_ids'])


class ThreadPolicyMigrationTests(TransactionTestCase):
    def test_migration_copies_saved_rules_without_changing_posts_or_empty_policy(self):
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor

        self.assertEqual(connection.vendor, 'sqlite')
        before = [('events', '0015_threadplacement_board_threadplacement_is_primary_and_more')]
        after = [('events', '0017_migrate_thread_policies')]
        executor = MigrationExecutor(connection)
        executor.migrate(before)
        historical = executor.loader.project_state(before).apps
        OldThread = historical.get_model('events', 'Thread')
        OldPost = historical.get_model('events', 'ThreadPost')
        OldRule = historical.get_model('events', 'ThreadAccessRule')
        thread = OldThread.objects.create(title='Migration Thread')
        empty = OldThread.objects.create(title='Empty Policy')
        post = OldPost.objects.create(thread=thread, number=1, body='PRESERVED')
        OldRule.objects.create(thread=thread, capability='view', audience='guest')
        OldRule.objects.create(thread=thread, capability='write', audience='account')
        try:
            executor = MigrationExecutor(connection)
            executor.migrate(after)
            migrated = executor.loader.project_state(after).apps
            Condition = migrated.get_model('events', 'ThreadPolicyCondition')
            conditions = list(Condition.objects.filter(thread_id=thread.pk))
            self.assertEqual(len(conditions), 2)
            self.assertEqual({item.kind for item in conditions}, {'default'})
            self.assertEqual({item.decision for item in conditions}, {'allow'})
            self.assertEqual({item.definition['code'] for item in conditions}, {'guest', 'account'})
            self.assertEqual(len({item.group_key for item in conditions}), 2)
            self.assertFalse(Condition.objects.filter(thread_id=empty.pk).exists())
            self.assertEqual(migrated.get_model('events', 'ThreadPost').objects.get(pk=post.pk).body, 'PRESERVED')
            self.assertEqual(migrated.get_model('events', 'ThreadAccessRule').objects.count(), 2)
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
