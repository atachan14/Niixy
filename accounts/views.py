import json

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.db.models import Prefetch, Q, Value
from django.db.models.functions import Concat
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from events.models import Thread, ThreadAccessRule, ThreadPlacement, ThreadPost
from events.services import prepare_thread_for_view, thread_queryset

from .forms import DisplayNameForm, LoginForm, SignUpForm
from .models import AccountCondition, AccountProfile
from .services import condition_payload, save_account_condition
from interfaces.models import FieldDefinition, Interface
from interfaces.views import mark_interface_update_status, module_list_context, profile_module_list_context


User = get_user_model()


def account_condition_search(request):
    query = request.GET.get('q', '').strip()
    accounts = User.objects.select_related('niixy_profile').annotate(
        search_identity=Concat('niixy_profile__display_name', Value('@'), 'username'),
    )
    if query:
        accounts = accounts.filter(
            Q(search_identity__icontains=query) | Q(username__icontains=query)
        )
    accounts = accounts.order_by('username')[:10]
    return JsonResponse({'accounts': [
        {
            'id': account.pk,
            'username': account.username,
            'label': account.niixy_profile.display_label,
        }
        for account in accounts
    ]})


@require_POST
def account_condition_save(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Account条件の保存にはログインが必要です。'}, status=401)
    try:
        definition = json.loads(request.POST.get('definition', '{}'))
        condition = save_account_condition(
            request.user,
            kind=request.POST.get('kind', ''),
            definition=definition,
            condition_id=request.POST.get('condition_id') or None,
        )
    except (json.JSONDecodeError, ValueError) as error:
        return JsonResponse({'error': str(error)}, status=400)
    return JsonResponse({'condition': condition_payload(condition)})


@require_POST
def account_condition_delete(request, condition_id):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'ログインが必要です。'}, status=401)
    condition = get_object_or_404(AccountCondition, pk=condition_id, owner=request.user)
    condition.active = False
    condition.save(update_fields=['active'])
    return JsonResponse({'ok': True})


def form_errors(form):
    return {field_name: list(errors) for field_name, errors in form.errors.items()}


@require_POST
def signup(request):
    form = SignUpForm(request.POST)
    if form.is_valid():
        try:
            user = get_user_model().objects.create_user(
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password'],
            )
        except IntegrityError:
            form.add_error('username', 'このNiixy IDはすでに使われています。')
        else:
            profile, _ = AccountProfile.objects.get_or_create(user=user)
            profile.display_name = form.cleaned_data['display_name']
            profile.save(update_fields=['display_name'])
            login(request, user)
            return JsonResponse({'username': user.username})

    return JsonResponse({'errors': form_errors(form)}, status=400)


@require_POST
def login_view(request):
    form = LoginForm(request, request.POST)
    if form.is_valid():
        login(request, form.user)
        return JsonResponse({'username': form.user.username})
    return JsonResponse({'errors': form_errors(form)}, status=400)


@require_POST
def logout_view(request):
    logout(request)
    return redirect('events:map')


def prepare_threads(queryset, viewer):
    threads = list(
        queryset.select_related('creator').prefetch_related(
            'access_rules',
            Prefetch('placements', queryset=ThreadPlacement.objects.filter(kind=ThreadPlacement.NII_MAP)),
            Prefetch('posts', queryset=ThreadPost.objects.select_related('creator__niixy_profile')),
            'interface_implementations__version__interface__creator',
            'interface_implementations__values__field',
        )
    )
    for thread in threads:
        thread.can_view = thread.allows(viewer, ThreadAccessRule.VIEW)
        thread.can_write = thread.allows(viewer, ThreadAccessRule.WRITE)
    return threads


def account_page(request, username):
    account = get_object_or_404(User.objects.select_related('niixy_profile'), username__iexact=username)
    return render(request, 'accounts/account_page.html', {
        'account': account,
    })


def account_thread_pane(request, username):
    account = get_object_or_404(User.objects.select_related('niixy_profile'), username__iexact=username)
    created_threads = prepare_threads(Thread.objects.filter(creator=account).order_by('-created_at'), request.user)
    created_page = Paginator(created_threads, 10).get_page(request.GET.get('created_page'))
    return render(request, 'accounts/partials/thread_pane.html', {
        'account': account,
        'created_page': created_page,
    })


def account_response_pane(request, username):
    account = get_object_or_404(User.objects.select_related('niixy_profile'), username__iexact=username)
    posts = list(
        ThreadPost.objects.filter(creator=account, number__gt=1)
        .select_related('thread', 'creator__niixy_profile')
        .prefetch_related(
            'thread__access_rules',
            Prefetch('thread__posts', queryset=ThreadPost.objects.select_related('creator__niixy_profile')),
        )
        .order_by('-created_at')
    )
    for post in posts:
        post.thread.can_view = post.thread.allows(request.user, ThreadAccessRule.VIEW)
    response_page = Paginator(posts, 10).get_page(request.GET.get('response_page'))
    return render(request, 'accounts/partials/response_pane.html', {
        'account': account,
        'response_page': response_page,
    })


def account_module_pane(request, username):
    account = get_object_or_404(User.objects.select_related('niixy_profile'), username__iexact=username)
    return render(
        request,
        'interfaces/module_management_list_pane.html',
        profile_module_list_context(account),
    )


def account_module_field_detail(request, username, field_id):
    account = get_object_or_404(User, username__iexact=username)
    field = get_object_or_404(
        FieldDefinition.objects.filter(
            creator=account,
            status=FieldDefinition.ACTIVE,
            current_version__isnull=False,
        ).select_related('creator', 'current_version').prefetch_related(
            'current_version__synonyms__target__creator',
        ),
        pk=field_id,
    )
    return render(request, 'interfaces/field_detail_pane.html', {
        'field_item': field,
        'profile_mode': True,
    })


def account_module_interface_detail(request, username, interface_id):
    account = get_object_or_404(User, username__iexact=username)
    interface = get_object_or_404(
        Interface.objects.filter(
            creator=account,
            status=Interface.ACTIVE,
            current_version__isnull=False,
        ).select_related('creator', 'current_version').prefetch_related(
            'current_version__fields__definition__creator',
            'current_version__fields__definition__current_version',
            'current_version__fields__field_version',
            'current_version__fields__field_version__synonyms__target__creator',
        ),
        pk=interface_id,
    )
    mark_interface_update_status([interface])
    return render(request, 'interfaces/published_detail_pane.html', {
        'selected_interface': interface,
        'selected_interface_dependents': 0,
        'profile_mode': True,
    })


def account_thread_detail(request, username, thread_id):
    account = get_object_or_404(User.objects.select_related('niixy_profile'), username__iexact=username)
    thread = get_object_or_404(
        thread_queryset().filter(Q(creator=account) | Q(posts__creator=account, posts__number__gt=1)).distinct(),
        pk=thread_id,
    )
    prepare_thread_for_view(thread, request.user)
    return render(request, 'accounts/partials/thread_detail.html', {
        'thread': thread,
    })


def my_page(request):
    if not request.user.is_authenticated:
        return redirect('events:map')

    profile, _ = AccountProfile.objects.get_or_create(user=request.user)
    form = DisplayNameForm(request.POST or None, initial={'display_name': profile.display_name})
    show_basic_info = request.method == 'POST'
    if request.method == 'POST' and form.is_valid():
        profile.display_name = form.cleaned_data['display_name']
        profile.save(update_fields=['display_name'])
        messages.success(request, '基本情報を更新しました。')
        return redirect('mypage')

    render_panes = request.GET.get('_panes') == '1' or request.method == 'POST'
    section = request.GET.get('section')
    show_module = section in {'module', 'interface', 'definition'}
    context = {
        'account': request.user,
        'form': form,
        'show_basic_info': show_basic_info,
        'show_module': show_module,
        'render_mypage_panes': render_panes,
    }
    if render_panes and show_module:
        context.update(module_list_context(request.user))
    return render(request, 'accounts/my_page.html', context)
