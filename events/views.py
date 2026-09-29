import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Max, Prefetch
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from interfaces.services import prepare_thread_interfaces, save_thread_interfaces, thread_interface_catalog

from .forms import ThreadCreateForm, ThreadPostForm
from .idempotency import run_once, submission_id_from
from .models import Locality, NiiMapFilterPreference, Station, Thread, ThreadAccessRule, ThreadPlacement, ThreadPost


CAPABILITIES = (ThreadAccessRule.DISCOVER, ThreadAccessRule.VIEW, ThreadAccessRule.WRITE)


def map_view(request):
    interface_catalog = thread_interface_catalog()
    threads = list(
        Thread.objects.select_related('creator__niixy_profile')
        .prefetch_related(
            'access_rules',
            Prefetch('placements', queryset=ThreadPlacement.objects.filter(kind=ThreadPlacement.NII_MAP)),
            Prefetch('posts', queryset=ThreadPost.objects.select_related('creator__niixy_profile')),
            'interface_implementations__version__interface__creator',
            'interface_implementations__values__field',
        )
    )
    threads = [thread for thread in threads if thread.allows(request.user, ThreadAccessRule.DISCOVER)]
    for thread in threads:
        thread.can_view = thread.allows(request.user, ThreadAccessRule.VIEW)
        thread.can_write = thread.allows(request.user, ThreadAccessRule.WRITE)

    preferences = {'show_guest_threads': True, 'account_ids_enabled': False, 'account_section_open': False}
    if request.user.is_authenticated:
        preference, _ = NiiMapFilterPreference.objects.get_or_create(user=request.user)
        preferences = {
            'show_guest_threads': preference.show_guest_threads,
            'account_ids_enabled': preference.account_ids_enabled,
            'account_section_open': preference.account_section_open,
        }

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
        'filter_preferences': preferences,
        'default_account_filter_id': request.user.username if request.user.is_authenticated else '',
        'geolonia_api_key': settings.GEOLONIA_API_KEY,
        'thread_submission_id': uuid.uuid4(),
        'rule_capabilities': [
            (ThreadAccessRule.DISCOVER, '発見制限'),
            (ThreadAccessRule.VIEW, '閲覧制限'),
            (ThreadAccessRule.WRITE, '書込制限'),
        ],
        'thread_interface_catalog': interface_catalog,
        'created_thread_interface_catalog': [
            item for item in interface_catalog
            if request.user.is_authenticated and item['creator'] == request.user.username
        ],
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
        interface_ids = [int(value) for value in request.POST.getlist('interface_ids')]
    except ValueError:
        return JsonResponse({'errors': {'interfaces': ['Interfaceの指定が正しくありません。']}}, status=400)
    value_lists = {}
    for key in request.POST:
        if not key.startswith('interface_value_'):
            continue
        _, _, interface_id, field_key = key.split('_', 3)
        try:
            value_lists[(int(interface_id), field_key)] = request.POST.getlist(key)
        except ValueError:
            return JsonResponse({'errors': {'interfaces': ['Interfaceの入力値が正しくありません。']}}, status=400)
    try:
        prepared_interfaces = prepare_thread_interfaces(interface_ids, value_lists)
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
        save_thread_interfaces(thread, prepared_interfaces)
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
