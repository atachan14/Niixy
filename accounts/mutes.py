"""Request-specific display filtering. Never used to grant or deny access."""
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import AccountMute


def muted_account_ids(viewer):
    if not viewer.is_authenticated:
        return AccountMute.objects.none().values_list('muted_account_id', flat=True)
    return AccountMute.objects.filter(muter_id=viewer.pk).values_list('muted_account_id', flat=True)


def filter_muted(queryset, viewer, account_field='creator_id'):
    if not viewer.is_authenticated:
        return queryset
    return queryset.exclude(**{f'{account_field}__in': muted_account_ids(viewer)})


def prepare_muted_posts(posts, viewer, muted=None):
    if muted is None:
        muted = set(muted_account_ids(viewer))
    for post in posts:
        post.is_muted = post.creator_id in muted


@require_POST
def change(request, username):
    from .reviews import target_account
    account = target_account(username)
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'ログインが必要です。'}, status=401)
    if request.user.pk == account.pk:
        return JsonResponse({'error': '自分のAccountはMuteできません。'}, status=403)
    enabled = request.POST.get('enabled')
    if enabled not in {'true', 'false'}:
        return JsonResponse({'error': 'Muteの状態が正しくありません。'}, status=400)
    # Set a desired state instead of toggling: duplicate POSTs are idempotent.
    # Request identity and URL are authoritative, never submitted account IDs.
    if enabled == 'true':
        AccountMute.objects.get_or_create(muter=request.user, muted_account=account)
    else:
        AccountMute.objects.filter(muter=request.user, muted_account=account).delete()
    return JsonResponse({'ok': True, 'muted': enabled == 'true'})
