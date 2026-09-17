import uuid

from django.contrib import messages
from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import EventForm
from .models import Event, Locality, NiiMapFilterPreference, Station


def map_view(request):
    events = Event.objects.select_related('creator')
    filter_preferences = {
        'range_filter_enabled': True,
        'show_ongoing': False,
        'show_today': False,
        'show_tomorrow': False,
        'show_ended': False,
        'show_guest_events': True,
        'account_ids_enabled': False,
        'datetime_section_open': False,
        'account_section_open': False,
    }
    if request.user.is_authenticated:
        preference, _ = NiiMapFilterPreference.objects.get_or_create(user=request.user)
        filter_preferences = {
            'range_filter_enabled': preference.range_filter_enabled,
            'show_ongoing': preference.show_ongoing,
            'show_today': preference.show_today,
            'show_tomorrow': preference.show_tomorrow,
            'show_ended': preference.show_ended,
            'show_guest_events': preference.show_guest_events,
            'account_ids_enabled': preference.account_ids_enabled,
            'datetime_section_open': preference.datetime_section_open,
            'account_section_open': preference.account_section_open,
        }
    event_markers = [
        {
            'id': event.pk,
            'starts_at': event.starts_at.isoformat(),
            'ends_at': event.ends_at.isoformat() if event.ends_at else None,
            'title': event.title,
            'description': event.description,
            'capacity': event.capacity,
            'creator_id': event.creator.username if event.creator else None,
            'latitude': float(event.latitude),
            'longitude': float(event.longitude),
        }
        for event in events
    ]
    return render(
        request,
        'events/map.html',
        {
            'events': events,
            'event_markers': event_markers,
            'filter_preferences': filter_preferences,
            'default_account_filter_id': request.user.username if request.user.is_authenticated else '',
            'geolonia_api_key': settings.GEOLONIA_API_KEY,
            'event_submission_id': uuid.uuid4(),
        },
    )


def healthcheck(request):
    return HttpResponse('ok', content_type='text/plain')


def event_create(request):
    if request.method != 'POST':
        return redirect('events:map')

    try:
        submission_id = uuid.UUID(request.POST.get('submission_id', ''))
    except (TypeError, ValueError):
        submission_id = uuid.uuid4()

    form = EventForm(request.POST)
    if form.is_valid():
        event = form.save(commit=False)
        event.submission_id = submission_id
        if request.user.is_authenticated:
            event.creator = request.user
        try:
            with transaction.atomic():
                event.save()
        except IntegrityError:
            Event.objects.get(submission_id=submission_id)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'redirect_url': reverse('events:map')})
        messages.success(request, 'Eventを投稿しました。')
        return redirect('events:map')

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse(
            {
                'errors': {
                    field_name: list(errors)
                    for field_name, errors in form.errors.items()
                },
            },
            status=400,
        )

    for field_name, errors in form.errors.items():
        label = form.fields[field_name].label if field_name in form.fields else ''
        for error in errors:
            messages.error(request, f'{label}：{error}' if label else error)

    return redirect(f"{reverse('events:map')}?mode=create")


def event_owner_or_error(request, event_id):
    event = get_object_or_404(Event, pk=event_id)
    if request.user.is_authenticated and event.creator_id == request.user.id:
        return event, None
    return None, JsonResponse({'error': 'このEventを管理する権限がありません。'}, status=403)


def event_update(request, event_id):
    if request.method != 'POST':
        return redirect('events:map')

    event, error_response = event_owner_or_error(request, event_id)
    if error_response:
        return error_response

    form = EventForm(request.POST, instance=event)
    if form.is_valid():
        form.save()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'redirect_url': reverse('events:map')})
        messages.success(request, 'Eventを更新しました。')
        return redirect('events:map')

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse(
            {'errors': {field_name: list(errors) for field_name, errors in form.errors.items()}},
            status=400,
        )

    for field_name, errors in form.errors.items():
        label = form.fields[field_name].label if field_name in form.fields else ''
        for error in errors:
            messages.error(request, f'{label}: {error}' if label else error)
    return redirect('events:map')


def event_delete(request, event_id):
    if request.method != 'POST':
        return redirect('events:map')

    event, error_response = event_owner_or_error(request, event_id)
    if error_response:
        return error_response

    event.delete()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'redirect_url': reverse('events:map')})
    messages.success(request, 'Eventを削除しました。')
    return redirect('events:map')


@require_POST
def filter_preferences_update(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'ログインが必要です。'}, status=401)

    preference, _ = NiiMapFilterPreference.objects.get_or_create(user=request.user)
    fields = [
        'range_filter_enabled',
        'show_ongoing',
        'show_today',
        'show_tomorrow',
        'show_ended',
        'show_guest_events',
        'account_ids_enabled',
        'datetime_section_open',
        'account_section_open',
    ]
    for field_name in fields:
        setattr(preference, field_name, request.POST.get(field_name) == 'true')
    preference.save(update_fields=fields)
    return JsonResponse({'ok': True})


def location_search(request):
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'locations': []})

    stations = Station.objects.filter(name__icontains=query)[:5]
    localities = Locality.objects.filter(full_name__icontains=query)[:5]
    locations = [
        {
            'name': station.name,
            'detail': f'{station.line_name} / {station.operator_name}',
            'latitude': float(station.latitude),
            'longitude': float(station.longitude),
        }
        for station in stations
    ]
    locations.extend(
        {
            'name': locality.name,
            'detail': locality.detail,
            'latitude': float(locality.latitude),
            'longitude': float(locality.longitude),
        }
        for locality in localities
    )
    return JsonResponse({'locations': locations})
