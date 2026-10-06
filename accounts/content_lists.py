"""Public BoardList / InterfaceList references without placement or application rights."""
from dataclasses import dataclass
from uuid import uuid4
from urllib.parse import urlencode

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
from events.models import Thread, ThreadPost, ThreadAccessRule, ThreadList, ResponseList, ThreadListReference, ResponseListReference, ThreadRating, ResponseRating
from events.services import thread_queryset, prepare_thread_for_view
from rooms.mutes import muted_thread_ids
from interfaces.models import (
    Interface, InterfaceList, InterfaceListReference, InterfaceRating,
    FieldDefinition, FieldListReference, FieldRating, AccountLayout, LayoutListReference, LayoutRating,
)
from rooms.models import Board, BoardPlacement, BoardPolicyCondition, BoardListReference, BoardRating, Collection
from .internal_urls import resolve_internal_url
from .lists import invalid, login_denied, url_error
from .mutes import filter_muted, muted_account_ids
from rooms.mutes import muted_board_ids
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
    'thread': ListKind('ThreadList', ThreadList, ThreadListReference, ThreadRating, 'owner', 'thread_list', 'submission_id', 80),
    'response': ListKind('ResponseList', ResponseList, ResponseListReference, ResponseRating, 'owner', 'response_list', 'submission_id', 80),
    'board': ListKind('BoardList', Collection, BoardListReference, BoardRating, 'account', 'board_list', 'list_submission_id', 120),
    'interface': ListKind('ModuleList', InterfaceList, InterfaceListReference, InterfaceRating, 'owner', 'interface_list', 'submission_id', 80),
    'field': ListKind('ModuleList', InterfaceList, FieldListReference, FieldRating, 'owner', 'interface_list', 'submission_id', 80),
    'layout': ListKind('ModuleList', InterfaceList, LayoutListReference, LayoutRating, 'owner', 'interface_list', 'submission_id', 80),
}

MODULE_KINDS = ('interface', 'field', 'layout')


def route(kind, action, *args):
    if kind in MODULE_KINDS and action.startswith('list-') and action != 'list-remove':
        kind = 'interface'
    return reverse('references:' + kind + '-' + action, args=args)


def list_query(kind):
    query = KINDS[kind].model.objects.all()
    if kind == 'board':
        query = query.filter(account__isnull=False, room__isnull=True)
    return query


def public_interfaces():
    return Interface.objects.filter(status=Interface.ACTIVE, current_version__isnull=False, current_version__interface_id=F('pk')).select_related('creator__niixy_profile', 'current_version')


def public_modules(kind):
    if kind == 'interface':
        return public_interfaces()
    model, version_parent = (FieldDefinition, 'definition') if kind == 'field' else (AccountLayout, 'layout')
    query = model.objects.filter(current_version__isnull=False, **{'current_version__' + version_parent + '_id': F('pk')})
    if kind == 'field':
        query = query.filter(status=FieldDefinition.ACTIVE)
    return query.select_related('creator__niixy_profile', 'current_version')


def module_is_public(kind, target):
    if not target.current_version_id:
        return False
    parent = {'interface': 'interface_id', 'field': 'definition_id', 'layout': 'layout_id'}[kind]
    return getattr(target.current_version, parent) == target.pk and (kind == 'layout' or target.status == 'active')


def target_kind(target):
    return 'field' if isinstance(target, FieldDefinition) else 'layout' if isinstance(target, AccountLayout) else 'interface'


def reference_count(item, kind):
    if kind not in MODULE_KINDS:
        return item.references.count()
    return sum(getattr(item, relation).count() for relation in ('references', 'field_references', 'layout_references'))


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


def conversation_can_view(kind, target, user):
    thread = target if kind == 'thread' else target.thread
    return thread.allows(user, ThreadAccessRule.VIEW)


def conversation_is_muted(kind, target, user):
    muted = set(muted_account_ids(user))
    if kind == 'thread':
        return target.creator_id in muted or target.pk in set(muted_thread_ids(user))
    return target.creator_id in muted or target.thread.creator_id in muted


def get_target(kind, target_id, user, *, require_view=True):
    if kind in {'thread', 'response'}:
        query = thread_queryset() if kind == 'thread' else ThreadPost.objects.filter(number__gt=1).select_related('thread', 'creator__niixy_profile').prefetch_related('thread__access_rules', 'thread__policy_conditions')
        target = get_object_or_404(query, pk=target_id)
        if require_view and not conversation_can_view(kind, target, user):
            raise PermissionDenied
        return target
    if kind in MODULE_KINDS:
        return get_object_or_404(public_modules(kind), pk=target_id)
    board = get_object_or_404(Board.objects.select_related('placement__collection__room').prefetch_related('policy_conditions'), pk=target_id)
    if require_view and not board_can_view(board, user):
        raise PermissionDenied
    return board


def resolve_target(request, kind, value):
    resolved = resolve_internal_url(request, value)
    if resolved.kind != kind and not (kind in MODULE_KINDS and resolved.kind in MODULE_KINDS):
        raise ValidationError('追加対象の正規URLを入力してください。他の種類やListは追加できません。')
    return get_target(resolved.kind, resolved.instance.pk, request.user)


def describe_target(kind, target, user):
    if kind in {'thread', 'response'}:
        if conversation_is_muted(kind, target, user):
            return None
        thread = target if kind == 'thread' else target.thread
        visible = conversation_can_view(kind, target, user)
        return {'kind': kind, 'name': thread.title, 'url': route(kind, 'page', target.pk),
                'context': ('Thread' if kind == 'thread' else 'Response #' + str(target.number)) if visible else '閲覧不可',
                'updated_at': thread.last_activity_at if kind == 'thread' or not visible else target.created_at}
    if kind in MODULE_KINDS:
        if not module_is_public(kind, target):
            return None
        label = target.get_kind_display() if kind == 'interface' else 'Field' if kind == 'field' else 'AccountLayout'
        return {'name': target.current_version.name, 'url': route(kind, 'page', target.pk),
                'context': label + ' · 公開定義 v' + str(target.current_version.version_number), 'updated_at': target.updated_at,
                'kind': kind, 'module_type': {'field': 'element', 'interface': 'interface', 'layout': 'layout'}[kind],
                'module_subtype': target.kind if kind == 'interface' else 'field' if kind == 'field' else 'account'}
    return {'kind': 'board', 'name': target.name, 'url': route(kind, 'page', target.pk),
            'context': '' if board_can_view(target, user) else '閲覧不可', 'updated_at': target.last_activity_at}


def prepare_list(kind, item):
    spec = KINDS[kind]
    item.page_url = route(kind, 'list-page', item.pk)
    item.add_url = route(kind, 'list-add', item.pk)
    item.owner_account = getattr(item, spec.owner_field)
    return item


def index_context(request, kind, account):
    spec = KINDS[kind]
    query = list_query(kind).filter(**{spec.owner_field: account}).order_by('created_at', 'pk')
    page = paginate_summary_list(query, request.GET.get('page'))
    for item in page:
        prepare_list(kind, item)
        item.reference_count = reference_count(item, kind)
    return {'kind': kind, 'list_label': spec.label, 'account': account, 'summary_page': page,
            'is_list_owner': request.user.pk == account.pk, 'submission_id': uuid4(), 'max_length': spec.max_length,
            'create_url': route(kind, 'list-create'), 'summary_page_url': route(kind, 'list-index', account.username),
            'summary_page_label': spec.label + '一覧のページ'}


@require_GET
@never_cache
def listing(request, kind, username):
    account = target_account(username)
    context = index_context(request, kind, account)
    return render(request, 'shared/content_list_index.html', context)


@require_GET
@never_cache
def picker(request, kind, target_id):
    denied = login_denied(request)
    if denied:
        return denied
    target = get_target(kind, target_id, request.user)
    context = index_context(request, 'interface' if kind in MODULE_KINDS else kind, request.user)
    context.update(target=describe_target(kind, target, request.user), target_url=route(kind, 'page', target.pk),
                   summary_page_url=route(kind, 'picker', target.pk))
    return render(request, 'shared/content_list_picker.html', context)


@require_GET
@never_cache
def detail(request, kind, list_id):
    spec = KINDS[kind]
    item = prepare_list(kind, get_object_or_404(list_query(kind).select_related(spec.owner_field + '__niixy_profile'), pk=list_id))
    references = []
    muted = set(muted_account_ids(request.user))
    muted_boards = set(muted_board_ids(request.user)) if kind == 'board' else set()
    for ref_kind in (MODULE_KINDS if kind in MODULE_KINDS else (kind,)):
        query = KINDS[ref_kind].reference.objects.filter(**{KINDS[ref_kind].list_field: item}).select_related('target')
        if ref_kind == 'board':
            query = query.select_related('target__placement__collection__room').prefetch_related('target__policy_conditions')
        elif ref_kind in MODULE_KINDS:
            query = query.select_related('target__current_version')
        elif ref_kind == 'thread':
            query = query.prefetch_related('target__access_rules', 'target__policy_conditions')
        else:
            query = query.select_related('target__thread').prefetch_related('target__thread__access_rules', 'target__thread__policy_conditions')
        for ref in query:
            if ref.target and (ref.target.creator_id in muted or (ref_kind == 'board' and ref.target_id in muted_boards)):
                continue
            if ref.target and ref_kind in {'thread', 'response'} and conversation_is_muted(ref_kind, ref.target, request.user):
                continue
            ref.summary = describe_target(ref_kind, ref.target, request.user) if ref.target else None
            # A filtered Module tab shows only matching published definitions.
            if request.GET.get('type'):
                if not ref.summary or ref.summary.get('module_type') != request.GET['type'] or ref.summary.get('module_subtype') != request.GET.get('subtype'):
                    continue
            ref.remove_url = route(ref_kind, 'list-remove', list_id, ref.pk)
            references.append(ref)
    references.sort(key=lambda ref: (ref.created_at, ref.pk))
    page = paginate_summary_list(references, request.GET.get('page'))
    placed = []
    if kind == 'board':
        boards = Board.objects.filter(placement__collection=item).select_related('placement__collection__room').prefetch_related('policy_conditions')
        boards = filter_muted(boards, request.user)
        placed = [describe_target(kind, board, request.user) for board in boards]
    return render(request, 'shared/content_list_detail.html', {
        'kind': kind, 'list_label': spec.label, 'target_label': {'board':'Board', 'thread':'Thread', 'response':'Response'}.get(kind, 'Module'), 'content_list': item, 'placed_boards': placed,
        'is_list_owner': request.user.pk == item.owner_account.pk, 'max_length': spec.max_length,
        'can_manage_name': kind != 'board' or not item.is_uncategorized,
        'add_url': item.add_url, 'rename_url': route(kind, 'list-rename', list_id), 'delete_url': route(kind, 'list-delete', list_id),
        'summary_page': page, 'summary_page_query': urlencode({'type': request.GET['type'], 'subtype': request.GET.get('subtype', '')}) if request.GET.get('type') else '',
        'list_fetch_url': request.get_full_path(), 'summary_page_url': route(kind, 'list-detail', list_id), 'summary_page_label': spec.label + '参照のページ',
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
        KINDS[target_kind(target) if kind in MODULE_KINDS else kind].reference.objects.get_or_create(**{spec.list_field: item, 'target': target})
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
    _, created = KINDS[target_kind(target) if kind in MODULE_KINDS else kind].reference.objects.get_or_create(**{spec.list_field: item, 'target': target})
    return JsonResponse({'ok': True, 'kind': kind, 'list_id': list_id, 'added': created, 'reference_count': reference_count(item, kind)})


@require_POST
def remove(request, kind, list_id, reference_id):
    denied = login_denied(request)
    if denied:
        return denied
    item = owned_list(request, kind, list_id)
    spec = KINDS[kind]
    spec.reference.objects.filter(**{spec.list_field: item}, pk=reference_id).delete()
    return JsonResponse({'ok': True, 'kind': 'interface' if kind in MODULE_KINDS else kind, 'list_id': list_id, 'reference_count': reference_count(item, kind)})


def feedback_context(kind, target, user):
    rating = KINDS[kind].rating
    counts = {row['sentiment']: row['count'] for row in rating.objects.filter(target=target).values('sentiment').annotate(count=Count('pk'))}
    sentiment = rating.objects.filter(target=target, author=user).values_list('sentiment', flat=True).first() if user.is_authenticated else ''
    return {'kind': kind, 'target_id': target.pk, 'sentiment': sentiment or '', 'fav_count': counts.get('fav', 0), 'bad_count': counts.get('bad', 0),
            'rating_url': route(kind, 'rating', target.pk), 'picker_url': route(kind, 'picker', target.pk), 'ratings_url': route(kind, 'ratings', target.pk),
            'can_rate': user.is_authenticated, 'target_url': route(kind, 'page', target.pk)}


@require_POST
@transaction.atomic
def rate(request, kind, target_id):
    denied = login_denied(request)
    if denied:
        return denied
    form = type('RatingForm', (forms.Form,), {'sentiment': forms.ChoiceField(required=False, choices=[('', ''), ('fav', 'fav'), ('bad', 'bad')])})(request.POST)
    if not form.is_valid():
        return invalid(form)
    model = {'board': Board, 'interface': Interface, 'field': FieldDefinition, 'layout': AccountLayout, 'thread': Thread, 'response': ThreadPost}[kind]
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
    if kind in {'thread', 'response'}:
        target = get_target(kind, target_id, request.user, require_view=False)
        thread = target if kind == 'thread' else get_object_or_404(thread_queryset(), pk=target.thread_id)
        prepare_thread_for_view(thread, request.user)
        return render(request, 'events/partials/thread_detail.html', {'thread':thread,
                      'target_post_number':target.number if kind == 'response' and thread.can_view else None})
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
    if kind == 'field':
        return render(request, 'interfaces/field_detail_pane.html', {'field_item': target, 'profile_mode': True})
    if kind == 'layout':
        from interfaces.layout_views import detail as layout_detail
        return layout_detail(request, target_id)
    return render(request, 'shared/public_interface.html', {'interface_item': target})


@require_GET
@never_cache
def target_page(request, kind, target_id):
    response = target_pane(request, kind, target_id)
    target = get_target(kind, target_id, request.user, require_view=False)
    title = target.title if kind == 'thread' else target.thread.title if kind == 'response' else target.name if kind == 'board' else target.current_version.name
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
