"""Public Account Reviews; only the author can change their one Review."""
from django.views.decorators.cache import never_cache
from django import forms
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .models import AccountMute, AccountReview


class ReviewIdentityForm(forms.Form):
    review_id = forms.IntegerField(required=False, min_value=1, max_value=9223372036854775807)
    revision = forms.IntegerField(required=False, min_value=1, max_value=2147483646)


class ReviewForm(ReviewIdentityForm):
    sentiment = forms.ChoiceField(choices=AccountReview.SENTIMENT_CHOICES)
    body = forms.CharField(max_length=AccountReview.BODY_MAX_LENGTH, strip=True)


def target_account(username):
    return get_object_or_404(
        get_user_model().objects.select_related('niixy_profile'), username__iexact=username,
    )


def review_context(account, viewer, params=None):
    params = params or {}
    reviews = AccountReview.objects.filter(target=account)
    counts = reviews.aggregate(
        total=Count('pk'), love=Count('pk', filter=Q(sentiment=AccountReview.LOVE)),
        hate=Count('pk', filter=Q(sentiment=AccountReview.HATE)),
    )
    muters = AccountMute.objects.filter(muted_account=account)
    muter_count = muters.count()
    own_mute = muters.filter(muter=viewer).exists() if viewer.is_authenticated else False
    own = reviews.filter(author=viewer).first() if viewer.is_authenticated else None
    kind = params.get('review_filter', 'all')
    if kind not in {'all', AccountReview.LOVE, AccountReview.HATE, 'muter'}:
        kind = 'all'
    filtered = muters.select_related('muter__niixy_profile') if kind == 'muter' else (reviews if kind == 'all' else reviews.filter(sentiment=kind)).select_related('author__niixy_profile')
    expanded = params.get('review_expanded') == '1'
    page = Paginator(filtered, 10 if expanded else (8 if kind == 'muter' else 3)).get_page(
        params.get('review_page') if expanded else 1,
    )
    return {
        'review_counts': counts, 'review_score': counts['love'] - counts['hate'],
        'muter_count': muter_count, 'own_mute': own_mute, 'own_review': own, 'review_filter': kind, 'review_expanded': expanded,
        'review_page': page, 'can_review': viewer.is_authenticated and viewer.pk != account.pk,
    }


@require_GET
@never_cache
def listing(request, username):
    account = target_account(username)
    return render(request, 'accounts/partials/review_section.html', {
        'account': account, **review_context(account, request.user, request.GET),
    })


@require_GET
def editor(request, username):
    account = target_account(username)
    denied = write_denied(request, account)
    if denied:
        return denied
    own = AccountReview.objects.filter(target=account, author=request.user).first()
    sentiment = request.GET.get('sentiment')
    if sentiment not in {AccountReview.LOVE, AccountReview.HATE}:
        sentiment = own.sentiment if own else AccountReview.LOVE
    return render(request, 'accounts/partials/review_editor.html', {
        'account': account, 'own_review': own, 'review_sentiment': sentiment,
        'review_body_max_length': AccountReview.BODY_MAX_LENGTH,
    })


def write_denied(request, account):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'ログインが必要です。'}, status=401)
    if request.user.pk == account.pk:
        return JsonResponse({'error': '自分のAccountにはReviewできません。'}, status=403)
    return None


def conflict():
    return JsonResponse({'error': 'Reviewが更新されています。閉じて開き直し、最新の内容を確認してください。'}, status=409)


@require_POST
def save(request, username):
    account = target_account(username)
    denied = write_denied(request, account)
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
        own = get_object_or_404(AccountReview, pk=data['review_id'], author=request.user, target=account)
        changed = AccountReview.objects.filter(pk=own.pk, revision=data['revision']).update(
            sentiment=data['sentiment'], body=data['body'], revision=data['revision'] + 1,
            updated_at=timezone.now(),
        )
        if not changed:
            return conflict()
        return JsonResponse({'ok': True})
    try:
        with transaction.atomic():
            AccountReview.objects.create(
                author=request.user, target=account, sentiment=data['sentiment'], body=data['body'],
            )
    except IntegrityError:
        # A simultaneous create must never turn into an implicit update.
        return conflict()
    return JsonResponse({'ok': True}, status=201)


@require_POST
def delete(request, username):
    account = target_account(username)
    denied = write_denied(request, account)
    if denied:
        return denied
    form = ReviewIdentityForm(request.POST)
    if not form.is_valid() or not all(form.cleaned_data.values()):
        return JsonResponse({'error': 'Reviewの版が不正です。'}, status=400)
    review_id, revision = form.cleaned_data['review_id'], form.cleaned_data['revision']
    own = get_object_or_404(AccountReview, pk=review_id, author=request.user, target=account)
    deleted, _ = AccountReview.objects.filter(pk=own.pk, revision=revision).delete()
    if not deleted:
        return conflict()
    return JsonResponse({'ok': True})
