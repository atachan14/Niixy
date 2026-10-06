"""Public Room Reviews; only the author can change their one Review."""
from django.views.decorators.cache import never_cache
from django import forms
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .models import Room, RoomMute, RoomReview


class ReviewIdentityForm(forms.Form):
    review_id = forms.IntegerField(required=False, min_value=1, max_value=9223372036854775807)
    revision = forms.IntegerField(required=False, min_value=1, max_value=2147483646)


class ReviewForm(ReviewIdentityForm):
    sentiment = forms.ChoiceField(choices=RoomReview.SENTIMENT_CHOICES)
    body = forms.CharField(max_length=RoomReview.BODY_MAX_LENGTH, strip=True)


def target_room(room_id):
    return get_object_or_404(Room.objects.select_related('owner__niixy_profile'), pk=room_id)


def review_context(room, viewer, params=None):
    params = params or {}
    reviews = RoomReview.objects.filter(target=room)
    counts = reviews.aggregate(
        total=Count('pk'), love=Count('pk', filter=Q(sentiment=RoomReview.LOVE)),
        hate=Count('pk', filter=Q(sentiment=RoomReview.HATE)),
    )
    muters = RoomMute.objects.filter(room=room)
    muter_count = muters.count()
    own_mute = muters.filter(muter=viewer).exists() if viewer.is_authenticated else False
    own = reviews.filter(author=viewer).first() if viewer.is_authenticated else None
    kind = params.get('review_filter', 'all')
    if kind not in {'all', RoomReview.LOVE, RoomReview.HATE, 'muter'}:
        kind = 'all'
    filtered = muters.select_related('muter__niixy_profile') if kind == 'muter' else (reviews if kind == 'all' else reviews.filter(sentiment=kind)).select_related('author__niixy_profile')
    expanded = params.get('review_expanded') == '1'
    page = Paginator(filtered, 10 if expanded else (8 if kind == 'muter' else 3)).get_page(
        params.get('review_page') if expanded else 1,
    )
    return {
        'review_counts': counts, 'review_score': counts['love'] - counts['hate'],
        'muter_count': muter_count, 'own_mute': own_mute, 'own_review': own, 'review_filter': kind, 'review_expanded': expanded,
        'review_page': page, 'can_review': viewer.is_authenticated,
    }


@require_GET
@never_cache
def listing(request, room_id):
    room = target_room(room_id)
    return render(request, 'rooms/partials/review_section.html', {
        'room': room, **review_context(room, request.user, request.GET),
    })


@require_GET
@never_cache
def editor(request, room_id):
    room = target_room(room_id)
    denied = write_denied(request, room)
    if denied:
        return denied
    own = RoomReview.objects.filter(target=room, author=request.user).first()
    sentiment = request.GET.get('sentiment')
    if sentiment not in {RoomReview.LOVE, RoomReview.HATE}:
        sentiment = own.sentiment if own else RoomReview.LOVE
    return render(request, 'rooms/partials/review_editor.html', {
        'room': room, 'own_review': own, 'review_sentiment': sentiment,
        'review_body_max_length': RoomReview.BODY_MAX_LENGTH,
    })


def write_denied(request, room):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'ログインが必要です。'}, status=401)
    return None


def conflict():
    return JsonResponse({'error': 'Reviewが更新されています。閉じて開き直し、最新の内容を確認してください。'}, status=409)


@require_POST
def save(request, room_id):
    room = target_room(room_id)
    denied = write_denied(request, room)
    if denied:
        return denied
    form = ReviewForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'errors': {key: list(value) for key, value in form.errors.items()}}, status=400)
    data = form.cleaned_data
    if bool(data['review_id']) != bool(data['revision']):
        return JsonResponse({'error': 'Reviewの版が不正です。'}, status=400)
    if data['review_id']:
        # Author and target are always taken from the authenticated request/URL.
        own = get_object_or_404(RoomReview, pk=data['review_id'], author=request.user, target=room)
        changed = RoomReview.objects.filter(pk=own.pk, revision=data['revision']).update(
            sentiment=data['sentiment'], body=data['body'], revision=data['revision'] + 1,
            updated_at=timezone.now(),
        )
        if not changed:
            return conflict()
        return JsonResponse({'ok': True})
    try:
        with transaction.atomic():
            RoomReview.objects.create(
                author=request.user, target=room, sentiment=data['sentiment'], body=data['body'],
            )
    except IntegrityError:
        # A simultaneous create must never turn into an implicit update.
        return conflict()
    return JsonResponse({'ok': True}, status=201)


@require_POST
def delete(request, room_id):
    room = target_room(room_id)
    denied = write_denied(request, room)
    if denied:
        return denied
    form = ReviewIdentityForm(request.POST)
    if not form.is_valid() or not all(form.cleaned_data.values()):
        return JsonResponse({'error': 'Reviewの版が不正です。'}, status=400)
    review_id, revision = form.cleaned_data['review_id'], form.cleaned_data['revision']
    own = get_object_or_404(RoomReview, pk=review_id, author=request.user, target=room)
    deleted, _ = RoomReview.objects.filter(pk=own.pk, revision=revision).delete()
    if not deleted:
        return conflict()
    return JsonResponse({'ok': True})
