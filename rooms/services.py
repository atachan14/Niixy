from django.utils import timezone

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
        board = Board.objects.create(name='最初のBoard', owner_room=room, created_by=owner)
        BoardPlacement.objects.create(board=board, kind=BoardPlacement.COLLECTION, collection=main)
        return room

    return run_once(Room, submission_id, operation)


def room_for_thread(thread):
    placements = thread._prefetched_objects_cache.get('placements')
    if placements is None:
        placements = thread.placements.select_related(
            'board__placement__collection__room',
        ).all()
    for placement in placements:
        if placement.kind != 'board' or not placement.board_id:
            continue
        try:
            collection = placement.board.placement.collection
        except (BoardPlacement.DoesNotExist, AttributeError):
            continue
        if collection and collection.room_id:
            return collection.room
    return None


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
