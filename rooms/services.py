import json
import uuid

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction

from events.idempotency import run_once
from accounts.policies import condition_groups

from .models import Board, BoardPlacement, BoardPolicyCondition, Collection, Room, RoomMembership, RoomPlacement


def default_board_policy_conditions(board, room):
    return [
        BoardPolicyCondition(
            board=board,
            capability=BoardPolicyCondition.VIEW,
            decision=BoardPolicyCondition.ALLOW,
            kind='default',
            definition={'code': 'guest'},
            label='Guest',
        ),
        BoardPolicyCondition(
            board=board,
            capability=BoardPolicyCondition.VIEW,
            decision=BoardPolicyCondition.ALLOW,
            kind='default',
            definition={'code': 'account'},
            label='NiixyAccount',
        ),
        BoardPolicyCondition(
            board=board,
            capability=BoardPolicyCondition.CREATE_THREAD,
            decision=BoardPolicyCondition.ALLOW,
            kind='room',
            definition={'room_id': room.pk, 'relation': 'member'},
            label=f'{room.name}に参加',
        ),
    ]


def seed_board_policy(board, room):
    if not board.policy_conditions.exists():
        BoardPolicyCondition.objects.bulk_create(default_board_policy_conditions(board, room))


def _board_policy_condition_snapshot(condition, room, actor):
    from accounts.policies import snapshot_policy_condition
    return snapshot_policy_condition(condition, actor)


def _policy_groups_from_data(data, capability, decision):
    raw = data.get(f'policy_{capability}_{decision}_groups')
    if raw is None:
        return None
    try:
        groups = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as error:
        raise ValueError('Policy条件が正しくありません。') from error
    if not isinstance(groups, list) or any(not isinstance(group, list) or not group for group in groups):
        raise ValueError('Policy条件が正しくありません。')
    return groups


@transaction.atomic
def update_board_policy(board, room, data, actor):
    candidates = {
        'guest': ('default', {'code': 'guest'}, 'Guest'),
        'account': ('default', {'code': 'account'}, 'NiixyAccount'),
        'room_member': ('room', {'room_id': room.pk, 'relation': 'member'}, f'{room.name}に参加'),
    }
    conditions = []
    for capability, _ in BoardPolicyCondition.CAPABILITY_CHOICES:
        for decision, _ in BoardPolicyCondition.DECISION_CHOICES:
            groups = _policy_groups_from_data(data, capability, decision)
            if groups is not None:
                for group in groups:
                    group_key = uuid.uuid4()
                    for position, condition in enumerate(group):
                        kind, definition, label = _board_policy_condition_snapshot(condition, room, actor)
                        conditions.append(BoardPolicyCondition(
                            board=board,
                            capability=capability,
                            decision=decision,
                            group_key=group_key,
                            position=position,
                            kind=kind,
                            definition=definition,
                            label=label,
                        ))
                continue
            for key, (kind, definition, label) in candidates.items():
                if data.get(f'policy_{capability}_{decision}_{key}') != 'true':
                    continue
                conditions.append(BoardPolicyCondition(
                    board=board,
                    capability=capability,
                    decision=decision,
                    kind=kind,
                    definition=definition,
                    label=label,
                ))
    board.policy_conditions.all().delete()
    BoardPolicyCondition.objects.bulk_create(conditions)


def board_policy_rows(board):
    conditions = list(board.policy_conditions.all())
    rows = []
    labels = {
        BoardPolicyCondition.VIEW: '閲覧',
        BoardPolicyCondition.CREATE_THREAD: 'Thread作成',
    }
    for capability, _ in BoardPolicyCondition.CAPABILITY_CHOICES:
        capability_conditions = [item for item in conditions if item.capability == capability]
        rows.append({
            'capability': capability,
            'label': labels[capability],
            'allow_labels': [
                ' AND '.join(item.label for item in group)
                for group in condition_groups(
                    item for item in capability_conditions if item.decision == BoardPolicyCondition.ALLOW
                )
            ],
            'deny_labels': [
                ' AND '.join(item.label for item in group)
                for group in condition_groups(
                    item for item in capability_conditions if item.decision == BoardPolicyCondition.DENY
                )
            ],
        })
    return rows


def board_policy_editor_rows(board, room):
    conditions = list(board.policy_conditions.all())
    rows = []
    for capability, label in BoardPolicyCondition.CAPABILITY_CHOICES:
        decisions = []
        for decision, decision_label in BoardPolicyCondition.DECISION_CHOICES:
            selected = [
                item for item in conditions
                if item.capability == capability and item.decision == decision
            ]
            groups = [
                [
                    {
                        'kind': item.kind,
                        'definition': item.definition,
                        'label': item.label,
                    }
                    for item in group
                ]
                for group in condition_groups(selected)
            ]
            decisions.append({
                'decision': decision,
                'label': f'{label}{decision_label}',
                'target': f'board-policy-{board.pk}-{capability}-{decision}',
                'groups_json': json.dumps(groups, ensure_ascii=False),
            })
        rows.append({'capability': capability, 'label': label, 'decisions': decisions})
    return rows


def create_room(*, submission_id, owner, name, description, latitude, longitude):
    def operation():
        room = Room.objects.create(
            submission_id=submission_id,
            owner=owner,
            created_by=owner,
            name=name,
            description=description,
        )
        RoomMembership.objects.create(room=room, account=owner)
        RoomPlacement.objects.create(room=room, latitude=latitude, longitude=longitude)
        main = Collection.objects.create(name='Main', room=room)
        Collection.objects.create(name='未分類', room=room, is_uncategorized=True)
        board = Board.objects.create(name='最初のBoard')
        BoardPlacement.objects.create(board=board, kind=BoardPlacement.COLLECTION, collection=main)
        seed_board_policy(board, room)
        return room

    return run_once(Room, submission_id, operation)


def create_board(*, submission_id, collection, name, description=''):
    def operation():
        with transaction.atomic():
            target = Collection.objects.select_for_update().get(pk=collection.pk)
            board = Board.objects.create(
                submission_id=submission_id,
                name=name,
                description=description,
            )
            BoardPlacement.objects.create(
                board=board,
                kind=BoardPlacement.COLLECTION,
                collection=target,
            )
            room = target.room
            if room is not None:
                seed_board_policy(board, room)
            return board

    return run_once(Board, submission_id, operation)


def delete_collection(collection):
    with transaction.atomic():
        source = Collection.objects.select_for_update().get(pk=collection.pk)
        if source.is_uncategorized:
            raise ValueError('The Uncategorized collection cannot be deleted.')

        placements = BoardPlacement.objects.select_for_update().filter(collection=source)
        fallback = None
        if placements.exists():
            container = {'account_id': source.account_id, 'room_id': source.room_id}
            fallback, _ = Collection.objects.get_or_create(
                **container,
                is_uncategorized=True,
                defaults={'name': '未分類'},
            )
            placements.update(collection=fallback)
            Collection.objects.filter(pk=fallback.pk).update(last_activity_at=timezone.now())

        source.delete()
        return fallback


def board_for_thread(thread):
    placements = getattr(thread, '_prefetched_objects_cache', {}).get('placements')
    if placements is None:
        placements = thread.placements.select_related(
            'board__placement__collection__room',
        ).all()
    for placement in placements:
        if placement.kind == 'board' and placement.board_id:
            return placement.board
    return None


def room_for_thread(thread):
    board = board_for_thread(thread)
    if board is None:
        return None
    try:
        collection = board.placement.collection
    except (BoardPlacement.DoesNotExist, AttributeError):
        return None
    return collection.room if collection and collection.room_id else None


def touch_thread_containers(thread):
    placement = (
        thread.placements.select_related('board__placement__collection__room')
        .filter(kind='board', board__isnull=False)
        .first()
    )
    if placement is None:
        return
    try:
        collection = placement.board.placement.collection
    except BoardPlacement.DoesNotExist:
        return
    now = timezone.now()
    Board.objects.filter(pk=placement.board_id).update(last_activity_at=now)
    if collection:
        Collection.objects.filter(pk=collection.pk).update(last_activity_at=now)
        if collection.room_id:
            Room.objects.filter(pk=collection.room_id).update(last_activity_at=now)
