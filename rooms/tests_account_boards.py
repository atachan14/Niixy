import importlib
from uuid import uuid4
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase
from django.urls import reverse

from events.models import Thread, ThreadPlacement, ThreadPost
from interfaces.models import FieldType, ThreadDirectField
from interfaces.services import publish_field_definition
from .models import Board, BoardPlacement, BoardPolicyCondition, Collection
from .services import create_board


class AccountBoardTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user('diary_owner')
        self.other = get_user_model().objects.create_user('diary_other')
        self.main = self.owner.collections.get(name='Main')
        self.fallback = self.owner.collections.get(is_uncategorized=True)
        self.diary = Board.objects.get(placement__collection=self.main)

    def url(self, name, *ids, account=None):
        return reverse('accounts:' + name, args=[(account or self.owner).username, *ids])

    def post_thread(self, board=None, **changes):
        data = {'submission_id': str(uuid4()), 'title': 'Diary Thread', 'body': 'private test body',
                'view_guest': 'true', 'view_account': 'true', 'write_account': 'true'}
        data.update(changes)
        return self.client.post(self.url('board-thread-create', (board or self.diary).pk), data)

    def test_initial_structure_and_policy(self):
        self.assertEqual(self.owner.collections.count(), 2)
        self.assertEqual(self.diary.name, '日記')
        self.assertFalse(self.main.is_uncategorized)
        self.assertEqual(self.diary.policy_conditions.count(), 3)
        for actor in (AnonymousUser(), self.owner, self.other):
            self.assertTrue(self.diary.evaluate_policy(actor, BoardPolicyCondition.VIEW).allowed)
            self.assertEqual(self.diary.evaluate_policy(actor, BoardPolicyCondition.CREATE_THREAD).allowed,
                             actor == self.owner)
        for actor in (None, self.other, self.owner):
            if actor:
                self.client.force_login(actor)
            else:
                self.client.logout()
            response = self.client.get(self.url('boards'))
            self.assertContains(response, 'data-board-title="日記"')
            self.assertContains(response, 'data-ui-tab="fav"')
            self.assertContains(response, 'data-ui-tab="bad"')
            self.assertNotContains(response, 'data-collection-management-tab')
            self.assertContains(response, 'Listの詳細・管理')
            self.assertEqual('data-board-editor' in self.client.get(self.url('board-threads', self.diary.pk)).content.decode(),
                             actor == self.owner)

    def test_management_requires_owner_and_rejects_cross_container_ids(self):
        endpoints = [('collection-create', (), {'name': 'Forbidden'}),
                     ('collection-edit', (self.main.pk,), {'name': 'Forbidden'}),
                     ('collection-delete', (self.main.pk,), {}),
                     ('board-create', (self.main.pk,), {'name': 'Forbidden'}),
                     ('board-edit', (self.diary.pk,), {'name': 'Forbidden'}),
                     ('board-delete', (self.diary.pk,), {})]
        for actor, status in ((None, 401), (self.other, 403)):
            if actor:
                self.client.force_login(actor)
            for name, ids, data in endpoints:
                with self.subTest(actor=actor, name=name):
                    self.assertEqual(self.client.post(self.url(name, *ids), data).status_code, status)
            self.assertEqual(self.post_thread().status_code, 403)
        self.client.force_login(self.owner)
        other_main = self.other.collections.get(name='Main')
        other_diary = Board.objects.get(placement__collection=other_main)
        for name, ids, data in [('collection-edit', (other_main.pk,), {'name': 'Forbidden'}),
                                ('collection-delete', (other_main.pk,), {}),
                                ('board-create', (other_main.pk,), {'name': 'Forbidden'}),
                                ('board-edit', (other_diary.pk,), {'name': 'Forbidden'}),
                                ('board-delete', (other_diary.pk,), {})]:
            self.assertEqual(self.client.post(self.url(name, *ids), data).status_code, 404)
        self.assertEqual(self.client.get(self.url('board-threads', other_diary.pk)).status_code, 404)

    def test_collection_crud_fallback_and_uncategorized_protection(self):
        self.client.force_login(self.owner)
        created = self.client.post(self.url('collection-create'), {'name': 'CollectionA'})
        self.assertEqual(created.status_code, 200)
        collection = Collection.objects.get(pk=created.json()['collection_id'])
        self.assertEqual(collection.account, self.owner)
        self.assertIsNone(collection.room_id)
        self.assertEqual(self.client.post(self.url('collection-edit', collection.pk), {'name': 'Changed'}).status_code, 200)
        self.assertEqual(self.client.post(self.url('collection-delete', collection.pk)).status_code, 200)
        response = self.client.post(self.url('collection-delete', self.main.pk))
        self.assertIn(f'collection={self.fallback.pk}', response.json()['redirect_url'])
        self.diary.refresh_from_db()
        self.assertEqual(self.diary.placement.collection_id, self.fallback.pk)
        self.assertContains(self.client.get(self.url('boards')), 'data-board-title="日記"')
        self.assertEqual(self.client.get(self.url('board-threads', self.diary.pk)).status_code, 200)
        for name in ('collection-edit', 'collection-delete'):
            self.assertEqual(self.client.post(self.url(name, self.fallback.pk), {'name': 'Invalid'}).status_code, 400)
        created = self.client.post(self.url('board-create', self.fallback.pk), {'name': 'Uncategorized Board'})
        self.assertEqual(created.status_code, 200)
        board = Board.objects.get(pk=created.json()['board_id'])
        self.assertEqual(board.policy_conditions.get(capability='create_thread').definition, {'account_id': self.owner.pk})

    def test_renamed_and_deleted_defaults_are_never_recreated(self):
        self.client.force_login(self.owner)
        self.client.post(self.url('collection-edit', self.main.pk), {'name': 'Archive'})
        self.client.post(self.url('board-edit', self.diary.pk), {'name': 'Journal'})
        self.owner.save()
        self.client.get(self.url('detail'))
        self.client.get(self.url('boards'))
        self.assertFalse(self.owner.collections.filter(name='Main').exists())
        self.assertFalse(Board.objects.filter(placement__collection__account=self.owner, name='日記').exists())
        self.client.post(self.url('board-delete', self.diary.pk))
        self.client.post(self.url('collection-delete', self.main.pk))
        self.owner.save()
        self.client.get(self.url('boards'))
        self.assertEqual(self.owner.collections.count(), 1)
        self.assertFalse(Board.objects.filter(placement__collection__account=self.owner).exists())

    def test_diary_creation_and_reply_use_separate_policies(self):
        self.client.force_login(self.owner)
        response = self.post_thread()
        self.assertEqual(response.status_code, 200)
        thread = Thread.objects.get(pk=response.json()['thread_id'])
        self.assertEqual(thread.creator, self.owner)
        self.assertEqual(thread.posts.get().body, 'private test body')
        self.assertEqual(thread.placements.get().board, self.diary)
        self.assertEqual(thread.policy_conditions.get(capability='write').definition, {'code': 'account'})
        self.client.force_login(self.other)
        detail = self.client.get(self.url('board-thread-detail', thread.pk))
        self.assertContains(detail, 'class="thread-reply-form"')
        self.assertEqual(self.post_thread().status_code, 403)
        reply = self.client.post(reverse('events:thread-post-create', args=[thread.pk]), {'body': 'Other Account reply'})
        self.assertEqual(reply.status_code, 200)
        self.client.logout()
        self.assertContains(self.client.get(self.url('board-thread-detail', thread.pk)), 'private test body')
        self.assertEqual(self.client.post(reverse('events:thread-post-create', args=[thread.pk]), {'body': 'Guest reply'}).status_code, 403)

    def test_guest_reply_when_thread_policy_explicitly_allows_it(self):
        self.client.force_login(self.owner)
        response = self.post_thread(write_guest='true')
        self.client.logout()
        self.assertEqual(self.client.post(reverse('events:thread-post-create', args=[response.json()['thread_id']]),
                                         {'body': 'Allowed Guest reply'}).status_code, 200)

    def test_board_delete_retains_thread_response_policy_and_direct_access(self):
        self.client.force_login(self.owner)
        field, _ = publish_field_definition(creator=self.owner, name='Diary Number', field_type=FieldType.INTEGER)
        thread = Thread.objects.get(pk=self.post_thread(direct_field_ids=str(field.pk),
            **{f'direct_field_value_{field.key}': '5'}).json()['thread_id'])
        self.assertEqual(ThreadDirectField.objects.get(thread=thread).binding.value.value, 5)
        original_policy = list(thread.policy_conditions.values_list('kind', 'definition'))
        self.assertEqual(self.client.post(self.url('board-delete', self.diary.pk)).status_code, 200)
        self.assertFalse(Board.objects.filter(pk=self.diary.pk).exists())
        self.assertFalse(ThreadPlacement.objects.filter(thread=thread).exists())
        self.assertTrue(ThreadPost.objects.filter(thread=thread).exists())
        self.assertEqual(ThreadDirectField.objects.get(thread=thread).binding.value.value, 5)
        self.assertEqual(list(thread.policy_conditions.values_list('kind', 'definition')), original_policy)
        self.assertEqual(self.client.get(self.url('board-thread-detail', thread.pk)).status_code, 404)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse('events:thread-post-create', args=[thread.pk]), {'body': 'After deletion'}).status_code, 200)
        self.assertContains(self.client.get(self.url('thread-detail', thread.pk)), 'After deletion')

    def test_board_denial_does_not_override_thread_policy_and_does_not_leak_children(self):
        self.client.force_login(self.owner)
        thread = Thread.objects.get(pk=self.post_thread().json()['thread_id'])
        self.diary.policy_conditions.filter(capability='view').delete()
        self.client.logout()
        denied = self.client.get(self.url('board-threads', self.diary.pk))
        self.assertContains(denied, 'data-board-view-unavailable')
        self.assertNotContains(denied, 'Diary Thread')
        self.assertNotContains(denied, 'private test body')
        self.assertContains(self.client.get(self.url('board-thread-detail', thread.pk)), 'private test body')

    def test_invalid_policy_and_modules_leave_no_partial_data(self):
        self.client.force_login(self.owner)
        before = (Board.objects.count(), BoardPlacement.objects.count(), BoardPolicyCondition.objects.count())
        response = self.client.post(self.url('board-create', self.main.pk),
            {'name': 'Bad Board', 'policy_present': 'true', 'policy_view_allow_groups': 'invalid'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual((Board.objects.count(), BoardPlacement.objects.count(), BoardPolicyCondition.objects.count()), before)
        for data in ({'policy_view_allow_groups': 'invalid'}, {'direct_field_ids': 'invalid'}):
            with self.subTest(data=data):
                # Policy or module JSON rejected before any Thread/Post/Placement is saved.
                response = self.post_thread(**data)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(Thread.objects.count(), 0)
                self.assertEqual(ThreadPost.objects.count(), 0)

    def test_duplicate_submissions_do_not_cross_scopes(self):
        self.client.force_login(self.owner)
        token = str(uuid4())
        first = self.post_thread(submission_id=token)
        second = self.post_thread(submission_id=token)
        self.assertEqual(first.json()['thread_id'], second.json()['thread_id'])
        board, _ = create_board(submission_id=uuid4(), collection=self.main, name='Second')
        self.assertEqual(self.post_thread(board=board, submission_id=token).status_code, 409)
        self.assertEqual(Thread.objects.count(), 1)
        other_main = self.other.collections.get(name='Main')
        token = uuid4()
        created, _ = create_board(submission_id=token, collection=other_main, name='Other Board')
        response = self.client.post(self.url('board-create', self.main.pk), {'submission_id': str(token), 'name': 'Replay'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(created.placement.collection_id, other_main.pk)

    def test_existing_account_backfill_preserves_all_existing_collections_and_boards(self):
        User = get_user_model()
        User.objects.bulk_create([User(username='old_empty'), User(username='old_custom'), User(username='old_deleted')])
        empty, custom, deleted = (User.objects.get(username=name) for name in ('old_empty', 'old_custom', 'old_deleted'))
        collection = Collection.objects.create(account=custom, name='Existing')
        board = Board.objects.create(name='Existing Diary')
        BoardPlacement.objects.create(board=board, kind='collection', collection=collection)
        Collection.objects.create(account=deleted, name='未分類', is_uncategorized=True)
        seed = importlib.import_module('rooms.migrations.0009_initial_account_boards').initialize_existing_accounts
        historical_apps = MigrationExecutor(connection).loader.project_state([('rooms', '0008_boardpolicycondition')]).apps
        seed(historical_apps, SimpleNamespace(connection=connection))
        self.assertEqual(empty.collections.count(), 2)
        self.assertEqual(custom.collections.count(), 1)
        self.assertEqual(deleted.collections.count(), 1)
        board.refresh_from_db()
        self.assertEqual(board.name, 'Existing Diary')
        self.assertEqual(board.placement.collection_id, collection.pk)
        seeded = Board.objects.get(placement__collection__account=empty)
        self.assertEqual(seeded.policy_conditions.get(capability='create_thread').definition, {'account_id': empty.pk})
        seeded.delete()
        seed(historical_apps, SimpleNamespace(connection=connection))
        self.assertFalse(Board.objects.filter(placement__collection__account=empty).exists())
