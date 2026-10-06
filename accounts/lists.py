"""Public named Account references; mutations always belong to request.user."""
from uuid import uuid4

from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from config.pagination import paginate_summary_list
from .internal_urls import resolve_internal_url
from .models import AccountList, AccountListReference, AccountReview
from .mutes import muted_account_ids
from .reviews import target_account


class ListForm(forms.Form):
    name = forms.CharField(max_length=80, strip=True)
    submission_id = forms.UUIDField()
    target_url = forms.CharField(required=False, max_length=2048)


class RenameForm(forms.Form):
    name = forms.CharField(max_length=80, strip=True)


class ReferenceForm(forms.Form):
    target_url = forms.CharField(max_length=2048)


def login_denied(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'ログインが必要です。'}, status=401)
    return None


def owned_list(request, list_id):
    return get_object_or_404(AccountList, pk=list_id, owner=request.user)


def invalid(form):
    return JsonResponse({'errors': {key: list(value) for key, value in form.errors.items()}}, status=400)


def resolve_account(request, value):
    target = resolve_internal_url(request, value)
    if target.kind != 'account':
        raise ValidationError('Accountの正規URLを入力してください。Listや他の種類は追加できません。')
    return target.instance


def url_error(error):
    return JsonResponse({'error': ' '.join(error.messages)}, status=400)


def list_context(request, account):
    page = paginate_summary_list(AccountList.objects.filter(owner=account).annotate(reference_count=Count('references')).order_by('created_at','pk'), request.GET.get('page'))
    return {'account': account, 'summary_page': page, 'is_list_owner': request.user.pk == account.pk,
            'submission_id': uuid4(), 'summary_page_url': reverse('accounts:list-index', args=[account.username]),
            'summary_page_label': 'AccountList一覧のページ'}


@require_GET
@never_cache
def listing(request, username):
    account = target_account(username)
    muted = muted_account_ids(request.user)
    references = AccountListReference.objects.select_related('target__niixy_profile').exclude(target_id__in=muted)
    lists = AccountList.objects.filter(owner=account).order_by('created_at','pk').prefetch_related(Prefetch('references',queryset=references,to_attr='visible_references'))
    reviewed = {sentiment: AccountReview.objects.filter(author=account,sentiment=sentiment).exclude(target_id__in=muted).select_related('target__niixy_profile') for sentiment in ('love','hate')}
    return render(request, 'accounts/partials/account_lists.html', {
        **list_context(request, account), 'people_lists': lists, 'loved_accounts': reviewed['love'], 'hated_accounts': reviewed['hate'],
    })


@require_GET
@never_cache
def picker(request, username):
    account = target_account(username)
    denied = login_denied(request)
    if denied:
        return denied
    if not AccountReview.objects.filter(author=request.user, target=account).exists():
        return JsonResponse({'error': '紹介文を保存してから追加先を選択してください。'}, status=403)
    context = list_context(request, request.user)
    context.update(target_account=account, target_url=reverse('accounts:detail', args=[account.username]),
                   summary_page_url=reverse('accounts:list-picker', args=[account.username]))
    return render(request, 'accounts/partials/account_list_picker.html', context)


@require_GET
@never_cache
def page(request, list_id):
    from .views import account_page
    account_list = get_object_or_404(AccountList.objects.select_related('owner__niixy_profile'), pk=list_id)
    return account_page(request, account_list.owner.username, account_list=account_list)


@require_GET
@never_cache
def detail(request, list_id):
    account_list = get_object_or_404(AccountList.objects.select_related('owner__niixy_profile'), pk=list_id)
    references = account_list.references.select_related('target__niixy_profile')
    # Display-only filtering: direct Account URLs and references stay intact.
    if request.user.is_authenticated:
        references = references.exclude(target_id__in=muted_account_ids(request.user))
    return render(request, 'accounts/partials/account_list_detail.html', {
        'account_list': account_list, 'is_list_owner': request.user.pk == account_list.owner_id,
        'summary_page': paginate_summary_list(references, request.GET.get('page')),
        'summary_page_url': reverse('accounts:list-detail', args=[list_id]),
        'summary_page_label': 'Account参照のページ',
    })


@require_POST
@transaction.atomic
def create(request):
    denied = login_denied(request)
    if denied:
        return denied
    form = ListForm(request.POST)
    if not form.is_valid():
        return invalid(form)
    data = form.cleaned_data
    try:
        target = resolve_account(request, data['target_url']) if data['target_url'] else None
    except ValidationError as error:
        return url_error(error)
    account_list, created = AccountList.objects.get_or_create(owner=request.user, submission_id=data['submission_id'], defaults={'name': data['name']})
    # Replayed creates never rename a previously created List.
    if target:
        AccountListReference.objects.get_or_create(account_list=account_list, target=target)
    return JsonResponse({'ok': True, 'list_id': account_list.pk,
                         'url': reverse('accounts:list-page', args=[account_list.pk]),
                         'index_url': reverse('accounts:list-index', args=[request.user.username])}, status=201 if created else 200)


@require_POST
def rename(request, list_id):
    denied = login_denied(request)
    if denied:
        return denied
    account_list = owned_list(request, list_id)
    form = RenameForm(request.POST)
    if not form.is_valid():
        return invalid(form)
    account_list.name = form.cleaned_data['name']
    account_list.save(update_fields=['name', 'updated_at'])
    return JsonResponse({'ok': True, 'list_id': account_list.pk, 'name': account_list.name})


@require_POST
def delete(request, list_id):
    denied = login_denied(request)
    if denied:
        return denied
    owned_list(request, list_id).delete()
    return JsonResponse({'ok': True, 'list_id': list_id, 'deleted': True})


@require_POST
def add(request, list_id):
    denied = login_denied(request)
    if denied:
        return denied
    account_list = owned_list(request, list_id)
    form = ReferenceForm(request.POST)
    if not form.is_valid():
        return invalid(form)
    try:
        target = resolve_account(request, form.cleaned_data['target_url'])
    except ValidationError as error:
        return url_error(error)
    reference, created = AccountListReference.objects.get_or_create(account_list=account_list, target=target)
    return JsonResponse({'ok': True, 'created': created, 'reference_id': reference.pk,
                         'list_id': account_list.pk, 'reference_count': account_list.references.count()}, status=201 if created else 200)


@require_POST
def remove(request, list_id, reference_id):
    denied = login_denied(request)
    if denied:
        return denied
    account_list = owned_list(request, list_id)
    # Repeated removal is safe; never delete the referenced Account.
    AccountListReference.objects.filter(account_list=account_list, pk=reference_id).delete()
    return JsonResponse({'ok': True, 'list_id': account_list.pk, 'reference_count': account_list.references.count()})
