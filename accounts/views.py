from django.contrib.auth import login, logout
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.db.models import OuterRef, Prefetch, Subquery
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from events.models import Thread, ThreadAccessRule, ThreadPost

from .forms import LoginForm, SignUpForm


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
            Prefetch('posts', queryset=ThreadPost.objects.select_related('creator')),
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
    account = get_object_or_404(User, username__iexact=username)
    created_threads = prepare_threads(Thread.objects.filter(creator=account).order_by('-created_at'), request.user)
    latest_reply = ThreadPost.objects.filter(
        thread_id=OuterRef('pk'),
        creator=account,
        number__gt=1,
    ).order_by('-created_at')
    replied_threads = prepare_threads(
        Thread.objects.annotate(
            account_latest_reply_at=Subquery(latest_reply.values('created_at')[:1]),
        ).filter(account_latest_reply_at__isnull=False).order_by('-account_latest_reply_at', '-pk'),
        request.user,
    )

    created_page = Paginator(created_threads, 10).get_page(request.GET.get('created_page'))
    replied_page = Paginator(replied_threads, 10).get_page(request.GET.get('replied_page'))
    detail_threads = []
    seen_thread_ids = set()
    for thread in [*created_page.object_list, *replied_page.object_list]:
        if thread.pk not in seen_thread_ids:
            detail_threads.append(thread)
            seen_thread_ids.add(thread.pk)

    return render(request, 'accounts/account_page.html', {
        'account': account,
        'created_page': created_page,
        'replied_page': replied_page,
        'detail_threads': detail_threads,
    })
