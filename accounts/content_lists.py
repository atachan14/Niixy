"""Public BoardList / InterfaceList references without placement or application rights."""
from dataclasses import dataclass
from uuid import uuid4

from django import forms
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, F
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from config.pagination import paginate_summary_list
from interfaces.models import Interface, InterfaceList, InterfaceListReference, InterfaceRating
from rooms.models import Board, BoardPlacement, BoardPolicyCondition, BoardListReference, BoardRating, Collection
from .internal_urls import resolve_internal_url
from .lists import invalid, login_denied, url_error
from .mutes import muted_account_ids
from .reviews import target_account


@dataclass(frozen=True)
class ListKind:
    label: str
    model: object
    reference: object
    rating: object
    owner_field: str
    list_field: str
    token_field: str
    max_length: int


KINDS = {
    'board': ListKind('BoardList', Collection, BoardListReference, BoardRating, 'account', 'board_list', 'list_submission_id', 120),
    'interface': ListKind('InterfaceList', InterfaceList, InterfaceListReference, InterfaceRating, 'owner', 'interface_list', 'submission_id', 80),
}


def route(kind, action, *args):
    return reverse('references:' + kind + '-' + action, args=args)


def list_query(kind):
    query = KINDS[kind].model.objects.all()
    if kind == 'board':
        query = query.filter(account__isnull=False, room__isnull=True)
    return query


def public_interfaces():
    return Interface.objects.filter(status=Interface.ACTIVE, current_version__isnull=False, current_version__interface_id=F('pk')).select_related('creator__niixy_profile', 'current_version')


def board_can_view(board, user):
    try:
        placement = board.placement
    except BoardPlacement.DoesNotExist:
        return False
    owner_id = None
    if placement.collection_id:
        container = placement.collection
        owner_id = container.account_id or container.room.owner_id
    return bool(user.is_authenticated and owner_id == user.pk) or board.evaluate_policy(user, BoardPolicyCondition.VIEW).allowed


def get_target(kind, target_id, user, *, require_view=True):
    if kind == 'interface':
        return get_object_or_404(public_interfaces(), pk=target_id)
    board = get_object_or_404(Board.objects.select_related('placement__collection__room').prefetch_related('policy_conditions'), pk=target_id)
    if require_view and not board_can_view(board, user):
        raise PermissionDenied
    return board


def resolve_target(request, kind, value):
    resolved = resolve_internal_url(request, value)
    if resolved.kind != kind:
        raise ValidationError('追加対象の正規URLを入力してください。他の種類やListは追加できません。')
    return get_target(kind, resolved.instance.pk, request.user)


def describe_target(kind, target, user):
    if kind == 'interface':
        if target.status != Interface.ACTIVE or not target.current_version_id or target.current_version.interface_id != target.pk:
            return None
        return {'name': target.current_version.name, 'url': route(kind, 'page', target.pk),
                'context': target.get_kind_display() + ' · 公開定義 v' + str(target.current_version.version_number), 'updated_at': target.updated_at}
    return {'name': target.name, 'url': route(kind, 'page', target.pk),
            'context': '' if board_can_view(target, user) else '閲覧不可', 'updated_at': target.last_activity_at}


def prepare_list(kind, item):
    spec = KINDS[kind]
    item.page_url = route(kind, 'list-page', item.pk)
    item.add_url = route(kind, 'list-add', item.pk)
    item.owner_account = getattr(item, spec.owner_field)
    return item


def index_context(request, kind, account):
    spec = KINDS[kind]
    query = list_query(kind).filter(**{spec.owner_field: account}).annotate(reference_count=Count('references')).order_by('created_at', 'pk')
    page = paginate_summary_list(query, request.GET.get('page'))
    for item in page:
        prepare_list(kind, item)
    return {'kind': kind, 'list_label': spec.label, 'account': account, 'summary_page': page,
            'is_list_owner': request.user.pk == account.pk, 'submission_id': uuid4(), 'max_length': spec.max_length,
            'create_url': route(kind, 'list-create'), 'summary_page_url': route(kind, 'list-index', account.username),
            'summary_page_label': spec.label + '一覧のページ'}


@require_GET
@never_cache
def listing(request, kind, username):
    account = target_account(username)
    context = index_context(request, kind, account)
    if kind == 'interface':
        # AccountPage shows published definitions only; private drafts and the
        # separate Module management UI keep their existing authorization.
        interfaces = public_interfaces().filter(creator=account).order_by('current_version__name', 'pk')
        if request.user.is_authenticated:
            interfaces = interfaces.exclude(creator_id__in=muted_account_ids(request.user))
        context['own_interfaces'] = [describe_target(kind, item, request.user) for item in interfaces]
        return render(request, 'accounts/partials/interface_lists.html', context)
    return render(request, 'shared/content_list_index.html', context)


@require_GET
@never_cache
def picker(request, kind, target_id):
    denied = login_denied(request)
    if denied:
        return denied
    target = get_target(kind, target_id, request.user)
    context = index_context(request, kind, request.user)
    context.update(target=describe_target(kind, target, request.user), target_url=route(kind, 'page', target.pk),
                   summary_page_url=route(kind, 'picker', target.pk))
    return render(request, 'shared/content_list_picker.html', context)


@require_GET
@never_cache
def detail(request, kind, list_id):
    spec = KINDS[kind]
    item = prepare_list(kind, get_object_or_404(list_query(kind).select_related(spec.owner_field + '__niixy_profile'), pk=list_id))
    references = item.references.select_related('target')
    if kind == 'board':
        references = references.select_related('target__placement__collection__room').prefetch_related('target__policy_conditions')
    else:
        references = references.select_related('target__current_version')
    if request.user.is_authenticated:
        references = references.exclude(target__creator_id__in=muted_account_ids(request.user))
    page = paginate_summary_list(references, request.GET.get('page'))
    for ref in page:
        ref.summary = describe_target(kind, ref.target, request.user) if ref.target else None
        ref.remove_url = route(kind, 'list-remove', list_id, ref.pk)
    placed = []
    if kind == 'board':
        boards = Board.objects.filter(placement__collection=item).select_related('placement__collection__room').prefetch_related('policy_conditions')
        if request.user.is_authenticated:
            boards = boards.exclude(creator_id__in=muted_account_ids(request.user))
        placed = [describe_target(kind, board, request.user) for board in boards]
    return render(request, 'shared/content_list_detail.html', {
        'kind': kind, 'list_label': spec.label, 'target_label': 'Board' if kind == 'board' else 'Interface', 'content_list': item, 'placed_boards': placed,
        'is_list_owner': request.user.pk == item.owner_account.pk, 'max_length': spec.max_length,
        'can_manage_name': kind != 'board' or not item.is_uncategorized,
        'add_url': item.add_url, 'rename_url': route(kind, 'list-rename', list_id), 'delete_url': route(kind, 'list-delete', list_id),
        'summary_page': page, 'summary_page_url': route(kind, 'list-detail', list_id), 'summary_page_label': spec.label + '参照のページ',
    })


@require_GET
@never_cache
def list_page(request, kind, list_id):
    item = prepare_list(kind, get_object_or_404(list_query(kind), pk=list_id))
    return render(request, 'shared/reference_page.html', {'title': item.name, 'direct_list_url': item.page_url})


def owned_list(request, kind, list_id):
    return get_object_or_404(list_query(kind), pk=list_id, **{KINDS[kind].owner_field: request.user})


def name_form(kind, data, *, create=False):
    fields = {'name': forms.CharField(max_length=KINDS[kind].max_length, strip=True)}
    if create:
        fields.update(submission_id=forms.UUIDField(), target_url=forms.CharField(required=False, max_length=2048))
    return type('ContentListForm', (forms.Form,), fields)(data)


@require_POST
@transaction.atomic
def create(request, kind):
    denied = login_denied(request)
    if denied:
        return denied
    form = name_form(kind, request.POST, create=True)
    if not form.is_valid():
        return invalid(form)
    data = form.cleaned_data
    try:
        target = resolve_target(request, kind, data['target_url']) if data['target_url'] else None
    except ValidationError as error:
        return url_error(error)
    spec = KINDS[kind]
    item, created = list_query(kind).get_or_create(**{spec.owner_field: request.user, spec.token_field: data['submission_id']}, defaults={'name': data['name']})
    if target:
        spec.reference.objects.get_or_create(**{spec.list_field: item, 'target': target})
    return JsonResponse({'ok': True, 'kind': kind, 'list_id': item.pk, 'url': route(kind, 'list-page', item.pk),
                         'index_url': route(kind, 'list-index', request.user.username)}, status=201 if created else 200)


@require_POST
def rename(request, kind, list_id):
    denied = login_denied(request)
    if denied:
        return denied
    item = owned_list(request, kind, list_id)
    if kind == 'board' and item.is_uncategorized:
        return JsonResponse({'error': '未分類BoardListは編集できません。'}, status=400)
    form = name_form(kind, request.POST)
    if not form.is_valid():
        return invalid(form)
    item.name = form.cleaned_data['name']
    item.save(update_fields=['name', 'updated_at'])
    return JsonResponse({'ok': True, 'kind': kind, 'list_id': item.pk, 'name': item.name})


@require_POST
def delete(request, kind, list_id):
    denied = login_denied(request)
    if denied:
        return denied
    item = owned_list(request, kind, list_id)
    if kind == 'board':
        if item.is_uncategorized:
            return JsonResponse({'error': '未分類BoardListは削除できません。'}, status=400)
        from rooms.services import delete_collection
        delete_collection(item)
    else:
        item.delete()
    return JsonResponse({'ok': True, 'kind': kind, 'list_id': list_id, 'deleted': True})


@require_POST
def add(request, kind, list_id):
    denied = login_denied(request)
    if denied:
        return denied
    item = owned_list(request, kind, list_id)
    form = type('ReferenceForm', (forms.Form,), {'target_url': forms.CharField(max_length=2048)})(request.POST)
    if not form.is_valid():
        return invalid(form)
    try:
        target = resolve_target(request, kind, form.cleaned_data['target_url'])
    except ValidationError as error:
        return url_error(error)
    spec = KINDS[kind]
    _, created = spec.reference.objects.get_or_create(**{spec.list_field: item, 'target': target})
    return JsonResponse({'ok': True, 'kind': kind, 'list_id': list_id, 'added': created, 'reference_count': item.references.count()})


@require_POST
def remove(request, kind, list_id, reference_id):
    denied = login_denied(request)
    if denied:
        return denied
    item = owned_list(request, kind, list_id)
    item.references.filter(pk=reference_id).delete()
    return JsonResponse({'ok': True, 'kind': kind, 'list_id': list_id, 'reference_count': item.references.count()})


def feedback_context(kind, target, user):
    rating = KINDS[kind].rating
    counts = {row['sentiment']: row['count'] for row in rating.objects.filter(target=target).values('sentiment').annotate(count=Count('pk'))}
    sentiment = rating.objects.filter(target=target, author=user).values_list('sentiment', flat=True).first() if user.is_authenticated else ''
    return {'kind': kind, 'target_id': target.pk, 'sentiment': sentiment or '', 'fav_count': counts.get('fav', 0), 'bad_count': counts.get('bad', 0),
            'rating_url': route(kind, 'rating', target.pk), 'picker_url': route(kind, 'picker', target.pk), 'ratings_url': route(kind, 'ratings', target.pk),
            'can_rate': user.is_authenticated}


@require_POST
@transaction.atomic
def rate(request, kind, target_id):
    denied = login_denied(request)
    if denied:
        return denied
    form = type('RatingForm', (forms.Form,), {'sentiment': forms.ChoiceField(required=False, choices=[('', ''), ('fav', 'fav'), ('bad', 'bad')])})(request.POST)
    if not form.is_valid():
        return invalid(form)
    model = Board if kind == 'board' else Interface
    get_object_or_404(model.objects.select_for_update(), pk=target_id)
    target = get_target(kind, target_id, request.user)
    rating = KINDS[kind].rating
    sentiment = form.cleaned_data['sentiment']
    if sentiment:
        rating.objects.update_or_create(author=request.user, target=target, defaults={'sentiment': sentiment})
    else:
        rating.objects.filter(author=request.user, target=target).delete()
    context = feedback_context(kind, target, request.user)
    return JsonResponse({key: context[key] for key in ['kind', 'target_id', 'sentiment', 'fav_count', 'bad_count']})


@require_GET
@never_cache
def ratings(request, kind, target_id):
    target = get_target(kind, target_id, request.user)
    sentiment = request.GET.get('sentiment', 'fav')
    if sentiment not in {'fav', 'bad'}:
        raise Http404
    query = KINDS[kind].rating.objects.filter(target=target, sentiment=sentiment).select_related('author__niixy_profile').order_by('-updated_at', '-pk')
    return render(request, 'shared/content_ratings.html', {'kind': kind, 'target_id': target_id, 'sentiment': sentiment,
        'summary_page': paginate_summary_list(query, request.GET.get('page')), 'summary_page_query': 'sentiment=' + sentiment,
        'summary_page_url': route(kind, 'ratings', target_id), 'summary_page_label': '公開評価のページ'})


@require_GET
@never_cache
def target_pane(request, kind, target_id):
    if kind == 'board':
        from rooms.views import board_threads
        target = get_target(kind, target_id, request.user, require_view=False)
        try:
            placement = target.placement
        except BoardPlacement.DoesNotExist:
            raise Http404 from None
        kwargs = {}
        if placement.collection_id:
            collection = placement.collection
            kwargs = {'username': collection.account.username} if collection.account_id else {'room_id': collection.room_id}
        return board_threads(request, target_id, **kwargs)
    target = get_target(kind, target_id, request.user)
    return render(request, 'shared/public_interface.html', {'interface_item': target})


@require_GET
@never_cache
def target_page(request, kind, target_id):
    response = target_pane(request, kind, target_id)
    target = get_target(kind, target_id, request.user, require_view=False)
    title = target.name if kind == 'board' else target.current_version.name
    from interfaces.services import thread_field_catalog, thread_interface_catalog
    return render(request, 'shared/reference_page.html', {'title': title, 'content_html': mark_safe(response.content.decode()),
        'kind': kind, 'target_id': target_id, 'thread_field_catalog': thread_field_catalog() if kind == 'board' and board_can_view(target, request.user) else [],
        'thread_interface_catalog': thread_interface_catalog() if kind == 'board' and board_can_view(target, request.user) else []})


@require_GET
@never_cache
def target_thread(request, kind, target_id, thread_id):
    if kind != 'board':
        raise Http404
    from rooms.views import account_board_thread_detail, room_thread_detail, map_board_thread_detail
    target = get_target(kind, target_id, request.user)
    placement = target.placement
    if not placement.collection_id:
        return map_board_thread_detail(request, target_id, thread_id)
    # Scope to this Board too, rather than any Thread in its container.
    from events.models import ThreadPlacement
    if not ThreadPlacement.objects.filter(board=target, thread_id=thread_id).exists():
        raise Http404
    collection = placement.collection
    if collection.account_id:
        return account_board_thread_detail(request, collection.account.username, thread_id)
    return room_thread_detail(request, collection.room_id, thread_id)
