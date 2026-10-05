"""Mute intent, display filtering, and creator regressions on isolated SQLite."""
from uuid import uuid4
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import AccountMute, AccountReview
from events.models import Thread, ThreadAccessRule, ThreadPlacement, ThreadPost
from rooms.models import Board, BoardPlacement
from rooms.services import create_board, create_room


class MuteTests(TestCase):
    def setUp(self):
        self.assertEqual(settings.DATABASES['default']['ENGINE'], 'django.db.backends.sqlite3')
        User = get_user_model()
        self.viewer = User.objects.create_user('mute_viewer')
        self.target = User.objects.create_user('mute_target')
        self.other = User.objects.create_user('mute_other')
        self.target.niixy_profile.display_name = '相手'
        self.target.niixy_profile.save()
        self.url = reverse('accounts:mute-change', args=[self.target.username])
        self.client.force_login(self.viewer)

    def mute(self):
        return AccountMute.objects.create(muter=self.viewer, muted_account=self.target)

    def thread(self, creator=None, board=None):
        creator = creator or self.target
        thread = Thread.objects.create(creator=creator, title='Mute QA Thread')
        ThreadPost.objects.create(thread=thread, number=1, creator=creator, body='Opening body')
        for capability in ['view', 'write']:
            for audience in ['guest', 'account']:
                ThreadAccessRule.objects.create(thread=thread, capability=capability, audience=audience)
        ThreadPlacement.objects.create(thread=thread, kind='board' if board else 'niimap', board=board,
            latitude=None if board else '35.681236', longitude=None if board else '139.767125')
        return thread

    def room(self, owner=None):
        return create_room(submission_id=uuid4(), owner=owner or self.target, name='Mute QA Room',
            description='Room body', latitude='35.681236', longitude='139.767125')[0]

    def test_login_self_post_and_invalid_state(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.client.logout()
        self.assertEqual(self.client.post(self.url, {'enabled': 'true'}).status_code, 401)
        self.client.force_login(self.target)
        self.assertEqual(self.client.post(self.url, {'enabled': 'true'}).status_code, 403)
        self.client.force_login(self.viewer)
        for data in [{}, {'enabled': 'yes'}, {'enabled': 'toggle'}]:
            self.assertEqual(self.client.post(self.url, data).status_code, 400)
        self.assertFalse(AccountMute.objects.exists())

    def test_identity_idempotence_and_author_only_release(self):
        first = self.client.post(self.url, {'enabled': 'true', 'muter': self.other.pk, 'muted_account': self.viewer.pk})
        self.assertEqual(first.json(), {'ok': True, 'muted': True})
        mute = AccountMute.objects.get()
        self.assertEqual((mute.muter_id, mute.muted_account_id), (self.viewer.pk, self.target.pk))
        self.assertEqual(self.client.post(self.url, {'enabled': 'true'}).status_code, 200)
        self.assertEqual(AccountMute.objects.get().created_at, mute.created_at)
        self.client.force_login(self.other)
        self.client.post(self.url, {'enabled': 'false', 'mute_id': mute.pk, 'muter': self.viewer.pk})
        self.assertTrue(AccountMute.objects.filter(pk=mute.pk).exists())
        self.client.force_login(self.target)
        self.assertEqual(self.client.post(self.url, {'enabled': 'false', 'muter': self.viewer.pk}).status_code, 403)
        self.client.force_login(self.viewer)
        for _ in range(2):
            self.assertEqual(self.client.post(self.url, {'enabled': 'false'}).json(), {'ok': True, 'muted': False})
        self.assertFalse(AccountMute.objects.exists())

    def test_csrf_and_constraints(self):
        csrf = Client(enforce_csrf_checks=True); csrf.force_login(self.viewer)
        self.assertEqual(csrf.post(self.url, {'enabled': 'true'}).status_code, 403)
        csrf.get(reverse('accounts:detail', args=[self.target.username]))
        self.assertEqual(csrf.post(self.url, {'enabled': 'true'}, HTTP_X_CSRFTOKEN=csrf.cookies['csrftoken'].value).status_code, 200)
        for values in [{'muter': self.viewer, 'muted_account': self.target}, {'muter': self.viewer, 'muted_account': self.viewer}]:
            with self.assertRaises(IntegrityError), transaction.atomic():
                AccountMute.objects.create(**values)
        with self.assertRaises(ValidationError):
            AccountMute(muter=self.viewer, muted_account=self.viewer).full_clean()

    def test_review_is_independent_in_both_directions(self):
        self.mute()
        review = AccountReview.objects.create(author=self.viewer, target=self.target, sentiment='hate', body='Review body')
        self.client.post(reverse('accounts:review-delete', args=[self.target.username]), {'review_id': review.pk, 'revision': review.revision})
        self.assertTrue(AccountMute.objects.exists())
        review = AccountReview.objects.create(author=self.viewer, target=self.target, sentiment='love', body='Review body')
        self.client.post(self.url, {'enabled': 'false'})
        self.assertTrue(AccountReview.objects.filter(pk=review.pk).exists())

    def test_public_muter_count_order_pages_and_guest_self_controls(self):
        for index in range(22):
            muter = get_user_model().objects.create_user(f'muter_{index:02}')
            AccountMute.objects.create(muter=muter, muted_account=self.target)
        url = reverse('accounts:reviews', args=[self.target.username])
        response = self.client.get(url, {'review_filter': 'muter'})
        self.assertEqual(response.context['muter_count'], 22)
        self.assertEqual(len(response.context['review_page']), 8)
        self.assertEqual(response.context['review_page'][0].muter.username, 'muter_21')
        self.assertContains(response, 'Muter (22)')
        self.assertNotContains(response, 'data-review-id=')
        self.assertEqual(len(self.client.get(url, {'review_filter': 'muter', 'review_expanded': '1', 'review_page': '2'}).context['review_page']), 10)
        self.assertEqual(len(self.client.get(url, {'review_filter': 'muter', 'review_expanded': '1', 'review_page': '3'}).context['review_page']), 2)
        self.client.logout()
        response = self.client.get(url, {'review_filter': 'muter'})
        self.assertEqual(response.context['muter_count'], 22)
        self.assertFalse(response.context['own_mute'])
        self.assertContains(response, 'disabled title="ログインが必要です"')
        self.client.force_login(self.target)
        self.assertContains(self.client.get(url), '自分のAccountはMuteできません')

    def test_map_search_marker_and_direct_url_use_same_filter(self):
        hidden = self.thread(); shown = self.thread(self.other)
        room = self.room()
        board, _ = create_board(submission_id=uuid4(), name='Muted Map Board', actor=self.target,
            latitude='35.681236', longitude='139.767125')
        unknown, _ = create_board(submission_id=uuid4(), name='Unknown Board', latitude='35.681236', longitude='139.767125')
        self.mute()
        response = self.client.get('/')
        self.assertEqual([t.pk for t in response.context['threads']], [shown.pk])
        self.assertEqual([m['id'] for m in response.context['thread_markers']], [shown.pk])
        self.assertEqual(response.context['rooms'], [])
        self.assertEqual(response.context['room_markers'], [])
        self.assertEqual([b.pk for b in response.context['boards']], [unknown.pk])
        self.assertEqual([m['id'] for m in response.context['board_markers']], [unknown.pk])
        search = self.client.post(reverse('events:thread-search'), {}).json()
        self.assertEqual(search['thread_ids'], [shown.pk]); self.assertEqual(search['room_ids'], [])
        self.assertEqual(search['board_ids'], [unknown.pk]); self.assertEqual(search['count'], 2)
        direct = self.client.get('/', {'thread': hidden.pk})
        self.assertNotIn(hidden.pk, [t.pk for t in direct.context['threads']])
        self.assertIn(hidden.pk, [t.pk for t in direct.context['detail_threads']])
        self.assertContains(direct, 'ミュート中 · 一時表示')
        self.assertContains(self.client.get(reverse('events:board-pane', args=[board.pk])), 'Muted Map Board')
        self.assertEqual(self.client.get(reverse('rooms:detail', args=[room.pk])).context['room'].pk, room.pk)
        # The target's ability to view/post is unchanged by another Account's Mute.
        self.assertEqual(self.client.post(reverse('events:thread-post-create', args=[hidden.pk]), {'body': 'Reply'}).status_code, 200)
        for viewer in [self.other, self.target, None]:
            if viewer: self.client.force_login(viewer)
            else: self.client.logout()
            response = self.client.get('/')
            self.assertEqual(len(response.context['thread_markers']), 2)
            self.assertEqual(len(response.context['room_markers']), 1)
            self.assertEqual(len(response.context['board_markers']), 2)

    def test_account_board_lists_pagination_and_counts(self):
        room = self.room(self.other)
        collection = room.collections.get(name='Main')
        hidden_board, _ = create_board(submission_id=uuid4(), name='Hide board', collection=collection, actor=self.target)
        kept_board, _ = create_board(submission_id=uuid4(), name='Keep board', collection=collection, actor=self.other)
        hidden_thread = self.thread(board=kept_board)
        shown_thread = self.thread(self.other, kept_board)
        self.mute()
        response = self.client.get(reverse('rooms:boards', args=[room.pk]))
        boards = [b for c in response.context['collections'] for b in c.visible_boards]
        self.assertNotIn(hidden_board.pk, [b.pk for b in boards])
        self.assertEqual(next(b.thread_count for b in boards if b.pk == kept_board.pk), 1)
        response = self.client.get(reverse('rooms:board-threads', args=[room.pk, kept_board.pk]))
        self.assertEqual([t.pk for t in response.context['threads']], [shown_thread.pk])
        self.assertContains(self.client.get(reverse('rooms:thread-detail', args=[room.pk, hidden_thread.pk])), '一時表示')
        thread_page = self.client.get(reverse('accounts:thread-pane', args=[self.target.username]))
        self.assertEqual(thread_page.context['created_page'].paginator.count, 0)
        self.assertEqual(self.client.get(reverse('accounts:room-pane', args=[self.target.username])).context['owner_page'].paginator.count, 0)
        self.assertEqual([b.pk for c in self.client.get(reverse('accounts:boards', args=[self.target.username])).context['collections'] for b in c.visible_boards], [])
        # Filtering happens before paging, including pages filled by a muted author.
        for _ in range(12): self.thread(self.target)
        self.assertEqual(self.client.get(reverse('accounts:thread-pane', args=[self.target.username]), {'created_page': 2}).context['created_page'].paginator.count, 0)

    def test_response_placeholder_preserves_numbers_and_existing_acl(self):
        thread = self.thread(self.other)
        ThreadPost.objects.create(thread=thread, number=2, creator=self.target, body='<b>muted response</b>')
        ThreadPost.objects.create(thread=thread, number=3, creator=self.other, body='Visible response')
        self.mute()
        response = self.client.get(reverse('accounts:thread-detail', args=[self.other.username, thread.pk]))
        self.assertContains(response, 'data-thread-post-number="2"')
        self.assertContains(response, 'data-muted-response')
        self.assertContains(response, '&lt;b&gt;muted response&lt;/b&gt;')
        self.assertContains(response, 'Visible response')
        history = self.client.get(reverse('accounts:response-pane', args=[self.target.username]))
        self.assertEqual(history.context['response_page'].paginator.count, 1)
        self.assertContains(history, 'data-muted-response')
        ThreadAccessRule.objects.filter(thread=thread, capability='view').delete()
        response = self.client.get(reverse('accounts:thread-detail', args=[self.other.username, thread.pk]))
        self.assertNotContains(response, 'muted response'); self.assertNotContains(response, 'Visible response')
        self.assertEqual(self.client.post(reverse('events:thread-post-create', args=[thread.pk]), {'body': 'No'}).status_code, 403)

    def test_creator_all_new_creation_paths_and_retry(self):
        self.assertEqual(Board.objects.get(placement__collection__account=self.viewer).creator, self.viewer)
        self.viewer.save()
        self.assertEqual(Board.objects.filter(placement__collection__account=self.viewer).count(), 1)
        room = self.room()
        self.assertEqual(set(Board.objects.filter(placement__collection__room=room).values_list('creator_id', flat=True)), {self.target.pk})
        data = {'submission_id': str(uuid4()), 'name': 'Account board', 'creator': self.other.pk}
        main = self.viewer.collections.get(name='Main')
        created = self.client.post(reverse('accounts:board-create', args=[self.viewer.username, main.pk]), data)
        self.assertEqual(created.status_code, 200, created.content)
        self.assertEqual(Board.objects.get(pk=created.json()['board_id']).creator, self.viewer)
        self.assertEqual(self.client.post(reverse('accounts:board-create', args=[self.viewer.username, main.pk]), data).json(), created.json())
        self.client.force_login(self.target)
        data['submission_id'] = str(uuid4())
        created = self.client.post(reverse('rooms:board-create', args=[room.pk, room.collections.get(name='Main').pk]), data)
        self.assertEqual(Board.objects.get(pk=created.json()['board_id']).creator, self.target)
        for viewer in [self.target, None]:
            if viewer: self.client.force_login(viewer)
            else: self.client.logout()
            created = self.client.post(reverse('events:board-create'), {'submission_id': str(uuid4()), 'name': 'Map', 'latitude': '35', 'longitude': '139', 'creator': self.other.pk})
            self.assertEqual(created.status_code, 200, created.content)
            self.assertEqual(Board.objects.get(pk=created.json()['board_id']).creator, viewer)

    def test_creator_does_not_grant_management_or_recreate_defaults(self):
        board, _ = create_board(submission_id=uuid4(), name='Other creator', actor=self.other,
            collection=self.viewer.collections.get(name='Main'))
        self.client.force_login(self.other)
        for action in ['board-edit', 'board-delete']:
            self.assertEqual(self.client.post(reverse('accounts:' + action, args=[self.viewer.username, board.pk]), {'name': 'No'}).status_code, 403)
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.post(reverse('accounts:board-edit', args=[self.viewer.username, board.pk]), {'name': 'Owner edit'}).status_code, 200)
        board.refresh_from_db(); self.assertEqual(board.creator, self.other)
        diary = Board.objects.get(placement__collection__account=self.viewer, name='日記'); diary.delete()
        self.client.get(reverse('accounts:detail', args=[self.viewer.username])); self.viewer.save()
        self.assertFalse(Board.objects.filter(placement__collection__account=self.viewer, name='日記').exists())
        self.other.delete(); board.refresh_from_db(); self.assertIsNone(board.creator_id)

    def test_personalized_html_is_not_shared_cacheable(self):
        thread = self.thread(self.other); room = self.room()
        board = Board.objects.get(placement__collection__account=self.target)
        for url in ['/', reverse('accounts:detail', args=[self.target.username]), reverse('accounts:pane', args=[self.target.username]),
                reverse('accounts:reviews', args=[self.target.username]), reverse('accounts:thread-pane', args=[self.target.username]),
                reverse('accounts:response-pane', args=[self.target.username]), reverse('accounts:room-pane', args=[self.target.username]),
                reverse('accounts:boards', args=[self.target.username]), reverse('accounts:board-threads', args=[self.target.username, board.pk]),
                reverse('accounts:thread-detail', args=[self.other.username, thread.pk]), reverse('rooms:boards', args=[room.pk])]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertIn('private', response['Cache-Control']); self.assertIn('no-store', response['Cache-Control'])
