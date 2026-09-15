from django.contrib import messages
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from .forms import EventForm
from .models import Event, Station


def map_view(request):
    events = Event.objects.all()
    event_markers = [
        {
            'id': event.pk,
            'starts_at': event.starts_at.isoformat(),
            'ends_at': event.ends_at.isoformat() if event.ends_at else None,
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
            'geolonia_api_key': settings.GEOLONIA_API_KEY,
        },
    )


def healthcheck(request):
    return HttpResponse('ok', content_type='text/plain')


def event_create(request):
    if request.method != 'POST':
        return redirect('events:map')

    form = EventForm(request.POST)
    if form.is_valid():
        form.save()
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


def location_search(request):
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'locations': []})

    stations = Station.objects.filter(name__icontains=query)[:10]
    locations = [
        {
            'name': station.name,
            'detail': f'{station.line_name} / {station.operator_name}',
            'latitude': float(station.latitude),
            'longitude': float(station.longitude),
        }
        for station in stations
    ]
    return JsonResponse({'locations': locations})
