import uuid

from django.db import transaction
from django.db.models import Count
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from events.idempotency import run_once, submission_id_from
from events.models import Thread, ThreadAccessRule, ThreadPlacement, ThreadPost
from events.services import prepare_thread_for_view, prepare_thread_modules, thread_queryset
from interfaces.services import save_thread_fields, thread_field_catalog, thread_interface_catalog

from .forms import BoardForm, BoardThreadCreateForm, RoomCreateForm, RoomEditForm
from .models import Board, Room, RoomMembership
from .services import create_board, create_room, touch_thread_containers


def _room(request, room_id):
    room = get_object_or_404(
        Room.objects.select_related('owner__niixy_profile', 'placement').prefetch_related(
            'memberships__account__niixy_profile',
        ),
        pk=room_id,
    )
    room.is_member = room.has_member(request.user)
    room.is_owner = request.user.is_authenticated and room.owner_id == request.user.id
    return room


def _room_boards(room):
    return (
        Board.objects.filter(placement__collection__room=room)
        .select_related('placement__collection')
        .order_by('-last_activity_at', '-created_at')
    )


def _managed_board(room, board_id):
    return get_object_or_404(_room_boards(room), pk=board_id)


def _require_room_owner(request, room):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Boardの管理にはログインが必要です。'}, status=401)
    if not room.is_owner:
        return JsonResponse({'error': 'Boardを管理できるのはRoomOwnerだけです。'}, status=403)
    return None


@require_POST
def room_create(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Roomの作成にはログインが必要です。'}, status=401)
    form = RoomCreateForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'errors': {name: list(errors) for name, errors in form.errors.items()}}, status=400)
    room, _ = create_room(
        submission_id=submission_id_from(request.POST.get('submission_id')),
        owner=request.user,
        name=form.cleaned_data['name'],
        description=form.cleaned_data['description'],
        latitude=form.cleaned_data['latitude'],
        longitude=form.cleaned_data['longitude'],
    )
    return JsonResponse({'redirect_url': reverse('rooms:detail', args=[room.pk]), 'room_id': room.pk})


def room_detail(request, room_id):
    room = _room(request, room_id)
    return render(request, 'rooms/room_page.html', {
        'room': room,
        'thread_field_catalog': thread_field_catalog(),
        'thread_interface_catalog': thread_interface_catalog(),
    })


def room_pane(request, room_id):
    return render(request, 'rooms/partials/room_pane.html', {'room': _room(request, room_id)})


@require_POST
def room_join(request, room_id):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Roomへの参加にはログインが必要です。'}, status=401)
    room = _room(request, room_id)
    RoomMembership.objects.get_or_create(room=room, account=request.user)
    return JsonResponse({'ok': True, 'redirect_url': reverse('rooms:detail', args=[room.pk])})


@require_POST
def room_leave(request, room_id):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Roomからの退出にはログインが必要です。'}, status=401)
    room = _room(request, room_id)
    if room.owner_id == request.user.id:
        return JsonResponse({'error': 'RoomOwnerは退出できません。'}, status=400)
    RoomMembership.objects.filter(room=room, account=request.user).delete()
    return JsonResponse({'ok': True, 'redirect_url': reverse('rooms:detail', args=[room.pk])})


@require_POST
def room_edit(request, room_id):
    room = _room(request, room_id)
    if not room.is_owner:
        return JsonResponse({'error': 'Roomを編集できるのはRoomOwnerだけです。'}, status=403)
    form = RoomEditForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'errors': {name: list(errors) for name, errors in form.errors.items()}}, status=400)
    room.name = form.cleaned_data['name']
    room.description = form.cleaned_data['description']
    room.save(update_fields=['name', 'description', 'updated_at'])
    room.placement.latitude = form.cleaned_data['latitude']
    room.placement.longitude = form.cleaned_data['longitude']
    room.placement.save(update_fields=['latitude', 'longitude', 'updated_at'])
    return JsonResponse({'ok': True, 'redirect_url': reverse('rooms:detail', args=[room.pk])})


def room_members(request, room_id):
    room = _room(request, room_id)
    return render(request, 'rooms/partials/member_list.html', {'room': room})


def room_boards(request, room_id):
    room = _room(request, room_id)
    collections = list(room.collections.order_by('-is_main', 'created_at'))
    for collection in collections:
        collection.visible_boards = list(
            Board.objects.filter(placement__collection=collection)
            .select_related('placement__collection')
            .annotate(thread_count=Count('thread_placements'))
            .order_by('-last_activity_at', '-created_at')
        )
    return render(request, 'rooms/partials/board_list.html', {
        'room': room,
        'collections': collections,
        'board_submission_id': uuid.uuid4(),
    })


@require_POST
def board_create(request, room_id):
    room = _room(request, room_id)
    denied = _require_room_owner(request, room)
    if denied:
        return denied
    form = BoardForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'errors': {name: list(errors) for name, errors in form.errors.items()}}, status=400)
    board, _ = create_board(
        submission_id=submission_id_from(request.POST.get('submission_id')),
        room=room,
        name=form.cleaned_data['name'],
        description=form.cleaned_data['description'],
    )
    return JsonResponse({
        'board_id': board.pk,
        'redirect_url': f'{reverse("rooms:detail", args=[room.pk])}?boards=1&board={board.pk}',
    })


@require_POST
def board_edit(request, room_id, board_id):
    room = _room(request, room_id)
    denied = _require_room_owner(request, room)
    if denied:
        return denied
    board = _managed_board(room, board_id)
    form = BoardForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'errors': {name: list(errors) for name, errors in form.errors.items()}}, status=400)
    board.name = form.cleaned_data['name']
    board.description = form.cleaned_data['description']
    board.save(update_fields=['name', 'description', 'updated_at'])
    return JsonResponse({
        'board_id': board.pk,
        'redirect_url': f'{reverse("rooms:detail", args=[room.pk])}?boards=1&board={board.pk}',
    })


@require_POST
def board_delete(request, room_id, board_id):
    room = _room(request, room_id)
    denied = _require_room_owner(request, room)
    if denied:
        return denied
    board = _managed_board(room, board_id)
    board.delete()
    return JsonResponse({
        'board_id': board_id,
        'redirect_url': f'{reverse("rooms:detail", args=[room.pk])}?boards=1',
    })


def board_threads(request, room_id, board_id):
    room = _room(request, room_id)
    board = get_object_or_404(_room_boards(room), pk=board_id)
    board_threads = list(thread_queryset().filter(placements__kind=ThreadPlacement.BOARD, placements__board=board))
    for thread in board_threads:
        thread.can_view = thread.allows(request.user, ThreadAccessRule.VIEW)
        thread.can_write = room.is_member and thread.allows(request.user, ThreadAccessRule.WRITE)
    threads = [thread for thread in board_threads if thread.can_view]
    return render(request, 'rooms/partials/board_threads.html', {
        'room': room,
        'board': board,
        'threads': threads,
        'thread_submission_id': uuid.uuid4(),
        'rule_capabilities': [
            (ThreadAccessRule.VIEW, '閲覧制限', 'guest account'),
            (ThreadAccessRule.WRITE, '書込制限', 'account'),
        ],
    })


def room_thread_detail(request, room_id, thread_id):
    room = _room(request, room_id)
    thread = get_object_or_404(
        thread_queryset().filter(
            placements__kind=ThreadPlacement.BOARD,
            placements__board__placement__collection__room=room,
        ),
        pk=thread_id,
    )
    prepare_thread_for_view(thread, request.user)
    return render(request, 'rooms/partials/thread_detail.html', {'room': room, 'thread': thread})


@require_POST
def board_thread_create(request, room_id, board_id):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Threadの作成にはRoomへの参加が必要です。'}, status=401)
    room = _room(request, room_id)
    if not room.is_member:
        return JsonResponse({'error': 'Threadの作成にはRoomへの参加が必要です。'}, status=403)
    board = get_object_or_404(_room_boards(room), pk=board_id)
    form = BoardThreadCreateForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'errors': {name: list(errors) for name, errors in form.errors.items()}}, status=400)
    try:
        prepared_direct_fields, prepared_interfaces = prepare_thread_modules(request.POST)
    except ValidationError as error:
        return JsonResponse({'errors': error.message_dict}, status=400)
    submission_id = submission_id_from(request.POST.get('submission_id'))

    def operation():
        with transaction.atomic():
            thread = Thread.objects.create(
                submission_id=submission_id,
                creator=request.user,
                title=form.cleaned_data['title'],
            )
            ThreadPost.objects.create(thread=thread, number=1, creator=request.user, body=form.cleaned_data['body'])
            ThreadPlacement.objects.create(thread=thread, kind=ThreadPlacement.BOARD, board=board)
            ThreadAccessRule.objects.bulk_create([
                ThreadAccessRule(thread=thread, capability=capability, audience=audience)
                for capability in (ThreadAccessRule.VIEW, ThreadAccessRule.WRITE)
                for audience in (ThreadAccessRule.GUEST, ThreadAccessRule.ACCOUNT)
                if request.POST.get(f'{capability}_{audience}') == 'true'
            ])
            save_thread_fields(thread, prepared_direct_fields, prepared_interfaces)
            touch_thread_containers(thread)
            return thread

    thread, _ = run_once(Thread, submission_id, operation)
    return JsonResponse({
        'thread_id': thread.pk,
        'redirect_url': f'{reverse("rooms:detail", args=[room.pk])}?board={board.pk}&thread={thread.pk}',
    })
