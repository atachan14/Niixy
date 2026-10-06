"""Room display filtering follows original placement, never free references or ACL."""
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import Board, RoomMute


def muted_room_ids(viewer):
    if not viewer.is_authenticated:
        return RoomMute.objects.none().values_list('room_id', flat=True)
    return RoomMute.objects.filter(muter_id=viewer.pk).values_list('room_id', flat=True)


def muted_thread_ids(viewer):
    from events.models import ThreadPlacement
    return ThreadPlacement.objects.filter(
        kind='board', is_primary=True, board__placement__kind='collection',
        board__placement__collection__room_id__in=muted_room_ids(viewer),
    ).values_list('thread_id', flat=True)


def filter_muted_rooms(queryset, viewer):
    if not viewer.is_authenticated:
        return queryset
    # ThreadPost deliberately retains existing AccountMute-only semantics.
    label = queryset.model._meta.label_lower
    if label == 'rooms.room':
        return queryset.exclude(pk__in=muted_room_ids(viewer))
    if label == 'rooms.board':
        return queryset.exclude(Q(placement__kind='collection', placement__collection__room_id__in=muted_room_ids(viewer)))
    if label == 'events.thread':
        return queryset.exclude(pk__in=muted_thread_ids(viewer))
    return queryset


def muted_board_ids(viewer):
    return Board.objects.filter(placement__kind='collection', placement__collection__room_id__in=muted_room_ids(viewer)).values_list('pk', flat=True)


@require_POST
def change(request, room_id):
    from .reviews import target_room
    room = target_room(room_id)
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'ログインが必要です。'}, status=401)
    enabled = request.POST.get('enabled')
    if enabled not in {'true', 'false'}:
        return JsonResponse({'error': 'Muteの状態が正しくありません。'}, status=400)
    if enabled == 'true':
        RoomMute.objects.get_or_create(muter=request.user, room=room)
    else:
        RoomMute.objects.filter(muter=request.user, room=room).delete()
    return JsonResponse({'ok': True, 'muted': enabled == 'true'})
