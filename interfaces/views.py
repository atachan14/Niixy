from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import InterfaceDraftFieldFormSet, InterfaceDraftForm
from .models import FieldType, Interface, InterfaceDraft, InterfaceDraftField, InterfaceDraftRequirement
from .services import publish_draft


def field_initial(field):
    options = field.settings.get('options', []) if isinstance(field.settings, dict) else []
    return {
        'field_id': field.pk,
        'label': field.label,
        'field_type': field.field_type,
        'required': field.required,
        'options': '\n'.join(options),
    }


def interface_management_context(
    user,
    selected_draft_id=None,
    selected_interface_id=None,
    draft_form=None,
    field_formset=None,
):
    drafts = list(
        user.interface_drafts.select_related('interface__current_version').prefetch_related(
            'fields',
            'requirements__required_interface__creator',
            'requirements__required_interface__current_version__fields',
        )
    )
    interfaces = list(
        user.interfaces.select_related('current_version')
        .prefetch_related(
            'current_version__fields',
            'current_version__requirements__required_interface__creator',
        )
        .order_by('name')
    )
    selected_draft = next((draft for draft in drafts if draft.pk == selected_draft_id), None)
    selected_interface = next((item for item in interfaces if item.pk == selected_interface_id), None)
    if selected_draft:
        selected_draft.next_version_number = (
            selected_draft.interface.current_version.version_number + 1
            if selected_draft.interface_id and selected_draft.interface.current_version_id
            else 1
        )
        draft_form = draft_form or InterfaceDraftForm(user=user, draft=selected_draft, initial={
            'name': selected_draft.name,
            'description': selected_draft.description,
            'required_interfaces': [item.required_interface_id for item in selected_draft.requirements.all()],
        })
        field_formset = field_formset or InterfaceDraftFieldFormSet(
            prefix='fields',
            initial=[field_initial(field) for field in selected_draft.fields.all()],
        )
    require_candidates = []
    if draft_form:
        require_candidates = list(
            draft_form.fields['required_interfaces'].queryset.prefetch_related('current_version__fields')
        )
    return {
        'interface_drafts': drafts,
        'active_interfaces': [item for item in interfaces if item.status == Interface.ACTIVE],
        'deleted_interfaces': [item for item in interfaces if item.status == Interface.DELETED],
        'selected_interface_draft': selected_draft,
        'selected_interface': selected_interface,
        'selected_interface_dependents': (
            selected_interface.version_dependents.values('version__interface_id').distinct().count()
            if selected_interface else 0
        ),
        'interface_draft_form': draft_form,
        'interface_field_formset': field_formset,
        'interface_require_candidates': require_candidates,
        'interface_require_created': [item for item in require_candidates if item.creator_id == user.pk],
        'field_type_choices': FieldType.choices,
    }


def interface_list_context(user):
    drafts = list(user.interface_drafts.select_related('interface__current_version'))
    interfaces = list(user.interfaces.select_related('current_version').order_by('name'))
    return {
        'interface_drafts': drafts,
        'active_interfaces': [item for item in interfaces if item.status == Interface.ACTIVE],
        'deleted_interfaces': [item for item in interfaces if item.status == Interface.DELETED],
    }


def draft_detail_context(user, draft_id):
    draft = get_object_or_404(
        user.interface_drafts.select_related('interface__current_version').prefetch_related(
            'fields',
            'requirements__required_interface__creator',
            'requirements__required_interface__current_version__fields',
        ),
        pk=draft_id,
    )
    draft.next_version_number = (
        draft.interface.current_version.version_number + 1
        if draft.interface_id and draft.interface.current_version_id else 1
    )
    requirements = [item.required_interface for item in draft.requirements.all()]
    return {
        'selected_interface_draft': draft,
        'interface_draft_form': InterfaceDraftForm(user=user, draft=draft, initial={
            'name': draft.name,
            'description': draft.description,
            'required_interfaces': [item.pk for item in requirements],
        }),
        'interface_field_formset': InterfaceDraftFieldFormSet(
            prefix='fields',
            initial=[field_initial(field) for field in draft.fields.all()],
        ),
        'selected_require_interfaces': requirements,
    }


@login_required
def management_list(request):
    return render(request, 'interfaces/management_list_pane.html', interface_list_context(request.user))


@login_required
def draft_detail(request, draft_id):
    context = draft_detail_context(request.user, draft_id)
    context['account'] = request.user
    return render(request, 'interfaces/definition_detail_pane.html', context)


@login_required
def published_detail(request, interface_id):
    interface = get_object_or_404(
        request.user.interfaces.select_related('current_version').prefetch_related(
            'current_version__fields',
            'current_version__requirements__required_interface__creator',
        ),
        pk=interface_id,
    )
    return render(request, 'interfaces/published_detail_pane.html', {
        'selected_interface': interface,
        'selected_interface_dependents': interface.version_dependents.values(
            'version__interface_id'
        ).distinct().count(),
    })


@login_required
def add_require_list(request, draft_id):
    draft = get_object_or_404(InterfaceDraft, pk=draft_id, creator=request.user)
    candidates = list(
        Interface.objects.filter(status=Interface.ACTIVE, current_version__isnull=False)
        .exclude(pk=draft.interface_id)
        .select_related('creator', 'current_version')
        .order_by('creator__username', 'name')
    )
    return render(request, 'interfaces/add_require_list_pane.html', {
        'draft': draft,
        'interface_require_created': [item for item in candidates if item.creator_id == request.user.pk],
    })


@login_required
def add_require_detail(request, draft_id, interface_id):
    draft = get_object_or_404(InterfaceDraft, pk=draft_id, creator=request.user)
    candidate = get_object_or_404(
        Interface.objects.filter(status=Interface.ACTIVE, current_version__isnull=False)
        .exclude(pk=draft.interface_id)
        .select_related('creator', 'current_version')
        .prefetch_related('current_version__fields'),
        pk=interface_id,
    )
    return render(request, 'interfaces/add_require_detail_pane.html', {'candidate': candidate})


@login_required
@require_POST
def draft_create(request):
    draft = InterfaceDraft.objects.create(
        creator=request.user,
        kind=Interface.THREAD,
        name='新しいInterface',
    )
    return redirect(f'/mypage/?section=interface&draft={draft.pk}')


@login_required
@require_POST
def draft_edit(request, interface_id):
    interface = get_object_or_404(
        Interface.objects.select_related('current_version').prefetch_related(
            'current_version__fields',
            'current_version__requirements',
        ),
        pk=interface_id,
        creator=request.user,
        status=Interface.ACTIVE,
        current_version__isnull=False,
    )
    draft, created = InterfaceDraft.objects.get_or_create(
        interface=interface,
        defaults={
            'creator': request.user,
            'kind': interface.kind,
            'name': interface.current_version.name,
            'description': interface.current_version.description,
        },
    )
    if created:
        InterfaceDraftField.objects.bulk_create([
            InterfaceDraftField(
                draft=draft,
                field_key=field.field_key,
                label=field.label,
                field_type=field.field_type,
                required=field.required,
                settings=field.settings,
                position=field.position,
            )
            for field in interface.current_version.fields.all()
        ])
        InterfaceDraftRequirement.objects.bulk_create([
            InterfaceDraftRequirement(
                draft=draft,
                required_interface=requirement.required_interface,
                position=requirement.position,
            )
            for requirement in interface.current_version.requirements.all()
        ])
    return redirect(f'/mypage/?section=interface&draft={draft.pk}')


def save_draft_forms(draft, draft_form, field_formset):
    existing_fields = {field.pk: field for field in draft.fields.all()}
    submitted_ids = set()
    with transaction.atomic():
        draft.name = draft_form.cleaned_data['name'].strip()
        draft.description = draft_form.cleaned_data['description'].strip()
        draft.save(update_fields=['name', 'description', 'updated_at'])

        draft.requirements.all().delete()
        InterfaceDraftRequirement.objects.bulk_create([
            InterfaceDraftRequirement(draft=draft, required_interface=required, position=position)
            for position, required in enumerate(draft_form.cleaned_data['required_interfaces'])
        ])

        position = 0
        for form in field_formset.forms:
            if not form.cleaned_data or form.cleaned_data.get('DELETE'):
                continue
            field_id = form.cleaned_data.get('field_id')
            field = existing_fields.get(field_id) if field_id else None
            if field_id and field is None:
                raise ValidationError('編集対象ではないFieldが含まれています。')
            settings = {}
            if form.cleaned_data['field_type'] in {FieldType.SINGLE_CHOICE, FieldType.MULTIPLE_CHOICE}:
                settings = {'options': form.cleaned_data['normalized_options']}
            if field is None:
                field = InterfaceDraftField(draft=draft)
            field.label = form.cleaned_data['label'].strip()
            field.field_type = form.cleaned_data['field_type']
            field.required = form.cleaned_data['required']
            field.settings = settings
            field.position = position
            field.save()
            submitted_ids.add(field.pk)
            position += 1
        draft.fields.exclude(pk__in=submitted_ids).delete()


@login_required
@require_POST
def draft_update(request, draft_id):
    draft = get_object_or_404(
        InterfaceDraft.objects.prefetch_related('fields'),
        pk=draft_id,
        creator=request.user,
    )
    draft_form = InterfaceDraftForm(request.POST, user=request.user, draft=draft)
    field_formset = InterfaceDraftFieldFormSet(request.POST, prefix='fields')
    if not draft_form.is_valid() or not field_formset.is_valid():
        errors = []
        for field_errors in draft_form.errors.values():
            errors.extend(str(error) for error in field_errors)
        for form in field_formset.forms:
            for field_errors in form.errors.values():
                errors.extend(str(error) for error in field_errors)
        errors.extend(str(error) for error in field_formset.non_form_errors())
        messages.error(request, ' '.join(errors) or '入力内容を確認してください。')
        return redirect(f'/mypage/?section=interface&draft={draft.pk}')

    try:
        save_draft_forms(draft, draft_form, field_formset)
        if request.POST.get('action') == 'publish':
            interface, version = publish_draft(draft.pk)
            messages.success(request, f'{interface.name} v{version.version_number}を公開しました。')
            return redirect('/mypage/?section=interface')
    except ValidationError as error:
        messages.error(request, ' '.join(error.messages))
        return redirect(f'/mypage/?section=interface&draft={draft.pk}')

    messages.success(request, 'Draftを保存しました。')
    return redirect(f'/mypage/?section=interface&draft={draft.pk}')


@login_required
@require_POST
def draft_discard(request, draft_id):
    draft = get_object_or_404(InterfaceDraft, pk=draft_id, creator=request.user)
    draft.delete()
    messages.success(request, 'Draftを破棄しました。')
    return redirect('/mypage/?section=interface')


@login_required
@require_POST
def interface_delete(request, interface_id):
    interface = get_object_or_404(Interface, pk=interface_id, creator=request.user)
    interface.status = Interface.DELETED
    interface.save(update_fields=['status', 'updated_at'])
    messages.success(request, f'{interface.name}を削除しました。既存の実装では引き続き利用されます。')
    return redirect('/mypage/?section=interface')


@login_required
@require_POST
def interface_restore(request, interface_id):
    interface = get_object_or_404(Interface, pk=interface_id, creator=request.user)
    interface.status = Interface.ACTIVE
    interface.save(update_fields=['status', 'updated_at'])
    messages.success(request, f'{interface.name}を復元しました。')
    return redirect(f'/mypage/?section=interface&interface={interface.pk}')
