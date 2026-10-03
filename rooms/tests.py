from uuid import uuid4
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from events.models import Thread, ThreadAccessRule, ThreadPlacement, ThreadPost
from interfaces.models import FieldType, ThreadDirectField
from interfaces.services import publish_field_definition

from .models import Board, BoardPlacement, Collection, Room, RoomMembership, RoomPlacement
from .services import create_room


class RoomCreationServiceTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user('room_owner', password='eightchars')

    def create(self, submission_id=None):
        return create_room(
            submission_id=submission_id or uuid4(),
            owner=self.owner,
            name='PokeShop',
            description='ポケモン用品のお店です。',
            latitude='35.681236',
            longitude='139.767125',
        )

    def test_create_room_builds_owner_membership_main_collection_and_first_board(self):
        room, created = self.create()

        self.assertTrue(created)
        self.assertEqual(room.owner, self.owner)
        self.assertEqual(room.created_by, self.owner)
        self.assertTrue(room.has_member(self.owner))
        self.assertEqual(RoomMembership.objects.get().account, self.owner)
        self.assertEqual(RoomPlacement.objects.get().latitude, Decimal('35.681236'))
        main = Collection.objects.get()
        self.assertEqual(main.name, 'Main')
        self.assertEqual(main.room, room)
        self.assertTrue(main.is_main)
        board = Board.objects.get()
        self.assertEqual(board.name, '最初のBoard')
        self.assertEqual(board.owner_room, room)
        self.assertEqual(board.created_by, self.owner)
        self.assertEqual(board.placement.kind, BoardPlacement.COLLECTION)
        self.assertEqual(board.placement.collection, main)

    def test_duplicate_submission_returns_existing_room_without_duplicates(self):
        submission_id = uuid4()

        first, first_created = self.create(submission_id)
        second, second_created = self.create(submission_id)

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(second, first)
        self.assertEqual(Room.objects.count(), 1)
        self.assertEqual(RoomMembership.objects.count(), 1)
        self.assertEqual(Collection.objects.count(), 1)
        self.assertEqual(Board.objects.count(), 1)
        self.assertEqual(BoardPlacement.objects.count(), 1)
        self.assertEqual(RoomPlacement.objects.count(), 1)

    def test_room_membership_is_unique_per_account(self):
        room, _ = self.create()

        with self.assertRaises(IntegrityError), transaction.atomic():
            RoomMembership.objects.create(room=room, account=self.owner)


class PlacementConstraintTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user('placement_owner', password='eightchars')
        self.room, _ = create_room(
            submission_id=uuid4(),
            owner=self.owner,
            name='Placement Room',
            description='',
            latitude='35.0',
            longitude='139.0',
        )
        self.board = Board.objects.get(owner_room=self.room)

    def test_board_thread_placement_uses_board_without_coordinates(self):
        thread = Thread.objects.create(creator=self.owner, title='Room Thread')

        placement = ThreadPlacement.objects.create(
            thread=thread,
            kind=ThreadPlacement.BOARD,
            board=self.board,
        )

        self.assertEqual(placement.board, self.board)
        self.assertIsNone(placement.latitude)
        self.assertIsNone(placement.longitude)
        self.assertTrue(placement.is_primary)

    def test_thread_cannot_have_two_primary_placements(self):
        thread = Thread.objects.create(creator=self.owner, title='Single Primary')
        ThreadPlacement.objects.create(
            thread=thread,
            kind=ThreadPlacement.BOARD,
            board=self.board,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            ThreadPlacement.objects.create(
                thread=thread,
                latitude='35.0',
                longitude='139.0',
            )


class RoomViewTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user('room_view_owner', password='eightchars')
        self.member = get_user_model().objects.create_user('room_member', password='eightchars')
        self.outsider = get_user_model().objects.create_user('room_outsider', password='eightchars')
        self.room, _ = create_room(
            submission_id=uuid4(), owner=self.owner, name='View Room', description='Roomの説明',
            latitude='35.0', longitude='139.0',
        )
        self.board = Board.objects.get(owner_room=self.room)

    def test_logged_in_account_creates_room_and_initial_structure(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('rooms:create'), {
            'submission_id': str(uuid4()), 'name': 'New Room', 'description': '新しいRoom',
            'latitude': '35.6', 'longitude': '139.7',
        })

        self.assertEqual(response.status_code, 200)
        room = Room.objects.get(name='New Room')
        self.assertEqual(response.json()['redirect_url'], reverse('rooms:detail', args=[room.pk]))
        self.assertTrue(room.has_member(self.member))
        self.assertTrue(room.collections.get(is_main=True).board_placements.filter(board__name='最初のBoard').exists())

    def test_guest_cannot_create_or_join_room(self):
        create_response = self.client.post(reverse('rooms:create'), {
            'submission_id': str(uuid4()), 'name': 'Guest Room',
            'latitude': '35.6', 'longitude': '139.7',
        })
        join_response = self.client.post(reverse('rooms:join', args=[self.room.pk]))

        self.assertEqual(create_response.status_code, 401)
        self.assertEqual(join_response.status_code, 401)

    def test_account_can_join_and_leave_but_owner_cannot_leave(self):
        self.client.force_login(self.member)
        self.assertEqual(self.client.post(reverse('rooms:join', args=[self.room.pk])).status_code, 200)
        self.assertTrue(self.room.has_member(self.member))
        self.assertEqual(self.client.post(reverse('rooms:leave', args=[self.room.pk])).status_code, 200)
        self.assertFalse(self.room.has_member(self.member))

        self.client.force_login(self.owner)
        owner_response = self.client.post(reverse('rooms:leave', args=[self.room.pk]))
        self.assertEqual(owner_response.status_code, 400)
        self.assertTrue(self.room.has_member(self.owner))

    def test_only_owner_can_edit_room(self):
        self.client.force_login(self.outsider)
        denied = self.client.post(reverse('rooms:edit', args=[self.room.pk]), {'name': 'Denied', 'description': ''})
        self.client.force_login(self.owner)
        allowed = self.client.post(reverse('rooms:edit', args=[self.room.pk]), {
            'name': 'Renamed Room', 'description': '更新済み',
            'latitude': '34.700000', 'longitude': '135.500000',
        })

        self.assertEqual(denied.status_code, 403)
        self.assertEqual(allowed.status_code, 200)
        self.room.refresh_from_db()
        self.assertEqual(self.room.name, 'Renamed Room')
        self.room.placement.refresh_from_db()
        self.assertEqual(self.room.placement.latitude, Decimal('34.700000'))

    def test_member_creates_board_thread_and_outsider_cannot(self):
        url = reverse('rooms:board-thread-create', args=[self.room.pk, self.board.pk])
        payload = {'submission_id': str(uuid4()), 'title': 'Room Thread', 'body': '本文'}
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.post(url, payload).status_code, 403)

        self.client.force_login(self.owner)
        response = self.client.post(url, payload)

        self.assertEqual(response.status_code, 200)
        thread = Thread.objects.get(title='Room Thread')
        placement = thread.placements.get()
        self.assertEqual(placement.kind, ThreadPlacement.BOARD)
        self.assertEqual(placement.board, self.board)
        self.assertEqual(thread.posts.get().body, '本文')

    def test_board_thread_keeps_direct_field_and_policy_features(self):
        definition, _ = publish_field_definition(
            creator=self.owner,
            name='Roomの募集人数',
            field_type=FieldType.INTEGER,
        )
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse('rooms:board-thread-create', args=[self.room.pk, self.board.pk]),
            {
                'submission_id': str(uuid4()), 'title': 'Field付き', 'body': '本文',
                'direct_field_ids': str(definition.pk),
                f'direct_field_value_{definition.key}': '5',
                'view_guest': 'true', 'view_account': 'true', 'write_account': 'true',
            },
        )

        self.assertEqual(response.status_code, 200)
        thread = Thread.objects.get(title='Field付き')
        self.assertEqual(ThreadDirectField.objects.get(thread=thread).binding.value.value, 5)
        self.assertEqual(thread.access_rules.count(), 3)

    def test_member_board_form_exposes_existing_thread_features(self):
        self.client.force_login(self.owner)

        page_response = self.client.get(reverse('rooms:detail', args=[self.room.pk]))
        pane_response = self.client.get(reverse('rooms:board-threads', args=[self.room.pk, self.board.pk]))

        self.assertContains(page_response, 'room-thread-field-catalog')
        self.assertContains(page_response, 'room-thread-interface-catalog')
        self.assertContains(pane_response, 'data-room-direct-fields')
        self.assertContains(pane_response, 'data-room-thread-interfaces')
        self.assertContains(pane_response, 'ui-control-accordion')
        self.assertContains(pane_response, 'name="view_guest"')
        self.assertContains(pane_response, 'name="write_account"')

    def test_room_overview_uses_compact_controls_without_description(self):
        response = self.client.get(reverse('rooms:detail', args=[self.room.pk]))
        board_response = self.client.get(reverse('rooms:boards', args=[self.room.pk]))

        self.assertContains(response, 'RoomIF')
        self.assertContains(response, 'メンバー 1')
        self.assertContains(response, '>Board<')
        self.assertContains(response, 'Timeline')
        self.assertContains(response, 'Policy')
        self.assertNotContains(response, 'もっと見る')
        self.assertNotContains(response, '最初のBoard')
        self.assertNotContains(response, 'Roomの説明')
        self.assertNotContains(response, 'Owner:')
        self.assertContains(response, 'room-thread-list-pane')
        self.assertContains(board_response, '最初のBoard')
        self.assertContains(board_response, 'data-ui-tab=', count=1)
        self.assertContains(board_response, '>Main<')

    def test_room_pane_exposes_workspace_endpoints(self):
        response = self.client.get(reverse('rooms:pane', args=[self.room.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-room-fragment')
        self.assertContains(response, reverse('rooms:members', args=[self.room.pk]))
        self.assertContains(response, reverse('rooms:boards', args=[self.room.pk]))
        self.assertContains(response, 'ui-placement-row')

    def test_only_room_member_can_reply_to_board_thread(self):
        thread = Thread.objects.create(creator=self.owner, title='Membership Gate')
        ThreadPost.objects.create(thread=thread, number=1, creator=self.owner, body='本文')
        ThreadPlacement.objects.create(thread=thread, kind=ThreadPlacement.BOARD, board=self.board)
        ThreadAccessRule.objects.create(thread=thread, capability='view', audience='account')
        ThreadAccessRule.objects.create(thread=thread, capability='write', audience='account')
        url = reverse('events:thread-post-create', args=[thread.pk])

        self.client.force_login(self.outsider)
        denied = self.client.post(url, {'body': '不可', 'submission_id': str(uuid4())})
        self.client.force_login(self.owner)
        allowed = self.client.post(url, {'body': '可能', 'submission_id': str(uuid4())})

        self.assertEqual(denied.status_code, 403)
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(thread.posts.count(), 2)

    def test_board_thread_uses_shared_detail_and_membership_from_account_page(self):
        thread = Thread.objects.create(creator=self.owner, title='Shared Detail')
        ThreadPost.objects.create(thread=thread, number=1, creator=self.owner, body='本文')
        ThreadPlacement.objects.create(thread=thread, kind=ThreadPlacement.BOARD, board=self.board)
        ThreadAccessRule.objects.create(thread=thread, capability='view', audience='account')
        ThreadAccessRule.objects.create(thread=thread, capability='write', audience='account')
        account_url = reverse('accounts:thread-detail', args=[self.owner.username, thread.pk])
        room_url = reverse('rooms:thread-detail', args=[self.room.pk, thread.pk])

        self.client.force_login(self.outsider)
        outsider_response = self.client.get(account_url)

        self.assertContains(outsider_response, 'class="thread-detail"')
        self.assertContains(outsider_response, f'{self.room.name} / {self.board.name}')
        self.assertNotContains(outsider_response, 'class="thread-reply-form"')

        RoomMembership.objects.create(room=self.room, account=self.member)
        self.client.force_login(self.member)
        account_response = self.client.get(account_url)
        room_response = self.client.get(room_url)

        self.assertContains(account_response, 'class="thread-reply-form"')
        self.assertContains(room_response, 'class="thread-reply-form"')
        self.assertContains(account_response, 'data-thread-id=', count=1)
        self.assertContains(room_response, 'data-thread-id=', count=1)

    def test_niimap_lists_room_but_not_room_internal_thread(self):
        thread = Thread.objects.create(creator=self.owner, title='Room Only Thread')
        ThreadPost.objects.create(thread=thread, number=1, creator=self.owner, body='本文')
        ThreadPlacement.objects.create(thread=thread, kind=ThreadPlacement.BOARD, board=self.board)

        response = self.client.get(reverse('events:map'))

        self.assertContains(response, 'View Room')
        self.assertNotContains(response, 'Room Only Thread')

    def test_niimap_search_filters_rooms_without_mixing_internal_threads(self):
        thread = Thread.objects.create(creator=self.owner, title='Needle only inside Board')
        ThreadPost.objects.create(thread=thread, number=1, creator=self.owner, body='本文')
        ThreadPlacement.objects.create(thread=thread, kind=ThreadPlacement.BOARD, board=self.board)
        payload = {
            'sort_kind': 'updated', 'sort_direction': 'desc', 'target_type': 'room',
            'freeword_include': 'View Room', 'creator_include_groups': '[]',
            'creator_exclude_groups': '[]', 'policy_conditions': '[]',
            'field_conditions': '[]', 'interface_conditions': '[]',
        }

        response = self.client.post(reverse('events:thread-search'), payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['room_ids'], [self.room.pk])
        self.assertEqual(response.json()['thread_ids'], [])

        payload['freeword_include'] = 'Needle'
        hidden_response = self.client.post(reverse('events:thread-search'), payload)
        self.assertEqual(hidden_response.json()['room_ids'], [])
