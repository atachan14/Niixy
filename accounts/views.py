from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.db.models import Prefetch
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from events.models import Thread, ThreadAccessRule, ThreadPost

from .forms import DisplayNameForm, LoginForm, SignUpForm
from .models import AccountProfile


User = get_user_model()


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
            Prefetch('posts', queryset=ThreadPost.objects.select_related('creator__niixy_profile')),
        )
    )
    discoverable = []
    for thread in threads:
        if not thread.allows(viewer, ThreadAccessRule.DISCOVER):
            continue
        thread.can_view = thread.allows(viewer, ThreadAccessRule.VIEW)
        thread.can_write = thread.allows(viewer, ThreadAccessRule.WRITE)
        discoverable.append(thread)
    return discoverable


def account_page(request, username):
    account = get_object_or_404(User.objects.select_related('niixy_profile'), username__iexact=username)
    created_threads = prepare_threads(Thread.objects.filter(creator=account).order_by('-created_at'), request.user)
    created_page = Paginator(created_threads, 10).get_page(request.GET.get('created_page'))
    response_posts = list(
        ThreadPost.objects.filter(creator=account, number__gt=1)
        .select_related('thread')
        .prefetch_related('thread__access_rules', Prefetch('thread__posts', queryset=ThreadPost.objects.select_related('creator__niixy_profile')))
        .order_by('-created_at')
    )
    visible_responses = []
    for post in response_posts:
        if not post.thread.allows(request.user, ThreadAccessRule.DISCOVER):
            continue
        post.can_view = post.thread.allows(request.user, ThreadAccessRule.VIEW)
        visible_responses.append(post)
    response_page = Paginator(visible_responses, 10).get_page(request.GET.get('response_page'))
    detail_threads = list(created_page.object_list)
    seen_thread_ids = {thread.pk for thread in detail_threads}
    for post in response_page.object_list:
        if post.thread_id not in seen_thread_ids:
            detail_threads.append(post.thread)
            seen_thread_ids.add(post.thread_id)

    return render(request, 'accounts/account_page.html', {
        'account': account,
        'created_page': created_page,
        'detail_threads': detail_threads,
        'response_page': response_page,
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

    return render(request, 'accounts/my_page.html', {
        'account': request.user,
        'form': form,
        'show_basic_info': show_basic_info,
    })
