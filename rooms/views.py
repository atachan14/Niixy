from django.views.decorators.cache import never_cache
import uuid

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q, Case, Count, IntegerField, Value, When
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from events.idempotency import run_once, submission_id_from
from accounts.mutes import filter_muted, muted_account_ids
from .mutes import muted_board_ids
from .reviews import review_context
from events.models import Thread, ThreadAccessRule, ThreadPlacement, ThreadPost
from events.services import prepare_thread_for_view, prepare_thread_modules, thread_queryset
from events.policies import prepare_thread_policy, save_thread_policy, default_thread_policy_groups, thread_policy_editor_rows
from interfaces.services import save_thread_fields, thread_field_catalog, thread_interface_catalog

from .forms import BoardForm, BoardThreadCreateForm, CollectionForm, MapBoardForm, RoomCreateForm, RoomEditForm
from .models import Board, BoardPlacement, BoardPolicyCondition, Collection, Room, RoomMembership
from .services import (
    board_policy_editor_rows,
    board_policy_rows,
    create_board,
    create_room,
    delete_collection,
    default_board_policy_conditions,
    touch_thread_containers,
    update_board_policy,
)


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


def _board_scope(request, room_id=None, username=None):
    if username is None:
        return _room(request, room_id) if room_id is not None else None
    account = get_object_or_404(get_user_model().objects.select_related('niixy_profile'), username__iexact=username)
    account.is_owner = request.user.is_authenticated and request.user.pk == account.pk
    return account


def _scope_room(scope):
    return scope if isinstance(scope, Room) else None


def _scope_account(scope):
    return None if isinstance(scope, Room) else scope


def _scope_url(scope, name, *ids):
    if scope is None:
        routes = {'detail': 'map', 'board-threads': 'board-pane', 'board-thread-create': 'board-thread-create'}
        return reverse(f'events:{routes[name]}', args=ids)
    namespace = 'rooms' if isinstance(scope, Room) else 'accounts'
    identifier = scope.pk if isinstance(scope, Room) else scope.username
    return reverse(f'{namespace}:{name}', args=[identifier, *ids])


def _scope_board_query(scope):
    return '' if scope is None else ('boards=1' if isinstance(scope, Room) else 'pane=board')


def _scope_context(scope):
    if scope is None:
        return {'board_is_owner': False, 'map_board': True}
    return {
        'room': _scope_room(scope),
        'account': _scope_account(scope),
        'board_is_owner': scope.is_owner,
        'account_boards': not isinstance(scope, Room),
        'collection_create_url': _scope_url(scope, 'collection-create'),
    }


def _container_boards(room):
    if room is None:
        return Board.objects.filter(placement__kind=BoardPlacement.NII_MAP).select_related('placement').prefetch_related('policy_conditions')
    return (
        Board.objects.filter(**{
            'placement__collection__room' if isinstance(room, Room) else 'placement__collection__account': room,
        })
        .select_related('placement__collection')
        .prefetch_related('policy_conditions')
        .order_by('-last_activity_at', '-created_at')
    )


def _managed_board(room, board_id):
    return get_object_or_404(_container_boards(room), pk=board_id)


def _container_collections(room):
    return room.collections.annotate(
        collection_order=Case(
            When(is_uncategorized=True, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        ),
    ).order_by('collection_order', 'created_at')


def _managed_collection(room, collection_id):
    return get_object_or_404(room.collections, pk=collection_id)


def _require_board_manager(request, room):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Boardの管理にはログインが必要です。'}, status=401)
    if room is None or not room.is_owner:
        return JsonResponse({'error': 'Boardを管理できるのは配置先の管理者だけです。'}, status=403)
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


@never_cache
def room_detail(request, room_id):
    room = _room(request, room_id)
    return render(request, 'rooms/room_page.html', {
        'room': room,
        **review_context(room, request.user),
        'thread_field_catalog': thread_field_catalog(),
        'thread_interface_catalog': thread_interface_catalog(),
    })


@never_cache
def room_pane(request, room_id):
    room = _room(request, room_id)
    return render(request, 'rooms/partials/room_pane.html', {
        'room': room,
        **review_context(room, request.user),
        'room_thread_field_catalog': thread_field_catalog(),
        'room_thread_interface_catalog': thread_interface_catalog(),
    })


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
    if room is None or not room.is_owner:
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


@never_cache
def room_boards(request, room_id=None, username=None):
    room = _board_scope(request, room_id, username)
    collections = list(_container_collections(room))
    for collection in collections:
        collection.edit_url = _scope_url(room, 'collection-edit', collection.pk)
        collection.delete_url = _scope_url(room, 'collection-delete', collection.pk)
        collection.board_create_url = _scope_url(room, 'board-create', collection.pk)
        collection.visible_boards = list(
            filter_muted(Board.objects.filter(placement__collection=collection), request.user)
            .select_related('placement__collection')
            .prefetch_related('policy_conditions')
            .annotate(thread_count=Count('thread_placements', filter=Q(thread_placements__thread_id__in=filter_muted(Thread.objects.all(), request.user).values('pk'))))
            .order_by('-last_activity_at', '-created_at')
        )
        for board in collection.visible_boards:
            board.detail_url = _scope_url(room, 'board-threads', board.pk)
            result = board.evaluate_policy(request.user, BoardPolicyCondition.VIEW)
            board.can_view = room.is_owner or result.allowed
        from accounts.content_lists import describe_target
        references = collection.references.select_related('target__placement__collection__room').prefetch_related('target__policy_conditions') if collection.account_id else []
        muted = set(muted_account_ids(request.user))
        muted_boards = set(muted_board_ids(request.user))
        collection.reference_summaries = [describe_target('board', ref.target, request.user) for ref in references if ref.target and ref.target.creator_id not in muted and ref.target_id not in muted_boards]
        collection.board_submission_id = uuid.uuid4()
        collection.board_policy_editor_rows = board_policy_editor_rows(
            Board(), room, conditions=default_board_policy_conditions(Board(), _scope_room(room), account=_scope_account(room)),
            target_prefix=f'board-policy-create-{collection.pk}',
        )
    return render(request, 'rooms/partials/board_list.html', {
        **_scope_context(room),
        'collections': collections,
        'rating_boards': _rated_boards(request, room) if username else {},
        'self_boards': [describe_target('board', board, request.user) for board in filter_muted(Board.objects.filter(creator=room).select_related('placement__collection__room').prefetch_related('policy_conditions'), request.user)] if username else [],
    })


@require_POST
def collection_create(request, room_id=None, username=None):
    room = _board_scope(request, room_id, username)
    denied = _require_board_manager(request, room)
    if denied:
        return denied
    form = CollectionForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'errors': {name: list(errors) for name, errors in form.errors.items()}}, status=400)
    collection = Collection.objects.create(
        room=_scope_room(room),
        account=_scope_account(room),
        name=form.cleaned_data['name'],
    )
    return JsonResponse({
        'collection_id': collection.pk,
        'redirect_url': f'{_scope_url(room, "detail")}?{_scope_board_query(room)}&collection={collection.pk}',
    })


@require_POST
def collection_edit(request, collection_id, room_id=None, username=None):
    room = _board_scope(request, room_id, username)
    denied = _require_board_manager(request, room)
    if denied:
        return denied
    collection = _managed_collection(room, collection_id)
    if collection.is_uncategorized:
        return JsonResponse({'error': '未分類Collectionは編集できません。'}, status=400)
    form = CollectionForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'errors': {name: list(errors) for name, errors in form.errors.items()}}, status=400)
    collection.name = form.cleaned_data['name']
    collection.save(update_fields=['name', 'updated_at'])
    return JsonResponse({
        'collection_id': collection.pk,
        'redirect_url': f'{_scope_url(room, "detail")}?{_scope_board_query(room)}&collection={collection.pk}',
    })


@require_POST
def collection_delete(request, collection_id, room_id=None, username=None):
    room = _board_scope(request, room_id, username)
    denied = _require_board_manager(request, room)
    if denied:
        return denied
    collection = _managed_collection(room, collection_id)
    if collection.is_uncategorized:
        return JsonResponse({'error': '未分類Collectionは削除できません。'}, status=400)
    fallback = delete_collection(collection)
    query = f'?{_scope_board_query(room)}'
    if fallback:
        query += f'&collection={fallback.pk}'
    return JsonResponse({
        'collection_id': collection_id,
        'redirect_url': f'{_scope_url(room, "detail")}{query}',
    })


@require_POST
def board_create(request, collection_id, room_id=None, username=None):
    room = _board_scope(request, room_id, username)
    denied = _require_board_manager(request, room)
    if denied:
        return denied
    form = BoardForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'errors': {name: list(errors) for name, errors in form.errors.items()}}, status=400)
    collection = _managed_collection(room, collection_id)
    try:
        board, _ = create_board(
            submission_id=submission_id_from(request.POST.get('submission_id')),
            collection=collection,
            name=form.cleaned_data['name'],
            description=form.cleaned_data['description'],
            policy_data=request.POST if request.POST.get('policy_present') == 'true' else None,
            actor=request.user,
        )
    except ValueError as error:
        return JsonResponse({'error': str(error)}, status=400)
    return JsonResponse({
        'board_id': board.pk,
        'redirect_url': f'{_scope_url(room, "detail")}?{_scope_board_query(room)}&collection={collection.pk}&board={board.pk}',
    })


@require_POST
def board_edit(request, board_id, room_id=None, username=None):
    room = _board_scope(request, room_id, username)
    denied = _require_board_manager(request, room)
    if denied:
        return denied
    board = _managed_board(room, board_id)
    form = BoardForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'errors': {name: list(errors) for name, errors in form.errors.items()}}, status=400)
    try:
        with transaction.atomic():
            board.name = form.cleaned_data['name']
            board.description = form.cleaned_data['description']
            board.save(update_fields=['name', 'description', 'updated_at'])
            if request.POST.get('policy_present') == 'true':
                update_board_policy(board, _scope_room(room), request.POST, request.user, account=_scope_account(room))
    except ValueError as error:
        return JsonResponse({'error': str(error)}, status=400)
    return JsonResponse({
        'board_id': board.pk,
        'redirect_url': f'{_scope_url(room, "detail")}?{_scope_board_query(room)}&board={board.pk}',
    })


@require_POST
def board_delete(request, board_id, room_id=None, username=None):
    room = _board_scope(request, room_id, username)
    denied = _require_board_manager(request, room)
    if denied:
        return denied
    board = _managed_board(room, board_id)
    board.delete()
    return JsonResponse({
        'board_id': board_id,
        'redirect_url': f'{_scope_url(room, "detail")}?{_scope_board_query(room)}',
    })


@never_cache
def board_threads(request, board_id, room_id=None, username=None):
    room = _board_scope(request, room_id, username)
    board = get_object_or_404(_container_boards(room), pk=board_id)
    view_policy = board.evaluate_policy(request.user, BoardPolicyCondition.VIEW)
    board.can_view = bool(room and room.is_owner) or view_policy.allowed
    create_policy = board.evaluate_policy(request.user, BoardPolicyCondition.CREATE_THREAD)
    board.can_create_thread = board.can_view and create_policy.allowed
    threads = []
    if board.can_view:
        board_threads = list(filter_muted(thread_queryset().filter(placements__kind=ThreadPlacement.BOARD, placements__board=board), request.user))
        muted = set(muted_account_ids(request.user))
        for thread in board_threads:
            prepare_thread_for_view(thread, request.user, muted)
        threads = board_threads
    return render(request, 'rooms/partials/board_threads.html', {
        **_scope_context(room),
        'board_edit_url': _scope_url(room, 'board-edit', board.pk) if room else '',
        'board_delete_url': _scope_url(room, 'board-delete', board.pk) if room else '',
        'board_thread_create_url': _scope_url(room, 'board-thread-create', board.pk),
        'board': board,
        'threads': threads,
        'board_policy_rows': board_policy_rows(board),
        'board_policy_editor_rows': board_policy_editor_rows(board, room),
        'view_policy': view_policy,
        'create_policy': create_policy,
        'thread_submission_id': uuid.uuid4(),
        'thread_policy_editor_rows': thread_policy_editor_rows(f'board-{board.pk}-{uuid.uuid4().hex}', default_thread_policy_groups()),
        'rule_capabilities': [
            (ThreadAccessRule.VIEW, '閲覧制限', 'guest account'),
            (ThreadAccessRule.WRITE, '書込制限', 'account'),
        ],
    })


@never_cache
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
def board_thread_create(request, board_id, room_id=None, username=None):
    room = _board_scope(request, room_id, username)
    board = get_object_or_404(_container_boards(room), pk=board_id)
    view_policy = board.evaluate_policy(request.user, BoardPolicyCondition.VIEW)
    can_view = bool(room and room.is_owner) or view_policy.allowed
    create_policy = board.evaluate_policy(request.user, BoardPolicyCondition.CREATE_THREAD)
    if not can_view or not create_policy.allowed:
        return JsonResponse({'error': 'BoardのThread作成条件を満たしていません。'}, status=403)
    form = BoardThreadCreateForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'errors': {name: list(errors) for name, errors in form.errors.items()}}, status=400)
    try:
        prepared_direct_fields, prepared_interfaces = prepare_thread_modules(request.POST)
        prepared_policy = prepare_thread_policy(request.POST, request.user)
    except ValidationError as error:
        return JsonResponse({'errors': error.message_dict}, status=400)
    submission_id = submission_id_from(request.POST.get('submission_id'))

    def operation():
        with transaction.atomic():
            thread = Thread.objects.create(
                submission_id=submission_id,
                creator=request.user if request.user.is_authenticated else None,
                title=form.cleaned_data['title'],
            )
            ThreadPost.objects.create(
                thread=thread,
                number=1,
                creator=request.user if request.user.is_authenticated else None,
                body=form.cleaned_data['body'],
            )
            ThreadPlacement.objects.create(thread=thread, kind=ThreadPlacement.BOARD, board=board)
            save_thread_policy(thread, prepared_policy)
            save_thread_fields(thread, prepared_direct_fields, prepared_interfaces)
            touch_thread_containers(thread)
            return thread

    thread, _ = run_once(Thread, submission_id, operation)
    if not thread.placements.filter(kind=ThreadPlacement.BOARD, board=board).exists():
        return JsonResponse({'error': 'この送信IDは別のBoardで使用されています。'}, status=409)
    query_prefix = f'{_scope_board_query(room)}&' if room is not None else ''
    return JsonResponse({
        'thread_id': thread.pk,
        'redirect_url': f'{_scope_url(room, "detail")}?{query_prefix}board={board.pk}&thread={thread.pk}',
    })


@never_cache
def account_board_thread_detail(request, username, thread_id):
    account = _board_scope(request, username=username)
    thread = get_object_or_404(
        thread_queryset().filter(
            placements__kind=ThreadPlacement.BOARD,
            placements__board__placement__collection__account=account,
        ),
        pk=thread_id,
    )
    prepare_thread_for_view(thread, request.user)
    return render(request, 'rooms/partials/thread_detail.html', {'thread': thread})


@require_POST
def map_board_create(request):
    form = MapBoardForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'errors': {name: list(errors) for name, errors in form.errors.items()}}, status=400)
    # NiiMap Boards are ownerless. All policy input is validated before the
    # atomic creation completes; there is no management route after saving.
    try:
        board, _ = create_board(
            submission_id=submission_id_from(request.POST.get('submission_id')),
            **form.cleaned_data,
            policy_data=request.POST if (request.POST.get('policy_present') == 'true' or any(
                key.startswith('policy_') and key.endswith('_groups') for key in request.POST
            )) else None,
            actor=request.user,
        )
    except (ValueError, ValidationError) as error:
        return JsonResponse({'error': str(error)}, status=400)
    return JsonResponse({'board_id': board.pk, 'redirect_url': f'{reverse("events:map")}?board={board.pk}'})


@never_cache
def map_board_thread_detail(request, board_id, thread_id):
    board = get_object_or_404(_container_boards(None), pk=board_id)
    thread = get_object_or_404(thread_queryset().filter(placements__kind=ThreadPlacement.BOARD, placements__board=board), pk=thread_id)
    # ThreadPolicy alone controls existing Thread reading and replies.
    prepare_thread_for_view(thread, request.user)
    return render(request, 'rooms/partials/thread_detail.html', {'thread': thread})


def _rated_boards(request, account):
    from accounts.content_lists import describe_target
    from .models import BoardRating
    muted = set(muted_account_ids(request.user))
    muted_boards = set(muted_board_ids(request.user))
    rows = BoardRating.objects.filter(author=account).select_related('target__placement__collection__room').prefetch_related('target__policy_conditions').order_by('-updated_at', '-pk')
    result = {'fav': [], 'bad': []}
    for row in rows:
        if row.target.creator_id not in muted and row.target_id not in muted_boards:
            result[row.sentiment].append(describe_target('board', row.target, request.user))
    return result
