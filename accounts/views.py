from django.views.decorators.cache import never_cache
import json

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Prefetch, Q, Value
from django.db.models.functions import Concat
from django.http import JsonResponse
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from events.models import Thread, ThreadAccessRule, ThreadPlacement, ThreadPost
from events.services import prepare_thread_for_view, thread_queryset

from .mutes import filter_muted, muted_account_ids, prepare_muted_posts
from .forms import DisplayNameForm, LoginForm, SignUpForm
from .models import AccountCondition, AccountProfile
from .services import account_condition_catalog, condition_payload, save_account_condition
from interfaces.models import FieldDefinition, Interface
from interfaces.services import thread_field_catalog, thread_interface_catalog
from interfaces.views import mark_interface_update_status, module_list_context, profile_module_list_context
from rooms.models import Room


User = get_user_model()


def account_condition_list(request):
    available_conditions = account_condition_catalog(request.user, include_inactive=True)
    return JsonResponse({
        'conditions': [condition for condition in available_conditions if condition['active']],
        'available_conditions': available_conditions,
    })


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


def account_condition_room_search(request):
    query = request.GET.get('q', '').strip()
    rooms = Room.objects.all()
    if query:
        rooms = rooms.filter(Q(name__icontains=query) | Q(owner__username__icontains=query))
    if request.GET.get('joined') == 'true':
        if not request.user.is_authenticated:
            rooms = rooms.none()
        else:
            rooms = rooms.filter(memberships__account=request.user)
    rooms = rooms.select_related('owner').order_by('name', 'pk').distinct()[:20]
    return JsonResponse({'rooms': [
        {'id': room.pk, 'name': room.name, 'label': f'{room.name}に参加'}
        for room in rooms
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
@transaction.atomic
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
        filter_muted(queryset, viewer).select_related('creator').prefetch_related(
            'access_rules',
            'policy_conditions',
            Prefetch('placements', queryset=ThreadPlacement.objects.filter(kind=ThreadPlacement.NII_MAP)),
            Prefetch('posts', queryset=ThreadPost.objects.select_related('creator__niixy_profile')),
            'interface_implementations__version__interface__creator',
            'interface_implementations__values__field',
        )
    )
    muted = set(muted_account_ids(viewer))
    for thread in threads:
        prepare_thread_for_view(thread, viewer, muted)
    return threads


@never_cache
def account_page(request, username, *, account_list=None):
    from interfaces.account_layouts import profile_context
    from .reviews import review_context
    account = get_object_or_404(User.objects.select_related('niixy_profile'), username__iexact=username)
    return render(request, 'accounts/account_page.html', {
        'account_list_direct': account_list,
        'account': account,
        **profile_context(account),
        **review_context(account, request.user),
        'thread_field_catalog': thread_field_catalog(),
        'thread_interface_catalog': thread_interface_catalog(),
    })


@never_cache
def account_pane(request, username):
    from interfaces.account_layouts import profile_context
    from .reviews import review_context
    account = get_object_or_404(User.objects.select_related('niixy_profile'), username__iexact=username)
    return render(request, 'accounts/partials/account_pane.html', {
        'account': account,
        **profile_context(account),
        **review_context(account, request.user),
        'thread_field_catalog': thread_field_catalog(),
        'thread_interface_catalog': thread_interface_catalog(),
    })


@never_cache
def account_thread_pane(request, username):
    account = get_object_or_404(User.objects.select_related('niixy_profile'), username__iexact=username)
    created_threads = prepare_threads(Thread.objects.filter(creator=account).order_by('-created_at'), request.user)
    created_page = Paginator(created_threads, 10).get_page(request.GET.get('created_page'))
    return render(request, 'accounts/partials/thread_pane.html', {
        'account': account,
        'created_page': created_page,
    })


@never_cache
def account_response_pane(request, username):
    account = get_object_or_404(User.objects.select_related('niixy_profile'), username__iexact=username)
    posts = list(
        filter_muted(ThreadPost.objects.filter(creator=account, number__gt=1), request.user, 'thread__creator_id')
        .select_related('thread', 'creator__niixy_profile')
        .prefetch_related(
            'thread__access_rules',
            'thread__policy_conditions',
            Prefetch('thread__posts', queryset=ThreadPost.objects.select_related('creator__niixy_profile')),
        )
        .order_by('-created_at')
    )
    prepare_muted_posts(posts, request.user)
    visible_posts = []
    denied_threads = set()
    for post in posts:
        post.thread.can_view = post.thread.allows(request.user, ThreadAccessRule.VIEW)
        if not post.thread.can_view:
            # Repeated denied summaries and pagination must not reveal reply counts.
            if post.thread_id in denied_threads:
                continue
            denied_threads.add(post.thread_id)
        visible_posts.append(post)
    response_page = Paginator(visible_posts, 10).get_page(request.GET.get('response_page'))
    return render(request, 'accounts/partials/response_pane.html', {
        'account': account,
        'response_page': response_page,
    })


@never_cache
def account_room_pane(request, username):
    account = get_object_or_404(User.objects.select_related('niixy_profile'), username__iexact=username)
    base_rooms = filter_muted(Room.objects.select_related('owner__niixy_profile'), request.user, 'owner_id')
    owner_page = Paginator(
        base_rooms.filter(owner=account).order_by('-last_activity_at', '-created_at'),
        20,
    ).get_page(request.GET.get('owner_page'))
    member_page = Paginator(
        base_rooms.filter(memberships__account=account).distinct().order_by('-last_activity_at', '-created_at'),
        20,
    ).get_page(request.GET.get('member_page'))
    return render(request, 'accounts/partials/room_pane.html', {
        'account': account,
        'owner_page': owner_page,
        'member_page': member_page,
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


@never_cache
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


def account_applied(request, username):
    from interfaces.account_applications import application_payload
    account = get_object_or_404(User.objects.select_related('niixy_profile'), username__iexact=username)
    return render(request, 'accounts/partials/applied_list.html', {
        'account': account, 'applied': application_payload(account),
        'edit_mode': request.GET.get('edit') == '1' and request.user.is_authenticated and request.user.pk == account.pk,
    })


def account_applied_data(request, username):
    from interfaces.account_applications import application_payload, application_catalog
    account = get_object_or_404(User, username__iexact=username)
    result = application_payload(account)
    if request.user.is_authenticated and request.user.pk == account.pk:
        result['catalog'] = application_catalog()
    return JsonResponse(result)


@require_POST
def account_applied_change(request, username):
    from interfaces.account_applications import change_application, MergeConfirmationRequired
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'ログインが必要です。'}, status=401)
    account = get_object_or_404(User, username__iexact=username)
    if account.pk != request.user.pk:
        return JsonResponse({'error': '本人のAccountだけを変更できます。'}, status=403)
    try:
        payload = json.loads(request.body)
        if not isinstance(payload, dict):
            raise ValidationError('操作が正しくありません。')
        confirmation = payload.pop('confirmation', None)
        change_application(account, payload, confirmation)
    except MergeConfirmationRequired as error:
        return JsonResponse({'error': '版・依存Field・共有値の更新内容を確認してください。',
            'changes': error.changes, 'confirmation': error.token, 'needs_confirmation': True})
    except (json.JSONDecodeError, UnicodeDecodeError, ValidationError, ValueError, TypeError) as error:
        messages = error.messages if isinstance(error, ValidationError) else ['操作が正しくありません。']
        return JsonResponse({'error': ' '.join(messages)}, status=400)
    return JsonResponse({'ok': True})
