"""Direct Map Board regressions, always run with Django's isolated SQLite test DB."""
import json
from uuid import uuid4
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from events.models import Thread, ThreadPost, ThreadPlacement
from rooms.models import Board, BoardPlacement, BoardPolicyCondition
from rooms.services import create_board, create_room


class MapBoardTests(TestCase):
    def payload(self, **values):
        return {'submission_id': str(uuid4()), 'name': 'Map Board', 'description': 'Map details',
                'latitude': '35.681236', 'longitude': '139.767125', **values}

    def create(self, **values):
        response = self.client.post(reverse('events:board-create'), self.payload(**values))
        self.assertEqual(response.status_code, 200, response.content)
        return Board.objects.get(pk=response.json()['board_id'])

    def test_guest_creation_defaults_ownerless_placement_and_retry(self):
        data = self.payload()
        first = self.client.post(reverse('events:board-create'), data)
        again = self.client.post(reverse('events:board-create'), data)
        self.assertEqual(first.json(), again.json())
        self.assertEqual(Board.objects.count(), 1)
        board = Board.objects.get()
        self.assertEqual(board.placement.kind, BoardPlacement.NII_MAP)
        self.assertIsNone(board.placement.collection_id)
        self.assertEqual(board.policy_conditions.count(), 4)
        self.assertTrue(board.evaluate_policy(self.client.get('/').wsgi_request.user, 'view').allowed)
        html = self.client.get(reverse('events:board-pane', args=[board.pk])).content.decode()
        self.assertIn('data-board-thread-create', html)
        self.assertNotIn('data-board-edit-toggle', html)
        self.assertNotIn('data-board-action-kind="delete"', html)

    def test_coordinate_and_policy_errors_are_atomic(self):
        invalid = [dict(latitude=''), dict(longitude='181'), dict(latitude='91'), dict(latitude='NaN'),
                   dict(latitude='35.1234567'), dict(policy_view_allow_groups='{}'), dict(policy_present='true', policy_view_allow_groups='{}'),
                   dict(policy_present='true', policy_view_allow_groups='[[{"kind":"field","definition":{}}]]'),
                   dict(policy_present='true', policy_view_allow_groups='[[{"kind":"default","definition":{"code":"self"}}]]')]
        for values in invalid:
            with self.subTest(values=values):
                response = self.client.post(reverse('events:board-create'), self.payload(**values))
                self.assertEqual(response.status_code, 400, response.content)
                self.assertFalse(Board.objects.exists())
                self.assertFalse(BoardPlacement.objects.exists())

    def test_four_fields_deny_view_blocks_form_and_direct_thread_post(self):
        guest = [[{'kind': 'default', 'definition': {'code': 'guest'}}]]
        board = self.create(policy_present='true', policy_view_allow_groups=json.dumps(guest),
            policy_view_deny_groups=json.dumps(guest), policy_create_thread_allow_groups=json.dumps(guest),
            policy_create_thread_deny_groups='[]')
        html = self.client.get(reverse('events:board-pane', args=[board.pk])).content.decode()
        self.assertEqual(self.client.get('/').context['board_markers'], [])
        self.assertIn('data-board-view-unavailable', html)
        self.assertNotIn('data-board-thread-create', html)
        self.assertNotIn('Map details', html)
        response = self.client.post(reverse('events:board-thread-create', args=[board.pk]), {'title': 'No', 'body': 'No'})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Thread.objects.exists())

    def test_thread_policy_controls_existing_threads_and_responses_independently(self):
        board = self.create()
        url = reverse('events:board-thread-create', args=[board.pk])
        data = {'submission_id': str(uuid4()), 'title': 'Board Thread', 'body': 'Opening',
                'view_guest': 'true', 'view_account': 'true', 'write_guest': 'true', 'write_account': 'true'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200, response.content)
        thread = Thread.objects.get(pk=response.json()['thread_id'])
        self.assertEqual(thread.placements.get().board, board)
        self.assertEqual(self.client.post(url, data).json(), response.json())
        BoardPolicyCondition.objects.filter(board=board).delete()
        detail_url = reverse('events:board-thread-detail', args=[board.pk, thread.pk])
        self.assertContains(self.client.get(detail_url), 'Opening')
        reply = self.client.post(reverse('events:thread-post-create', args=[thread.pk]), {'body': 'Response'})
        self.assertEqual(reply.status_code, 200, reply.content)
        self.assertEqual(thread.posts.count(), 2)
        self.assertEqual(self.client.post(url, {'title': 'No', 'body': 'No'}).status_code, 403)

    def test_account_creator_has_no_management_rights_and_scope_cannot_be_forged(self):
        owner = get_user_model().objects.create_user('map_creator')
        self.client.force_login(owner)
        board = self.create()
        room, _ = create_room(submission_id=uuid4(), owner=owner, name='Room', description='', latitude='35', longitude='139')
        for namespace, identifier in [('accounts', owner.username), ('rooms', room.pk)]:
            for action in ['board-edit', 'board-delete']:
                response = self.client.post(reverse(f'{namespace}:{action}', args=[identifier, board.pk]), {'name': 'Changed'})
                self.assertEqual(response.status_code, 404)
        for action in ['edit', 'delete', 'placement']:
            self.assertEqual(self.client.post(f'/boards/{board.pk}/{action}/', {}).status_code, 404)
        board.refresh_from_db()
        self.assertEqual(board.name, 'Map Board')
        collection = room.collections.get(name='Main')
        existing, _ = create_board(submission_id=uuid4(), collection=collection, name='Collection Board')
        response = self.client.post(reverse('events:board-create'), self.payload(submission_id=str(existing.submission_id)))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(existing.placement.collection_id, collection.pk)

    def test_map_search_includes_direct_board_and_never_child_thread(self):
        board = self.create(description='secret board text')
        thread = Thread.objects.create(title='Internal child')
        ThreadPost.objects.create(thread=thread, number=1, body='Only child body')
        ThreadPlacement.objects.create(thread=thread, kind='board', board=board)
        html = self.client.get('/').content.decode()
        self.assertIn(f'data-board-id="{board.pk}"', html)
        self.assertNotIn('Internal child', html)
        result = self.client.post(reverse('events:thread-search'), {'target_type': 'board', 'sort_kind': 'updated'}).json()
        self.assertEqual(result['board_ids'], [board.pk])
        self.assertEqual(result['thread_ids'], [])
        self.assertEqual(result['room_ids'], [])
        self.assertEqual(result['spot_order'], [{'kind': 'board', 'id': board.pk}])
        self.assertEqual(result['count'], 1)
        BoardPolicyCondition.objects.filter(board=board).delete()
        result = self.client.post(reverse('events:thread-search'), {'freeword_include': 'secret board text'}).json()
        self.assertEqual(result['board_ids'], [])
        result = self.client.post(reverse('events:thread-search'), {'freeword_include': 'Map Board'}).json()
        self.assertEqual(result['board_ids'], [board.pk])
