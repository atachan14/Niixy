from django.utils import timezone
from django.db import transaction

from events.idempotency import run_once

from .models import Board, BoardPlacement, Collection, Room, RoomMembership, RoomPlacement


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
        main = Collection.objects.create(name='Main', room=room, is_main=True)
        board = Board.objects.create(name='最初のBoard')
        BoardPlacement.objects.create(board=board, kind=BoardPlacement.COLLECTION, collection=main)
        return room

    return run_once(Room, submission_id, operation)


def create_board(*, submission_id, room, name, description=''):
    def operation():
        with transaction.atomic():
            main = room.collections.select_for_update().get(is_main=True)
            board = Board.objects.create(
                submission_id=submission_id,
                name=name,
                description=description,
            )
            BoardPlacement.objects.create(
                board=board,
                kind=BoardPlacement.COLLECTION,
                collection=main,
            )
            return board

    return run_once(Board, submission_id, operation)


def board_for_thread(thread):
    placements = thread._prefetched_objects_cache.get('placements')
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
