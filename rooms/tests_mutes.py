"""Room intent, original placement, references, existing ACL and filter routes."""
from uuid import uuid4
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse
from accounts.content_lists import route
from accounts.models import AccountMute
from accounts.mutes import filter_muted
from events.models import Thread, ThreadAccessRule, ThreadPlacement, ThreadPost
from rooms.models import Board, BoardListReference, BoardRating, Collection, Room, RoomMute, RoomReview
from rooms.mutes import muted_thread_ids
from rooms.services import create_room


class RoomMuteTests(TestCase):
    def setUp(self):
        self.assertEqual(settings.DATABASES['default']['ENGINE'], 'django.db.backends.sqlite3')
        User = get_user_model()
        self.viewer = User.objects.create_user('room_mute_viewer')
        self.owner = User.objects.create_user('room_mute_owner')
        self.other = User.objects.create_user('room_mute_other')
        self.room = self.make_room('Muted Room')
        self.other_room = self.make_room('Same Owner Other Room')
        self.board = Board.objects.get(placement__collection__room=self.room, name='掲示板')
        self.other_board = Board.objects.get(placement__collection__room=self.other_room, name='掲示板')
        self.thread = self.make_thread(self.board)
        self.other_thread = self.make_thread(self.other_board)
        self.map_thread = self.make_thread()
        self.url = reverse('rooms:mute-change', args=[self.room.pk])
        self.client.force_login(self.viewer)

    def make_room(self, name):
        return create_room(submission_id=uuid4(), owner=self.owner, name=name,
                           description='SQLite only', latitude='35', longitude='139')[0]

    def make_thread(self, board=None):
        thread = Thread.objects.create(creator=self.other, title='Room Filter Thread')
        ThreadPost.objects.create(thread=thread, creator=self.other, number=1, body='Opening body')
        ThreadPost.objects.create(thread=thread, creator=self.other, number=2, body='Response remains directly readable')
        ThreadPlacement.objects.create(thread=thread, kind='board' if board else 'niimap', board=board,
            latitude=None if board else '35', longitude=None if board else '139')
        for capability in ['view', 'write']:
            for audience in ['guest', 'account']:
                ThreadAccessRule.objects.create(thread=thread, capability=capability, audience=audience)
        return thread

    def mute(self):
        return RoomMute.objects.create(muter=self.viewer, room=self.room)

    def test_auth_csrf_state_identity_idempotence_and_author_only_release(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.client.logout()
        self.assertEqual(self.client.post(self.url, {'enabled': 'true'}).status_code, 401)
        self.client.force_login(self.viewer)
        for data in [{}, {'enabled': 'yes'}, {'enabled': 'toggle'}]:
            self.assertEqual(self.client.post(self.url, data).status_code, 400)
        secure = Client(enforce_csrf_checks=True); secure.force_login(self.viewer)
        self.assertEqual(secure.post(self.url, {'enabled': 'true'}).status_code, 403)
        secure.get(reverse('rooms:detail', args=[self.room.pk]))
        self.assertEqual(secure.post(self.url, {'enabled': 'true', 'muter': self.other.pk, 'room': self.other_room.pk}, HTTP_X_CSRFTOKEN=secure.cookies['csrftoken'].value).status_code, 200)
        row = RoomMute.objects.get()
        self.assertEqual((row.muter_id, row.room_id), (self.viewer.pk, self.room.pk))
        self.client.post(self.url, {'enabled': 'true'})
        self.assertEqual(RoomMute.objects.get().created_at, row.created_at)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(self.url, {'enabled': 'true'}).status_code, 200)
        self.client.post(self.url, {'enabled': 'false', 'muter': self.viewer.pk, 'mute_id': row.pk})
        self.assertTrue(RoomMute.objects.filter(pk=row.pk).exists())
        self.client.force_login(self.viewer)
        for _ in range(2):
            self.assertEqual(self.client.post(self.url, {'enabled': 'false'}).json(), {'ok': True, 'muted': False})
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.mute(); self.mute()

    def test_mute_review_and_owner_account_are_independent(self):
        self.mute()
        review = RoomReview.objects.create(author=self.viewer, target=self.room, sentiment='love', body='Review body')
        self.client.post(reverse('rooms:review-delete', args=[self.room.pk]), {'review_id': review.pk, 'revision': 1})
        self.assertTrue(RoomMute.objects.exists())
        review = RoomReview.objects.create(author=self.viewer, target=self.room, sentiment='hate', body='Independent')
        self.client.post(self.url, {'enabled': 'false'})
        self.assertTrue(RoomReview.objects.filter(pk=review.pk).exists())
        self.assertFalse(AccountMute.objects.exists())

    def test_public_muters_count_order_pages_and_viewer_filter_does_not_hide_reviews(self):
        rows = []
        for index in range(22):
            author = get_user_model().objects.create_user(f'room_muter_{index}')
            rows.append(RoomMute.objects.create(muter=author, room=self.room))
        AccountMute.objects.create(muter=self.viewer, muted_account=rows[-1].muter)
        self.client.logout()
        url = reverse('rooms:reviews', args=[self.room.pk])
        page = self.client.get(url, {'review_filter': 'muter'})
        self.assertEqual(page.context['muter_count'], 22)
        self.assertEqual(len(page.context['review_page']), 8)
        self.assertEqual(page.context['review_page'][0].pk, rows[-1].pk)
        self.assertContains(page, 'data-review-kind="room"')
        self.assertContains(page, 'Muter (22)')
        self.assertContains(page, 'disabled title="ログインが必要です"')
        self.assertEqual(len(self.client.get(url, {'review_filter': 'muter', 'review_expanded': '1', 'review_page': '3'}).context['review_page']), 2)
        self.client.force_login(self.viewer)
        page = self.client.get(url, {'review_filter': 'muter'})
        self.assertContains(page, rows[-1].muter.username)
        self.assertIn('no-store', page.headers['Cache-Control'])

    def test_original_room_filter_composes_account_mute_and_leaves_guest_and_other_rooms(self):
        self.mute()
        self.assertEqual(list(filter_muted(Room.objects.all(), self.viewer, 'owner_id')), [self.other_room])
        self.assertFalse(filter_muted(Board.objects.filter(pk=self.board.pk), self.viewer).exists())
        self.assertEqual(set(filter_muted(Thread.objects.all(), self.viewer).values_list('pk', flat=True)), {self.other_thread.pk, self.map_thread.pk})
        self.assertTrue(filter_muted(Thread.objects.filter(pk=self.thread.pk), AnonymousUser()).exists())
        self.assertTrue(filter_muted(Thread.objects.filter(pk=self.thread.pk), self.owner).exists())
        AccountMute.objects.create(muter=self.viewer, muted_account=self.other)
        self.assertFalse(filter_muted(Thread.objects.all(), self.viewer).exists())
        # RoomMute does not mute the Owner Account or other Room by that Owner.
        self.assertTrue(filter_muted(Room.objects.filter(pk=self.other_room.pk), self.viewer, 'owner_id').exists())

    def test_all_existing_list_search_marker_paths_and_response_boundary(self):
        self.mute()
        pane = self.client.get(reverse('accounts:room-pane', args=[self.owner.username]))
        self.assertNotContains(pane, f'data-account-room-detail="{self.room.pk}"')
        self.assertContains(pane, f'data-account-room-detail="{self.other_room.pk}"')
        board_list = self.client.get(reverse('rooms:boards', args=[self.room.pk]))
        self.assertFalse(any(collection.visible_boards for collection in board_list.context['collections']))
        threads = self.client.get(reverse('accounts:thread-pane', args=[self.other.username]))
        self.assertNotIn(self.thread.pk, [row.pk for row in threads.context['created_page']])
        threads = self.client.get(reverse('rooms:board-threads', args=[self.room.pk, self.board.pk]))
        self.assertEqual(threads.context['threads'], [])
        map_page = self.client.get(reverse('events:map'))
        self.assertNotIn(self.room.pk, [row.pk for row in map_page.context['rooms']])
        self.assertIn(self.other_room.pk, [row.pk for row in map_page.context['rooms']])
        search = self.client.post(reverse('events:thread-search'), {'target_type': 'room'})
        self.assertEqual(search.json()['room_ids'], [self.other_room.pk])
        search = self.client.get(reverse('accounts:account-condition-room-search'))
        self.assertEqual({row['id'] for row in search.json()['rooms']}, {self.other_room.pk})
        # Existing search stays NiiMap-only, without adding Room Thread search.
        search = self.client.post(reverse('events:thread-search'), {'target_type': 'thread'})
        self.assertEqual(search.json()['thread_ids'], [self.map_thread.pk])
        # Response history and direct thread body remain unchanged by RoomMute.
        response = self.client.get(reverse('accounts:response-pane', args=[self.other.username]))
        self.assertIn(self.thread.pk, [row.thread_id for row in response.context['response_page']])
        direct = self.client.get(reverse('rooms:thread-detail', args=[self.room.pk, self.thread.pk]))
        self.assertContains(direct, 'Response remains directly readable')

    def test_original_placement_overrides_reference_lists_and_secondary_placements(self):
        self.mute()
        external = Board.objects.get(placement__collection__account=self.other)
        account_list = self.viewer.collections.get(name='Main')
        BoardListReference.objects.create(board_list=account_list, target=self.board)
        BoardListReference.objects.create(board_list=account_list, target=external)
        # A foreign Board referenced in the muted Room never becomes its child.
        BoardListReference.objects.create(board_list=self.room.collections.get(name='Main'), target=external)
        BoardRating.objects.create(author=self.viewer, target=self.board, sentiment='fav')
        BoardRating.objects.create(author=self.viewer, target=external, sentiment='bad')
        self.assertTrue(filter_muted(Board.objects.filter(pk=external.pk), self.viewer).exists())
        page = self.client.get(route('board', 'list-detail', account_list.pk))
        self.assertEqual([row.target_id for row in page.context['summary_page']], [external.pk])
        page = self.client.get(reverse('accounts:boards', args=[self.viewer.username]))
        self.assertEqual(page.context['rating_boards']['fav'], [])
        self.assertEqual(len(page.context['rating_boards']['bad']), 1)
        self.assertTrue(any(collection.reference_summaries for collection in page.context['collections']))
        # A secondary reference/placement does not change original Room ownership.
        ThreadPlacement.objects.create(thread=self.map_thread, kind='board', board=self.board, is_primary=False)
        ThreadPlacement.objects.create(thread=self.thread, kind='board', board=external, is_primary=False)
        self.assertEqual(set(muted_thread_ids(self.viewer)), {self.thread.pk})
        self.assertTrue(filter_muted(Thread.objects.filter(pk=self.map_thread.pk), self.viewer).exists())
        page = self.client.get(reverse('accounts:boards', args=[self.other.username]))
        visible = [board for collection in page.context['collections'] for board in collection.visible_boards]
        self.assertEqual(next(board.thread_count for board in visible if board.pk == external.pk), 0)
        # Direct reference routes still use original ACL and permit readable content.
        self.assertEqual(self.client.get(route('board', 'pane', self.board.pk)).status_code, 200)
        self.assertEqual(self.client.get(reverse('rooms:detail', args=[self.room.pk])).status_code, 200)

    def test_account_room_love_hate_tabs_sort_pages_and_viewer_filter(self):
        RoomReview.objects.create(author=self.other, target=self.room, sentiment='love', body='Other Love')
        RoomReview.objects.create(author=self.viewer, target=self.other_room, sentiment='hate', body='Viewer Hate')
        url = reverse('accounts:room-pane', args=[self.other.username])
        page = self.client.get(url)
        self.assertEqual([row.pk for row in page.context['love_page']], [self.room.pk])
        self.assertEqual(len(page.context['hate_page']), 0)
        self.assertEqual([tab['kind'] for tab in page.context['room_tabs']], ['owner', 'member', 'love', 'hate'])
        self.mute()
        self.assertEqual(len(self.client.get(url).context['love_page']), 0)
        self.client.logout()
        self.assertEqual(len(self.client.get(url).context['love_page']), 1)
        for index in range(21):
            room = self.make_room(f'Love page {index}')
            RoomReview.objects.create(author=self.other, target=room, sentiment='love', body='Review')
        page = self.client.get(url, {'room_tab': 'love', 'love_page': '2'})
        self.assertEqual(page.context['room_tab'], 'love')
        self.assertEqual(len(page.context['love_page']), 2)
        self.assertContains(page, f'{url}?room_tab=love&amp;love_page=1')
        self.assertIn('no-store', page.headers['Cache-Control'])
