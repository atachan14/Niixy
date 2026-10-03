import uuid
import json
from datetime import date
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.db.models import Max, Prefetch
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.services import account_condition_catalog
from interfaces.models import FieldType
from interfaces.services import (
    expand_field_definition_ids,
    prepare_thread_fields,
    save_thread_fields,
    thread_field_catalog,
    thread_interface_catalog,
)

from .forms import ThreadCreateForm, ThreadPostForm
from .idempotency import run_once, submission_id_from
from .models import Locality, NiiMapFilterPreference, Station, Thread, ThreadAccessRule, ThreadPlacement, ThreadPost


CAPABILITIES = (ThreadAccessRule.VIEW, ThreadAccessRule.WRITE)


def thread_queryset():
    return (
        Thread.objects.select_related('creator__niixy_profile')
        .prefetch_related(
            'access_rules',
            Prefetch('placements', queryset=ThreadPlacement.objects.filter(kind=ThreadPlacement.NII_MAP)),
            Prefetch('posts', queryset=ThreadPost.objects.select_related('creator__niixy_profile')),
            'interface_implementations__version__interface__creator',
            'interface_implementations__values__field',
            'direct_fields__version__definition__creator',
            'direct_fields__binding__value',
            'field_bindings__value',
        )
    )


def map_view(request):
    interface_catalog = thread_interface_catalog()
    field_catalog = thread_field_catalog()
    search_state = {}
    if request.user.is_authenticated:
        preference, _ = NiiMapFilterPreference.objects.get_or_create(user=request.user)
        search_state = preference.search_state
    threads = list(thread_queryset())
    for thread in threads:
        thread.can_view = thread.allows(request.user, ThreadAccessRule.VIEW)
        thread.can_write = thread.allows(request.user, ThreadAccessRule.WRITE)

    markers = []
    for thread in threads:
        for placement in thread.placements.all():
            markers.append({
                'id': thread.pk,
                'title': thread.title,
                'creator_id': thread.creator.username if thread.creator else None,
                'latitude': float(placement.latitude),
                'longitude': float(placement.longitude),
            })

    return render(request, 'events/map.html', {
        'threads': threads,
        'thread_markers': markers,
        'geolonia_api_key': settings.GEOLONIA_API_KEY,
        'thread_submission_id': uuid.uuid4(),
        'rule_capabilities': [
            (ThreadAccessRule.VIEW, '閲覧制限'),
            (ThreadAccessRule.WRITE, '書込制限'),
        ],
        'thread_interface_catalog': interface_catalog,
        'created_thread_interface_catalog': [
            item for item in interface_catalog
            if request.user.is_authenticated and item['creator'] == request.user.username
        ],
        'thread_field_catalog': field_catalog,
        'created_thread_field_catalog': [
            item for item in field_catalog
            if request.user.is_authenticated and item['creator'] == request.user.username
        ],
        'thread_field_types': FieldType.choices,
        'thread_search_default_actor': request.user.username if request.user.is_authenticated else 'Guest',
        'account_condition_catalog': account_condition_catalog(request.user),
        'available_account_condition_catalog': account_condition_catalog(request.user, include_inactive=True),
        'niimap_search_state': search_state,
    })


def healthcheck(request):
    return HttpResponse('ok', content_type='text/plain')


def rules_from_request(request):
    rules = []
    for capability in CAPABILITIES:
        for audience in (ThreadAccessRule.GUEST, ThreadAccessRule.ACCOUNT):
            if request.POST.get(f'{capability}_{audience}') == 'true':
                rules.append(ThreadAccessRule(capability=capability, audience=audience))
    return rules


@require_POST
def thread_create(request):
    submission_id = submission_id_from(request.POST.get('submission_id'))

    form = ThreadCreateForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'errors': {name: list(errors) for name, errors in form.errors.items()}}, status=400)

    try:
        direct_field_ids = [int(value) for value in request.POST.getlist('direct_field_ids')]
        interface_ids = [int(value) for value in request.POST.getlist('interface_ids')]
    except ValueError:
        return JsonResponse({'errors': {'fields': ['FieldまたはInterfaceの指定が正しくありません。']}}, status=400)
    direct_value_lists = {}
    interface_value_lists = {}
    for key in request.POST:
        if key.startswith('direct_field_value_'):
            direct_value_lists[key.removeprefix('direct_field_value_')] = request.POST.getlist(key)
            continue
        if not key.startswith('interface_value_'):
            continue
        _, _, interface_id, field_key = key.split('_', 3)
        try:
            interface_value_lists[(int(interface_id), field_key)] = request.POST.getlist(key)
        except ValueError:
            return JsonResponse({'errors': {'interfaces': ['Interfaceの入力値が正しくありません。']}}, status=400)
    try:
        prepared_direct_fields, prepared_interfaces = prepare_thread_fields(
            direct_field_ids,
            direct_value_lists,
            interface_ids,
            interface_value_lists,
        )
    except ValidationError as error:
        return JsonResponse({'errors': error.message_dict}, status=400)

    def create_thread():
        thread = Thread.objects.create(
                submission_id=submission_id,
                creator=request.user if request.user.is_authenticated else None,
                title=form.cleaned_data['title'],
        )
        ThreadPost.objects.create(thread=thread, number=1, creator=thread.creator, body=form.cleaned_data['body'])
        ThreadPlacement.objects.create(
                thread=thread,
                latitude=form.cleaned_data['latitude'],
                longitude=form.cleaned_data['longitude'],
        )
        ThreadAccessRule.objects.bulk_create([
                ThreadAccessRule(thread=thread, capability=rule.capability, audience=rule.audience)
                for rule in rules_from_request(request)
        ])
        save_thread_fields(thread, prepared_direct_fields, prepared_interfaces)
        return thread

    thread, _ = run_once(Thread, submission_id, create_thread)

    return JsonResponse({'redirect_url': f"{reverse('events:map')}?thread={thread.pk}", 'thread_id': thread.pk})


@require_POST
def thread_post_create(request, thread_id):
    thread = get_object_or_404(Thread.objects.prefetch_related('access_rules'), pk=thread_id)
    if not thread.allows(request.user, ThreadAccessRule.VIEW):
        return JsonResponse({'error': 'このThreadは閲覧できません。'}, status=403)
    if not thread.allows(request.user, ThreadAccessRule.WRITE):
        return JsonResponse({'error': 'このThreadには書き込めません。'}, status=403)

    form = ThreadPostForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'errors': {name: list(errors) for name, errors in form.errors.items()}}, status=400)

    submission_id = submission_id_from(request.POST.get('submission_id'))

    def create_post():
        locked_thread = Thread.objects.select_for_update().get(pk=thread_id)
        number = (locked_thread.posts.aggregate(max_number=Max('number'))['max_number'] or 0) + 1
        post = ThreadPost.objects.create(submission_id=submission_id, thread=locked_thread, number=number, creator=request.user if request.user.is_authenticated else None, body=form.cleaned_data['body'])
        locked_thread.save(update_fields=['last_activity_at', 'updated_at'])
        return post

    run_once(ThreadPost, submission_id, create_post)
    return JsonResponse({'redirect_url': f"{reverse('events:map')}?thread={thread.pk}"})


@require_POST
def filter_preferences_update(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'ログインが必要です。'}, status=401)
    preference, _ = NiiMapFilterPreference.objects.get_or_create(user=request.user)
    fields = ['show_guest_threads', 'account_ids_enabled', 'account_section_open']
    for field in fields:
        setattr(preference, field, request.POST.get(field) == 'true')
    preference.save(update_fields=fields)
    return JsonResponse({'ok': True})


def _json_conditions(request, name):
    try:
        value = json.loads(request.POST.get(name, '[]'))
    except json.JSONDecodeError as error:
        raise ValidationError({name: '検索条件が正しくありません。'}) from error
    if not isinstance(value, list):
        raise ValidationError({name: '検索条件が正しくありません。'})
    return value


def _terms(value):
    return [term.casefold() for term in value.replace(',', ' ').split() if term]


def _creator_matches(thread, term):
    if term in {'guest', '@guest'}:
        return thread.creator_id is None
    return thread.creator is not None and thread.creator.username.casefold() == term.removeprefix('@')


def _account_condition_matches(account, request_user, condition):
    kind = condition.get('kind')
    definition = condition.get('definition') or {}
    if kind == 'account':
        try:
            return account is not None and account.pk == int(definition.get('account_id'))
        except (TypeError, ValueError):
            return False
    if kind != 'default':
        return False
    code = definition.get('code')
    if code == 'guest':
        return account is None
    if code == 'account':
        return account is not None
    if code == 'self':
        return request_user.is_authenticated and account is not None and account.pk == request_user.pk
    return False


def _account_group_matches(account, request_user, group):
    return bool(group) and all(
        _account_condition_matches(account, request_user, condition)
        for condition in group
    )


def _account_groups_match(account, request_user, groups):
    return any(_account_group_matches(account, request_user, group) for group in groups)


def _policy_group_subject(group, request_user):
    account_ids = {
        condition.get('definition', {}).get('account_id')
        for condition in group
        if condition.get('kind') == 'account'
    }
    account_ids.discard(None)
    if len(account_ids) > 1:
        return None, False
    if account_ids:
        try:
            subject = get_user_model().objects.get(pk=int(next(iter(account_ids))))
        except (get_user_model().DoesNotExist, TypeError, ValueError):
            return None, False
        return (subject, True) if _account_group_matches(subject, request_user, group) else (None, False)

    default_codes = {
        condition.get('definition', {}).get('code')
        for condition in group
        if condition.get('kind') == 'default'
    }
    if 'guest' in default_codes:
        return (AnonymousUser(), True) if _account_group_matches(None, request_user, group) else (None, False)
    if 'self' in default_codes and request_user.is_authenticated:
        return (request_user, True) if _account_group_matches(request_user, request_user, group) else (None, False)
    if default_codes == {'account'}:
        return ThreadAccessRule.ACCOUNT, True
    return None, False


def _field_value_matches(value, operator, expected):
    values = value if isinstance(value, list) else [value]
    if operator in {'contains', 'not_contains'}:
        matched = any(expected.casefold() in str(item).casefold() for item in values)
        return not matched if operator == 'not_contains' else matched
    if operator in {'true', 'false'}:
        return bool(value) is (operator == 'true')
    if operator == 'equals':
        return any(str(item).casefold() == expected.casefold() for item in values)
    try:
        actual_number = Decimal(str(value))
        expected_number = Decimal(expected)
        return actual_number >= expected_number if operator == 'gte' else actual_number <= expected_number
    except (InvalidOperation, TypeError, ValueError):
        actual = str(value)
        return actual >= expected if operator == 'gte' else actual <= expected


def _thread_field_values(thread, definition_ids):
    return [
        binding.value.value
        for binding in thread.field_bindings.all()
        if binding.definition_id in definition_ids
    ]


def _policy_matches(thread, user, condition):
    capability = condition.get('capability')
    if capability not in CAPABILITIES:
        return False
    groups = condition.get('account_groups')
    if groups is None:
        actor = condition.get('actor')
        if actor == 'self' and not user.is_authenticated:
            actor = 'guest'
        groups = [[{'kind': 'default', 'definition': {'code': actor}}]]
    if not isinstance(groups, list) or not groups:
        return False
    matches = []
    for group in groups:
        if not isinstance(group, list):
            continue
        subject, valid = _policy_group_subject(group, user)
        if not valid:
            continue
        if subject == ThreadAccessRule.ACCOUNT:
            allowed = any(
                rule.capability == capability and rule.audience == ThreadAccessRule.ACCOUNT
                for rule in thread.access_rules.all()
            )
        else:
            allowed = thread.allows(subject, capability)
        matches.append(allowed if condition.get('decision') == 'allow' else not allowed)
    return any(matches)


@require_POST
def thread_search(request):
    try:
        creator_include_groups = _json_conditions(request, 'creator_include_groups')
        creator_exclude_groups = _json_conditions(request, 'creator_exclude_groups')
        policy_conditions = _json_conditions(request, 'policy_conditions')
        field_conditions = _json_conditions(request, 'field_conditions')
        interface_conditions = _json_conditions(request, 'interface_conditions')
    except ValidationError as error:
        return JsonResponse({'errors': error.message_dict}, status=400)

    threads = list(thread_queryset())
    include_creators = _terms(request.POST.get('creator_include', ''))
    exclude_creators = _terms(request.POST.get('creator_exclude', ''))
    include_words = _terms(request.POST.get('freeword_include', ''))
    exclude_words = _terms(request.POST.get('freeword_exclude', ''))
    updated_value = request.POST.get('updated_value', '').strip()
    updated_operator = request.POST.get('updated_operator', 'after')
    try:
        updated_date = date.fromisoformat(updated_value) if updated_value else None
    except ValueError:
        return JsonResponse({'errors': {'updated_value': ['更新日が正しくありません。']}}, status=400)

    resolved_field_conditions = []
    for condition in field_conditions:
        try:
            definition_id = int(condition.get('field_id'))
        except (TypeError, ValueError):
            return JsonResponse({'errors': {'field_conditions': ['Fieldを選択してください。']}}, status=400)
        resolved_field_conditions.append((condition, expand_field_definition_ids([definition_id])))

    filtered = []
    for thread in threads:
        if creator_include_groups and not _account_groups_match(thread.creator, request.user, creator_include_groups):
            continue
        if creator_exclude_groups and _account_groups_match(thread.creator, request.user, creator_exclude_groups):
            continue
        if not creator_include_groups and include_creators and not any(_creator_matches(thread, term) for term in include_creators):
            continue
        if not creator_exclude_groups and any(_creator_matches(thread, term) for term in exclude_creators):
            continue
        if updated_date:
            thread_date = thread.last_activity_at.date()
            if updated_operator == 'before' and thread_date > updated_date:
                continue
            if updated_operator != 'before' and thread_date < updated_date:
                continue
        can_view = thread.allows(request.user, ThreadAccessRule.VIEW)
        searchable_text = thread.title
        if can_view:
            searchable_text += ' ' + ' '.join(post.body for post in thread.posts.all())
        searchable_text = searchable_text.casefold()
        if any(term not in searchable_text for term in include_words):
            continue
        if any(term in searchable_text for term in exclude_words):
            continue
        if not all(_policy_matches(thread, request.user, condition) for condition in policy_conditions):
            continue
        if (resolved_field_conditions or interface_conditions) and not can_view:
            continue
        field_match = True
        for condition, definition_ids in resolved_field_conditions:
            values = _thread_field_values(thread, definition_ids)
            operator = condition.get('operator', 'contains')
            expected = str(condition.get('value', ''))
            matches = [_field_value_matches(value, operator, expected) for value in values]
            if not values or not (all(matches) if operator == 'not_contains' else any(matches)):
                field_match = False
                break
        if not field_match:
            continue
        implemented_ids = {item.interface_id for item in thread.interface_implementations.all()}
        interface_match = True
        for condition in interface_conditions:
            try:
                interface_id = int(condition.get('interface_id'))
            except (TypeError, ValueError):
                interface_match = False
                break
            if (condition.get('operator') == 'include') != (interface_id in implemented_ids):
                interface_match = False
                break
        if not interface_match:
            continue
        filtered.append(thread)

    sort_kind = request.POST.get('sort_kind', 'updated')
    sort_direction = request.POST.get('sort_direction', 'desc')
    reverse = sort_direction != 'asc'
    if sort_kind == 'field':
        try:
            sort_field_ids = expand_field_definition_ids([int(request.POST.get('sort_field_id'))])
        except (TypeError, ValueError):
            return JsonResponse({'errors': {'sort_field_id': ['並び替えに使うFieldを選択してください。']}}, status=400)

        def sortable_field_values(thread):
            if not thread.allows(request.user, ThreadAccessRule.VIEW):
                return []
            return _thread_field_values(thread, sort_field_ids)

        def field_sort_key(thread):
            values = sortable_field_values(thread)
            return (not values, str(values[0]).casefold() if values else '')

        present = [thread for thread in filtered if sortable_field_values(thread)]
        missing = [thread for thread in filtered if not sortable_field_values(thread)]
        filtered = sorted(present, key=field_sort_key, reverse=reverse) + missing
    elif sort_kind == 'updated':
        filtered.sort(key=lambda thread: (thread.last_activity_at, thread.pk), reverse=reverse)

    if request.user.is_authenticated:
        preference, _ = NiiMapFilterPreference.objects.get_or_create(user=request.user)
        preference.search_state = {
            'sort_kind': sort_kind,
            'sort_direction': sort_direction,
            'target_type': request.POST.get('target_type', 'all'),
            'updated_value': updated_value,
            'updated_operator': updated_operator,
            'freeword_include': request.POST.get('freeword_include', ''),
            'freeword_exclude': request.POST.get('freeword_exclude', ''),
            'sort_field_id': request.POST.get('sort_field_id', ''),
            'conditions': {
                'creator_include_groups': creator_include_groups,
                'creator_exclude_groups': creator_exclude_groups,
                'policy': policy_conditions,
                'fields': field_conditions,
                'interfaces': interface_conditions,
            },
        }
        preference.save(update_fields=['search_state'])

    return JsonResponse({'thread_ids': [thread.pk for thread in filtered], 'count': len(filtered)})


def location_search(request):
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'locations': []})
    stations = Station.objects.filter(name__icontains=query)[:5]
    localities = Locality.objects.filter(full_name__icontains=query)[:5]
    locations = [
        {'name': station.name, 'detail': f'{station.line_name} / {station.operator_name}', 'latitude': float(station.latitude), 'longitude': float(station.longitude)}
        for station in stations
    ]
    locations.extend(
        {'name': locality.name, 'detail': locality.detail, 'latitude': float(locality.latitude), 'longitude': float(locality.longitude)}
        for locality in localities
    )
    return JsonResponse({'locations': locations})
