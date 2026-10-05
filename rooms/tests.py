import json
from uuid import uuid4
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from events.models import Thread, ThreadAccessRule, ThreadPlacement, ThreadPost
from interfaces.models import FieldType, ThreadDirectField
from interfaces.services import publish_field_definition

from .models import Board, BoardPlacement, BoardPolicyCondition, Collection, Room, RoomMembership, RoomPlacement
from .services import create_board, create_room


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
        main = Collection.objects.get(name='Main')
        uncategorized = Collection.objects.get(is_uncategorized=True)
        self.assertEqual(main.name, 'Main')
        self.assertEqual(main.room, room)
        self.assertFalse(main.is_uncategorized)
        self.assertEqual(uncategorized.name, '未分類')
        self.assertEqual(uncategorized.room, room)
        board = Board.objects.get()
        self.assertEqual(board.name, '最初のBoard')
        self.assertEqual(board.placement.kind, BoardPlacement.COLLECTION)
        self.assertEqual(board.placement.collection, main)
        self.assertEqual(board.policy_conditions.count(), 3)
        self.assertTrue(board.evaluate_policy(self.owner, BoardPolicyCondition.VIEW).allowed)
        self.assertTrue(board.evaluate_policy(self.owner, BoardPolicyCondition.CREATE_THREAD).allowed)

    def test_duplicate_submission_returns_existing_room_without_duplicates(self):
        submission_id = uuid4()

        first, first_created = self.create(submission_id)
        second, second_created = self.create(submission_id)

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(second, first)
        self.assertEqual(Room.objects.count(), 1)
        self.assertEqual(RoomMembership.objects.count(), 1)
        self.assertEqual(Collection.objects.count(), 2)
        self.assertEqual(Board.objects.count(), 1)
        self.assertEqual(BoardPlacement.objects.count(), 1)
        self.assertEqual(RoomPlacement.objects.count(), 1)
        self.assertEqual(BoardPolicyCondition.objects.count(), 3)

    def test_room_membership_is_unique_per_account(self):
        room, _ = self.create()

        with self.assertRaises(IntegrityError), transaction.atomic():
            RoomMembership.objects.create(room=room, account=self.owner)

    def test_create_board_is_idempotent_and_uses_main_collection(self):
        room, _ = self.create()
        submission_id = uuid4()
        main = room.collections.get(name='Main')

        first, first_created = create_board(
            submission_id=submission_id, collection=main, name='お知らせ',
        )
        second, second_created = create_board(
            submission_id=submission_id, collection=main, name='重複送信',
        )

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first, second)
        self.assertEqual(second.name, 'お知らせ')
        self.assertFalse(second.placement.collection.is_uncategorized)
        self.assertEqual(Board.objects.filter(placement__collection__room=room).count(), 2)
        self.assertEqual(second.policy_conditions.count(), 3)


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
        self.board = Board.objects.get(placement__collection__room=self.room)

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
        self.board = Board.objects.get(placement__collection__room=self.room)
        self.main = self.board.placement.collection
        self.uncategorized = self.room.collections.get(is_uncategorized=True)

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
        self.assertTrue(room.collections.get(name='Main').board_placements.filter(board__name='最初のBoard').exists())

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

    def test_room_participation_controls_match_account_state(self):
        guest_response = self.client.get(reverse('rooms:detail', args=[self.room.pk]))

        self.client.force_login(self.owner)
        owner_response = self.client.get(reverse('rooms:detail', args=[self.room.pk]))

        RoomMembership.objects.create(room=self.room, account=self.member)
        self.client.force_login(self.member)
        member_response = self.client.get(reverse('rooms:detail', args=[self.room.pk]))

        self.client.force_login(self.outsider)
        outsider_response = self.client.get(reverse('rooms:detail', args=[self.room.pk]))

        self.assertContains(guest_response, '>参加不可<')
        self.assertContains(guest_response, 'data-explanation-target="[data-room-participation-dialog]"')
        self.assertContains(guest_response, 'class="ui-dialog room-participation-dialog"')
        self.assertContains(guest_response, 'GuestはRoomに参加できません。参加状況を保持するAccountがないためです。')
        self.assertContains(guest_response, f'<h3>{self.room.name}のPolicy</h3>')
        self.assertContains(guest_response, 'Room独自の参加条件はありません。')
        self.assertContains(owner_response, 'disabled>Owner</button>')
        self.assertNotContains(owner_response, '>参加中<')
        self.assertContains(member_response, 'data-pending-label="退会中...">退会</button>')
        self.assertContains(outsider_response, 'data-pending-label="参加中...">参加</button>')

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

    def test_only_owner_can_create_edit_and_delete_board(self):
        create_url = reverse('rooms:board-create', args=[self.room.pk, self.main.pk])
        submission_id = str(uuid4())
        self.client.force_login(self.outsider)
        denied = self.client.post(create_url, {'submission_id': submission_id, 'name': 'Denied'})

        self.client.force_login(self.owner)
        created = self.client.post(create_url, {'submission_id': submission_id, 'name': 'お知らせ'})
        duplicate = self.client.post(create_url, {'submission_id': submission_id, 'name': '重複'})
        board = Board.objects.get(name='お知らせ')
        edited = self.client.post(
            reverse('rooms:board-edit', args=[self.room.pk, board.pk]),
            {'name': '更新済みBoard', 'description': 'Boardの詳細'},
        )
        board.refresh_from_db()
        self.assertEqual(board.name, '更新済みBoard')
        self.assertEqual(board.description, 'Boardの詳細')
        deleted = self.client.post(reverse('rooms:board-delete', args=[self.room.pk, board.pk]))

        self.assertEqual(denied.status_code, 403)
        self.assertEqual(created.status_code, 200)
        self.assertEqual(duplicate.json()['board_id'], board.pk)
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(deleted.json()['redirect_url'], f'{reverse("rooms:detail", args=[self.room.pk])}?boards=1')
        self.assertFalse(Board.objects.filter(pk=board.pk).exists())

    def test_owner_manages_collections_and_deleted_collection_moves_boards(self):
        create_url = reverse('rooms:collection-create', args=[self.room.pk])
        self.client.force_login(self.outsider)
        denied = self.client.post(create_url, {'name': 'Denied'})

        self.client.force_login(self.owner)
        created = self.client.post(create_url, {'name': '交流用'})
        collection = self.room.collections.get(name='交流用')
        list_response = self.client.get(reverse('rooms:boards', args=[self.room.pk]))
        list_html = list_response.content.decode()
        board_response = self.client.post(
            reverse('rooms:board-create', args=[self.room.pk, collection.pk]),
            {'submission_id': str(uuid4()), 'name': '会員Board'},
        )
        board = Board.objects.get(name='会員Board')
        edited = self.client.post(
            reverse('rooms:collection-edit', args=[self.room.pk, collection.pk]),
            {'name': '交流'},
        )
        deleted = self.client.post(
            reverse('rooms:collection-delete', args=[self.room.pk, collection.pk]),
        )

        self.assertEqual(denied.status_code, 403)
        self.assertEqual(created.status_code, 200)
        self.assertLess(list_html.index('>Main</button>'), list_html.index('>交流用</button>'))
        self.assertLess(list_html.index('>交流用</button>'), list_html.index('>未分類</button>'))
        self.assertLess(list_html.index('>未分類</button>'), list_html.index('>管理</button>'))
        self.assertEqual(board_response.status_code, 200)
        self.assertEqual(edited.status_code, 200)
        self.assertFalse(Collection.objects.filter(pk=collection.pk).exists())
        uncategorized = self.room.collections.get(is_uncategorized=True)
        board.placement.refresh_from_db()
        self.assertEqual(board.placement.collection, uncategorized)
        self.assertEqual(
            deleted.json()['redirect_url'],
            f'{reverse("rooms:detail", args=[self.room.pk])}?boards=1&collection={uncategorized.pk}',
        )

    def test_uncategorized_collection_cannot_be_edited_or_deleted(self):
        collection = self.uncategorized
        self.client.force_login(self.owner)

        edited = self.client.post(
            reverse('rooms:collection-edit', args=[self.room.pk, collection.pk]),
            {'name': 'Renamed'},
        )
        deleted = self.client.post(
            reverse('rooms:collection-delete', args=[self.room.pk, collection.pk]),
        )

        self.assertEqual(edited.status_code, 400)
        self.assertEqual(deleted.status_code, 400)
        self.assertTrue(Collection.objects.filter(pk=collection.pk).exists())

    def test_board_list_has_create_action_without_status_tabs(self):
        self.client.force_login(self.owner)
        owner_response = self.client.get(reverse('rooms:boards', args=[self.room.pk]))
        self.client.force_login(self.member)
        member_response = self.client.get(reverse('rooms:boards', args=[self.room.pk]))

        self.assertContains(owner_response, reverse('rooms:collection-create', args=[self.room.pk]))
        self.assertContains(owner_response, reverse('rooms:collection-edit', args=[self.room.pk, self.main.pk]))
        self.assertContains(owner_response, reverse('rooms:board-create', args=[self.room.pk, self.main.pk]))
        self.assertContains(owner_response, reverse('rooms:board-create', args=[self.room.pk, self.uncategorized.pk]))
        self.assertContains(owner_response, 'data-collection-information-toggle', count=2)
        self.assertContains(owner_response, 'data-collection-create-toggle', count=2)
        self.assertContains(owner_response, 'data-collection-information-window', count=2)
        self.assertContains(owner_response, 'data-collection-create-window', count=2)
        self.assertContains(owner_response, 'data-collection-edit-toggle', count=1)
        self.assertContains(owner_response, f'<dd>{self.main.name}</dd>')
        self.assertContains(owner_response, '<dt>Board数</dt><dd>1</dd>')
        owner_html = owner_response.content.decode()
        self.assertLess(owner_html.index('room-board-create'), owner_html.index(f'data-open-board="{self.board.pk}"'))
        self.assertLess(owner_html.index('>Main</button>'), owner_html.index('>未分類</button>'))
        self.assertLess(owner_html.index('>未分類</button>'), owner_html.index('>管理</button>'))
        self.assertLess(owner_html.index('data-ui-tab-panel="collection-management"'), owner_html.index('room-collection-create'))
        self.assertNotContains(owner_response, 'data-board-status-tab')
        self.assertNotContains(owner_response, '削除済み')
        self.assertContains(owner_response, f'{self.board.name} (0)')
        self.assertContains(owner_response, f'data-board-title="{self.board.name}"')
        self.assertContains(owner_response, 'data-summary-kind="board"')
        self.assertNotContains(member_response, reverse('rooms:collection-create', args=[self.room.pk]))
        self.assertNotContains(member_response, reverse('rooms:board-create', args=[self.room.pk, self.main.pk]))
        self.assertContains(member_response, 'data-collection-information-toggle', count=2)
        self.assertNotContains(member_response, 'data-collection-create-toggle')
        self.assertNotContains(member_response, 'data-collection-edit-toggle')
        self.assertNotContains(member_response, '>管理</button>')

    def test_board_information_and_edit_actions_are_exposed_below_header(self):
        self.client.force_login(self.owner)

        room_response = self.client.get(reverse('rooms:detail', args=[self.room.pk]))
        board_response = self.client.get(reverse('rooms:board-threads', args=[self.room.pk, self.board.pk]))
        self.client.force_login(self.member)
        member_response = self.client.get(reverse('rooms:board-threads', args=[self.room.pk, self.board.pk]))

        self.assertNotContains(room_response, 'id="edit-room-board"')
        self.assertContains(board_response, 'data-board-manageable="true"')
        self.assertContains(board_response, 'data-board-information-toggle')
        self.assertContains(board_response, 'data-board-create-toggle')
        self.assertContains(board_response, 'data-board-edit-toggle')
        self.assertContains(board_response, 'data-board-information-window')
        self.assertContains(board_response, 'data-board-create-window')
        self.assertContains(board_response, 'class="ui-accordion-content room-board-window"', count=2)
        self.assertContains(board_response, 'data-board-editor hidden')
        self.assertContains(board_response, 'class="room-board-edit"')
        self.assertContains(board_response, '>編集<', count=1)
        self.assertContains(board_response, '>詳細情報<', count=1)
        self.assertContains(board_response, '>Thread作成<', count=1)
        self.assertNotContains(member_response, 'data-board-edit-toggle')
        self.assertContains(member_response, 'data-board-information-toggle')
        self.assertContains(member_response, 'data-board-create-toggle')
        self.assertContains(member_response, 'disabled title="BoardのThread作成条件を満たしていません"')
        self.assertNotContains(member_response, 'data-board-create-window')
        self.assertContains(board_response, 'Boardの削除は取り消せません。')
        self.assertContains(board_response, 'data-open-account-conditions', count=8)
        self.assertContains(board_response, 'data-account-condition-groups-input', count=8)

    def test_room_page_includes_shared_account_condition_workspace(self):
        self.client.force_login(self.owner)
        self.assertFalse(self.owner.account_conditions.exists())

        response = self.client.get(reverse('rooms:detail', args=[self.room.pk]))

        self.assertFalse(self.owner.account_conditions.exists())
        self.assertContains(response, 'id="account-condition-pane"')
        self.assertContains(response, 'data-account-condition-pane-template')
        self.assertContains(response, 'id="account-selector-pane"')
        self.assertContains(response, 'data-account-selector-pane-template')
        self.assertContains(response, 'data-account-condition-list-url="/accounts/account-conditions/"')
        self.assertNotContains(response, 'id="room-account-condition-catalog"')
        self.assertContains(response, 'accounts/account_conditions.js?v=20261005-v10')
        self.assertContains(response, 'room.js?v=20261004-17')

    def test_board_policy_supports_and_groups_and_deny_precedence(self):
        group_key = uuid4()
        self.board.policy_conditions.all().delete()
        BoardPolicyCondition.objects.bulk_create([
            BoardPolicyCondition(
                board=self.board, capability='view', decision='allow', group_key=group_key,
                position=0, kind='default', definition={'code': 'account'}, label='NiixyAccount',
            ),
            BoardPolicyCondition(
                board=self.board, capability='view', decision='allow', group_key=group_key,
                position=1, kind='room', definition={'room_id': self.room.pk, 'relation': 'member'},
                label=f'{self.room.name}に参加',
            ),
        ])

        outsider_result = self.board.evaluate_policy(self.outsider, 'view')
        RoomMembership.objects.create(room=self.room, account=self.member)
        member_result = self.board.evaluate_policy(self.member, 'view')

        self.assertFalse(outsider_result.allowed)
        self.assertEqual(
            outsider_result.unmet_allow_labels,
            (f'NiixyAccount AND {self.room.name}に参加',),
        )
        self.assertTrue(member_result.allowed)

        BoardPolicyCondition.objects.create(
            board=self.board, capability='view', decision='deny',
            kind='default', definition={'code': 'account'}, label='NiixyAccount',
        )
        denied_result = self.board.evaluate_policy(self.member, 'view')
        self.assertFalse(denied_result.allowed)
        self.assertEqual(denied_result.matched_deny_labels, ('NiixyAccount',))

    def test_board_view_policy_keeps_summary_but_withholds_board_contents(self):
        thread = Thread.objects.create(creator=self.owner, title='Secret Thread')
        ThreadPost.objects.create(thread=thread, number=1, creator=self.owner, body='Secret Body')
        ThreadPlacement.objects.create(thread=thread, kind=ThreadPlacement.BOARD, board=self.board)
        self.board.description = 'Secret Board Description'
        self.board.save(update_fields=['description'])
        self.board.policy_conditions.filter(capability='view').delete()
        BoardPolicyCondition.objects.create(
            board=self.board, capability='view', decision='allow',
            kind='default', definition={'code': 'account'}, label='NiixyAccount',
        )

        list_response = self.client.get(reverse('rooms:boards', args=[self.room.pk]))
        detail_response = self.client.get(reverse('rooms:board-threads', args=[self.room.pk, self.board.pk]))

        self.assertContains(list_response, '閲覧不可')
        self.assertContains(list_response, self.board.name)
        self.assertNotContains(list_response, f'{self.board.name} (1)')
        self.assertContains(detail_response, 'data-board-view-unavailable')
        self.assertContains(detail_response, 'NiixyAccount')
        self.assertNotContains(detail_response, 'Secret Board Description')
        self.assertNotContains(detail_response, 'Secret Thread')
        self.assertNotContains(detail_response, 'Secret Body')
        self.assertNotContains(detail_response, 'data-board-information-toggle')

    def test_owner_updates_board_policy_with_board_information(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse('rooms:board-edit', args=[self.room.pk, self.board.pk]),
            {
                'name': self.board.name,
                'description': self.board.description,
                'policy_present': 'true',
                'policy_view_allow_account': 'true',
                'policy_view_deny_guest': 'true',
                'policy_create_thread_allow_room_member': 'true',
            },
        )

        self.assertEqual(response.status_code, 200)
        conditions = self.board.policy_conditions.order_by('capability', 'decision', 'label')
        self.assertEqual(conditions.count(), 3)
        self.assertTrue(self.board.evaluate_policy(self.outsider, 'view').allowed)
        guest_result = self.board.evaluate_policy(AnonymousUser(), 'view')
        self.assertFalse(guest_result.allowed)
        self.assertEqual(guest_result.matched_deny_labels, ('Guest',))

    def test_owner_updates_board_policy_from_account_condition_groups(self):
        self.client.force_login(self.owner)
        groups = [[
            {
                'kind': 'default',
                'definition': {'code': 'account'},
                'label': 'NiixyAccount',
            },
            {
                'kind': 'room',
                'definition': {'room_id': self.room.pk, 'relation': 'member'},
                'label': f'{self.room.name}に参加',
            },
        ]]

        response = self.client.post(
            reverse('rooms:board-edit', args=[self.room.pk, self.board.pk]),
            {
                'name': self.board.name,
                'description': self.board.description,
                'policy_present': 'true',
                'policy_view_allow_groups': json.dumps(groups),
                'policy_view_deny_groups': '[]',
                'policy_create_thread_allow_groups': '[]',
                'policy_create_thread_deny_groups': '[]',
            },
        )

        self.assertEqual(response.status_code, 200)
        conditions = list(self.board.policy_conditions.order_by('position'))
        self.assertEqual(len(conditions), 2)
        self.assertEqual(conditions[0].group_key, conditions[1].group_key)
        self.assertEqual([condition.position for condition in conditions], [0, 1])
        self.assertEqual([condition.kind for condition in conditions], ['default', 'room'])
        self.assertFalse(self.board.evaluate_policy(self.outsider, 'view').allowed)
        self.assertTrue(self.board.evaluate_policy(self.owner, 'view').allowed)

    def test_board_thread_create_requires_view_and_create_permissions(self):
        RoomMembership.objects.create(room=self.room, account=self.member)
        url = reverse('rooms:board-thread-create', args=[self.room.pk, self.board.pk])
        for actor, allow_view, deny_view, allow_create, expected_status in (
            (self.member, False, False, True, 403),
            (self.member, True, True, True, 403),
            (self.member, True, False, False, 403),
            (self.member, True, False, True, 200),
            (self.owner, False, True, True, 200),
            (self.owner, False, True, False, 403),
        ):
            with self.subTest(actor=actor.username, allow_view=allow_view,
                              deny_view=deny_view, allow_create=allow_create):
                self.board.policy_conditions.all().delete()
                for capability, decision, enabled in (
                    (BoardPolicyCondition.VIEW, BoardPolicyCondition.ALLOW, allow_view),
                    (BoardPolicyCondition.VIEW, BoardPolicyCondition.DENY, deny_view),
                    (BoardPolicyCondition.CREATE_THREAD, BoardPolicyCondition.ALLOW, allow_create),
                ):
                    if enabled:
                        BoardPolicyCondition.objects.create(
                            board=self.board, capability=capability, decision=decision,
                            kind='default', definition={'code': 'account'}, label='NiixyAccount',
                        )
                self.client.force_login(actor)
                before = (Thread.objects.count(), ThreadPost.objects.count(),
                          ThreadPlacement.objects.count())
                response = self.client.post(url, {
                    'submission_id': str(uuid4()), 'title': 'Permission check', 'body': 'Body',
                })
                self.assertEqual(response.status_code, expected_status)
                after = (Thread.objects.count(), ThreadPost.objects.count(),
                         ThreadPlacement.objects.count())
                if expected_status == 403:
                    self.assertEqual(after, before)
                else:
                    self.assertEqual(after, tuple(count + 1 for count in before))
                    thread = Thread.objects.get(pk=response.json()['thread_id'])
                    self.assertEqual(thread.creator, actor)
                    self.assertEqual(thread.placements.get().board, self.board)

    def test_thread_create_post_rechecks_board_policy(self):
        self.client.force_login(self.owner)
        self.client.post(
            reverse('rooms:board-edit', args=[self.room.pk, self.board.pk]),
            {
                'name': self.board.name,
                'description': self.board.description,
                'policy_present': 'true',
                'policy_view_allow_guest': 'true',
                'policy_view_allow_account': 'true',
            },
        )

        response = self.client.post(
            reverse('rooms:board-thread-create', args=[self.room.pk, self.board.pk]),
            {'submission_id': str(uuid4()), 'title': 'Denied', 'body': 'Denied'},
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Thread.objects.filter(title='Denied').exists())

    def test_deleting_board_keeps_thread_and_allows_policy_authorized_reply(self):
        thread = Thread.objects.create(creator=self.owner, title='Unplaced Thread')
        post = ThreadPost.objects.create(thread=thread, number=1, creator=self.owner, body='残る本文')
        ThreadPlacement.objects.create(thread=thread, kind=ThreadPlacement.BOARD, board=self.board)
        ThreadAccessRule.objects.create(thread=thread, capability='view', audience='account')
        ThreadAccessRule.objects.create(thread=thread, capability='write', audience='account')
        self.client.force_login(self.owner)

        delete_response = self.client.post(reverse('rooms:board-delete', args=[self.room.pk, self.board.pk]))
        self.assertEqual(delete_response.status_code, 200)
        self.assertFalse(Board.objects.filter(pk=self.board.pk).exists())
        self.assertTrue(Thread.objects.filter(pk=thread.pk).exists())
        self.assertTrue(ThreadPost.objects.filter(pk=post.pk).exists())
        self.assertFalse(ThreadPlacement.objects.filter(thread=thread).exists())

        self.client.force_login(self.outsider)
        reply_response = self.client.post(
            reverse('events:thread-post-create', args=[thread.pk]),
            {'submission_id': str(uuid4()), 'body': 'Board削除後の返信'},
        )
        detail_response = self.client.get(
            reverse('accounts:thread-detail', args=[self.owner.username, thread.pk]),
        )

        self.assertEqual(reply_response.status_code, 200)
        self.assertContains(detail_response, '残る本文')
        self.assertContains(detail_response, 'Board削除後の返信')
        self.assertContains(detail_response, 'class="thread-reply-form"')

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
        self.assertEqual(thread.policy_conditions.count(), 3)

    def test_member_board_form_exposes_existing_thread_features(self):
        self.client.force_login(self.owner)

        page_response = self.client.get(reverse('rooms:detail', args=[self.room.pk]))
        pane_response = self.client.get(reverse('rooms:board-threads', args=[self.room.pk, self.board.pk]))

        self.assertContains(page_response, 'room-thread-field-catalog')
        self.assertContains(page_response, 'room-thread-interface-catalog')
        self.assertContains(pane_response, 'data-thread-selected-direct-fields')
        self.assertContains(pane_response, 'data-thread-selected-interfaces')
        self.assertContains(pane_response, 'data-open-thread-field-selector')
        self.assertContains(pane_response, 'data-open-thread-interface-selector')
        self.assertContains(pane_response, 'class="thread-interface-input"', count=3)
        self.assertContains(pane_response, '<summary>Policy</summary>')
        self.assertContains(pane_response, 'data-thread-policy-editor')
        for capability in ('view', 'write'):
            for decision in ('allow', 'deny'):
                self.assertContains(pane_response, f'name="policy_{capability}_{decision}_groups"')
        rows = pane_response.context['thread_policy_editor_rows']
        for row in rows:
            groups = json.loads(row['groups_json'])
            self.assertEqual([group[0]['definition']['code'] for group in groups],
                             ['guest', 'account'] if row['decision'] == 'allow' else [])

    def test_board_thread_summary_uses_thread_color_kind(self):
        thread = Thread.objects.create(creator=self.owner, title='色分けThread')
        ThreadPost.objects.create(thread=thread, number=1, creator=self.owner, body='本文')
        ThreadPlacement.objects.create(thread=thread, kind=ThreadPlacement.BOARD, board=self.board)
        self.client.force_login(self.owner)

        response = self.client.get(reverse('rooms:board-threads', args=[self.room.pk, self.board.pk]))

        self.assertContains(response, 'data-summary-kind="thread"')

    def test_room_overview_uses_compact_controls_without_description(self):
        response = self.client.get(reverse('rooms:detail', args=[self.room.pk]))
        board_response = self.client.get(reverse('rooms:boards', args=[self.room.pk]))

        self.assertContains(response, 'RoomIF')
        self.assertContains(response, 'Member(1)')
        self.assertContains(response, '>Board<')
        self.assertContains(response, 'Timeline')
        self.assertContains(response, 'Policy')
        self.assertContains(response, 'class="room-overview-body identity-overview-content"')
        self.assertContains(response, 'class="room-hero identity-overview-hero"')
        self.assertContains(response, '<h2>評価</h2>')
        self.assertContains(response, '<h2>Profile</h2>')
        self.assertLess(
            response.content.index(b'class="ui-placement-row'),
            response.content.index(b'class="room-overview-body'),
        )
        self.assertNotContains(response, 'もっと見る')
        self.assertNotContains(response, '最初のBoard')
        self.assertNotContains(response, 'Roomの説明')
        self.assertNotContains(response, 'Owner:')
        self.assertContains(response, 'room-thread-list-pane')
        self.assertContains(board_response, '最初のBoard')
        self.assertContains(board_response, 'data-ui-tab=', count=2)
        self.assertContains(board_response, '>Main<')
        self.assertContains(board_response, '>未分類<')

    def test_room_pane_exposes_workspace_endpoints(self):
        response = self.client.get(reverse('rooms:pane', args=[self.room.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-room-fragment')
        self.assertContains(response, reverse('rooms:members', args=[self.room.pk]))
        self.assertContains(response, reverse('rooms:boards', args=[self.room.pk]))
        self.assertContains(response, reverse('accounts:account-condition-list'))
        self.assertContains(response, 'id="room-pane-field-catalog"')
        self.assertContains(response, 'id="room-pane-interface-catalog"')
        self.assertContains(response, 'ui-placement-row')

    def test_explicit_thread_room_condition_controls_reply(self):
        thread = Thread.objects.create(creator=self.owner, title='Membership Gate')
        ThreadPost.objects.create(thread=thread, number=1, creator=self.owner, body='本文')
        ThreadPlacement.objects.create(thread=thread, kind=ThreadPlacement.BOARD, board=self.board)
        ThreadAccessRule.objects.create(thread=thread, capability='view', audience='account')
        from events.policies import prepare_thread_policy, save_thread_policy
        save_thread_policy(thread, prepare_thread_policy({
            'policy_view_allow_groups': json.dumps([[{'kind': 'default', 'definition': {'code': 'account'}}]]),
            'policy_write_allow_groups': json.dumps([[{'kind': 'room', 'definition': {'room_id': self.room.pk, 'relation': 'member'}}]]),
        }, self.owner))
        url = reverse('events:thread-post-create', args=[thread.pk])

        self.client.force_login(self.outsider)
        denied = self.client.post(url, {'body': '不可', 'submission_id': str(uuid4())})
        self.client.force_login(self.owner)
        allowed = self.client.post(url, {'body': '可能', 'submission_id': str(uuid4())})

        self.assertEqual(denied.status_code, 403)
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(thread.posts.count(), 2)

    def test_shared_detail_uses_explicit_thread_room_condition_from_account_page(self):
        thread = Thread.objects.create(creator=self.owner, title='Shared Detail')
        ThreadPost.objects.create(thread=thread, number=1, creator=self.owner, body='本文')
        ThreadPlacement.objects.create(thread=thread, kind=ThreadPlacement.BOARD, board=self.board)
        ThreadAccessRule.objects.create(thread=thread, capability='view', audience='account')
        from events.policies import prepare_thread_policy, save_thread_policy
        save_thread_policy(thread, prepare_thread_policy({
            'policy_view_allow_groups': json.dumps([[{'kind': 'default', 'definition': {'code': 'account'}}]]),
            'policy_write_allow_groups': json.dumps([[{'kind': 'room', 'definition': {'room_id': self.room.pk, 'relation': 'member'}}]]),
        }, self.owner))
        account_url = reverse('accounts:thread-detail', args=[self.owner.username, thread.pk])
        room_url = reverse('rooms:thread-detail', args=[self.room.pk, thread.pk])

        self.client.force_login(self.outsider)
        outsider_response = self.client.get(account_url)

        self.assertContains(outsider_response, 'class="thread-detail"')
        self.assertContains(outsider_response, self.room.name)
        self.assertContains(outsider_response, self.board.placement.collection.name)
        self.assertContains(outsider_response, self.board.name)
        self.assertContains(outsider_response, f'href="{reverse("rooms:detail", args=[self.room.pk])}"')
        self.assertContains(outsider_response, f'href="{reverse("rooms:detail", args=[self.room.pk])}?boards=1"')
        self.assertContains(outsider_response, f'href="{reverse("rooms:detail", args=[self.room.pk])}?board={self.board.pk}"')
        self.assertNotContains(outsider_response, 'class="thread-reply-form"')
        self.assertContains(outsider_response, 'class="thread-reply-unavailable"')
        self.assertContains(outsider_response, '次の条件グループのいずれかを満たす必要があります。')
        self.assertContains(outsider_response, f'<span class="thread-write-condition">{self.room.name}に参加</span>')
        self.assertContains(outsider_response, 'data-open-thread-policy')

        RoomMembership.objects.create(room=self.room, account=self.member)
        self.client.force_login(self.member)
        account_response = self.client.get(account_url)
        room_response = self.client.get(room_url)

        self.assertContains(account_response, 'class="thread-reply-form"')
        self.assertContains(room_response, 'class="thread-reply-form"')
        self.assertNotContains(account_response, 'class="thread-reply-unavailable"')
        self.assertNotContains(room_response, 'class="thread-reply-unavailable"')
        self.assertContains(account_response, 'data-thread-id=', count=1)
        self.assertContains(room_response, 'data-thread-id=', count=1)

    def test_niimap_lists_room_but_not_room_internal_thread(self):
        thread = Thread.objects.create(creator=self.owner, title='Room Only Thread')
        ThreadPost.objects.create(thread=thread, number=1, creator=self.owner, body='本文')
        ThreadPlacement.objects.create(thread=thread, kind=ThreadPlacement.BOARD, board=self.board)

        response = self.client.get(reverse('events:map'))

        self.assertContains(response, 'View Room')
        self.assertContains(response, 'data-summary-kind="room"')
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
