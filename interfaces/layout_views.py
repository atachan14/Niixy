import json

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import AccountLayout, AccountLayoutDraft, AccountLayoutApplication, FieldDefinition, Interface
from . import account_layouts as layouts
from .account_applications import application_catalog, application_payload
from .versioning import interface_availability


def body(request):
    if len(request.body) > 300000:
        raise ValidationError('Layout入力が大きすぎます。HTML/CSS/Itemの上限を確認してください。')
    payload = json.loads(request.body)
    if not isinstance(payload, dict):
        raise ValidationError('Layout入力を確認してください。')
    return payload


def error_response(error):
    return JsonResponse({'error': ' '.join(error.messages) if isinstance(error, ValidationError) else '入力の構文を確認してください。'}, status=400)


@login_required
def draft_detail(request, draft_id):
    draft = get_object_or_404(AccountLayoutDraft, pk=draft_id, creator=request.user)
    fields = list(FieldDefinition.objects.filter(Q(status='active', current_version__isnull=False) | Q(pk__in=draft.requirements.get('fields', []))).select_related('creator', 'current_version'))
    interfaces = list(Interface.objects.filter(kind='account').filter(Q(status='active', current_version__isnull=False) | Q(pk__in=draft.requirements.get('interfaces', []))).select_related('creator', 'current_version'))
    catalog = {'fields': [{'id': f.pk, 'name': f.name, 'creator': f.creator.username, 'version': f.current_version.version_number if f.current_version_id else 0,
                          'usable': f.status == f.ACTIVE and bool(f.current_version_id)} for f in fields],
        'interfaces': [{'id': i.pk, 'name': i.name, 'creator': i.creator.username, 'version': i.current_version.version_number if i.current_version_id else 0,
                        'usable': interface_availability(i).usable,
                        'fields': [{'id': f.definition_id, 'name': f.label, 'creator': f.definition.creator.username, 'version': f.field_version.version_number} for f in i.current_version.fields.select_related('field_version', 'definition__creator')] if i.current_version_id else []} for i in interfaces]}
    return render(request, 'interfaces/layout_draft_pane.html', {'draft': draft, 'layout_data': layouts.draft_payload(draft), 'layout_catalog': catalog})


@require_POST
def draft_create(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'ログインが必要です。'}, status=401)
    draft = AccountLayoutDraft.objects.create(creator=request.user)
    return JsonResponse({'ok': True, 'url': reverse('interfaces:layout-draft-detail', args=[draft.pk]), 'draft_id': draft.pk})


@require_POST
def draft_save(request, draft_id):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'ログインが必要です。'}, status=401)
    get_object_or_404(AccountLayoutDraft, pk=draft_id, creator=request.user)
    try:
        data = body(request)
        operation = data.get('operation')
        if operation not in {'save', 'preview', 'publish'}:
            raise ValidationError('操作を確認してください。')
        payload = data.get('layout')
        if operation == 'preview':
            return JsonResponse(layouts.preview(request.user, payload))
        result = layouts.save_draft(request.user, draft_id, payload, publish=operation == 'publish', token=data.get('token'))
        return JsonResponse({'ok': True, 'url': reverse('interfaces:layout-detail', args=[result.layout_id]) if operation == 'publish'
                             else reverse('interfaces:layout-draft-detail', args=[draft_id]), 'published': operation == 'publish'})
    except (ValidationError, ValueError, TypeError, RecursionError) as error:
        return error_response(error)


@require_POST
def draft_discard(request, draft_id):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'ログインが必要です。'}, status=401)
    get_object_or_404(AccountLayoutDraft, pk=draft_id, creator=request.user).delete()
    return JsonResponse({'ok': True, 'discarded': True})


def detail(request, layout_id):
    from accounts.content_lists import public_modules
    layout = get_object_or_404(public_modules('layout'), pk=layout_id)
    version = layout.current_version
    own = request.user.is_authenticated
    management = request.GET.get('manage') == '1'
    requirements = layouts.requirement_status(request.user, version) if own else []
    if not own:
        for r in version.require_fields.select_related('field_version__definition__creator'):
            f = r.field_version
            requirements.append({'kind': 'field', 'id': f.definition_id, 'name': f.name, 'creator': f.definition.creator.username, 'version': f.version_number})
        for r in version.require_interfaces.select_related('interface_version__interface__creator'):
            i = r.interface_version
            requirements.append({'kind': 'interface', 'id': i.interface_id, 'name': i.name, 'creator': i.interface.creator.username, 'version': i.version_number})
    return render(request, 'interfaces/layout_detail_pane.html', {'layout': layout, 'version': version,
        'requirements': requirements, 'reasons': layouts.availability(version),
        'management': management, 'can_apply': own and management and not layouts.availability(version) and all(r['ready'] for r in requirements),
        'applied_layout': AccountLayoutApplication.objects.filter(account=request.user).select_related('version').first() if own else None})


@require_POST
def edit(request, layout_id):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'ログインが必要です。'}, status=401)
    get_object_or_404(AccountLayout, pk=layout_id, creator=request.user)
    draft = layouts.edit_draft(request.user, layout_id)
    return JsonResponse({'ok': True, 'url': reverse('interfaces:layout-draft-detail', args=[draft.pk])})


@require_POST
def apply(request, username):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'ログインが必要です。'}, status=401)
    if username.casefold() != request.user.username.casefold():
        return JsonResponse({'error': '本人のAccountだけを変更できます。'}, status=403)
    try:
        data = body(request)
        if data.get('operation') == 'remove':
            with transaction.atomic():
                from django.contrib.auth import get_user_model
                get_user_model().objects.select_for_update().get(pk=request.user.pk)
                AccountLayoutApplication.objects.filter(account=request.user).delete()
        elif data.get('operation') == 'apply' and type(data.get('id')) is int and type(data.get('version')) is int:
            get_object_or_404(AccountLayout, pk=data['id'], current_version__isnull=False)
            layouts.apply_layout(request.user, data['id'], data['version'])
        else:
            raise ValidationError('操作を確認してください。')
    except (ValidationError, ValueError, TypeError) as error:
        return error_response(error)
    return JsonResponse({'ok': True})


def requirement_detail(request, kind, definition_id):
    if kind not in {'field', 'interface'}:
        from django.http import Http404
        raise Http404
    definition = get_object_or_404(FieldDefinition if kind == 'field' else Interface, pk=definition_id)
    if kind == 'interface' and definition.kind != Interface.ACCOUNT:
        from django.http import Http404
        raise Http404
    catalog = application_catalog()
    item = next((i for i in catalog['fields' if kind == 'field' else 'interfaces'] if i['id'] == definition_id), None)
    data = application_payload(request.user) if request.user.is_authenticated else None
    return render(request, 'interfaces/layout_requirement_pane.html', {'definition': definition, 'kind': kind,
        'management': request.GET.get('manage') == '1',
        'requirement_data': {'kind': kind, 'id': definition_id, 'catalog': item, 'applied': data},
        'account': request.user})
