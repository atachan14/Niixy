from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import FieldDefinitionForm, InterfaceDraftFieldFormSet, InterfaceDraftForm
from .models import FieldDefinition, Interface, InterfaceDraft, InterfaceDraftField
from .services import publish_draft, publish_field_definition


def field_initial(field):
    return {
        'field_id': field.pk,
        'definition_id': field.definition_id,
        'required': field.required,
    }


def draft_field_formset(draft, data=None):
    fields = list(draft.fields.all())
    formset = InterfaceDraftFieldFormSet(
        data,
        prefix='fields',
        initial=[field_initial(field) for field in fields],
    )
    for form, field in zip(formset.forms, fields):
        form.definition_item = field.definition
    return formset


def mark_interface_update_status(interfaces):
    for interface in interfaces:
        interface.requires_update = bool(
            interface.current_version_id
            and any(
                field.definition.status != FieldDefinition.ACTIVE
                or field.definition.current_version_id != field.field_version_id
                for field in interface.current_version.fields.all()
            )
        )
    return interfaces


def interface_management_context(
    user,
    selected_draft_id=None,
    selected_interface_id=None,
    draft_form=None,
    field_formset=None,
):
    drafts = list(
        user.interface_drafts.select_related('interface__current_version').prefetch_related(
            'fields__definition__creator',
            'fields__definition__current_version',
        )
    )
    interfaces = mark_interface_update_status(list(
        user.interfaces.select_related('current_version')
        .prefetch_related(
            'current_version__fields__definition__creator',
            'current_version__fields__definition__current_version',
            'current_version__fields__field_version',
        )
        .order_by('name')
    ))
    selected_draft = next((draft for draft in drafts if draft.pk == selected_draft_id), None)
    selected_interface = next((item for item in interfaces if item.pk == selected_interface_id), None)
    if selected_draft:
        selected_draft.next_version_number = (
            selected_draft.interface.current_version.version_number + 1
            if selected_draft.interface_id and selected_draft.interface.current_version_id
            else 1
        )
        draft_form = draft_form or InterfaceDraftForm(initial={
            'name': selected_draft.name,
            'description': selected_draft.description,
        })
        field_formset = field_formset or draft_field_formset(selected_draft)
    return {
        'interface_drafts': drafts,
        'active_interfaces': [item for item in interfaces if item.status == Interface.ACTIVE],
        'deleted_interfaces': [item for item in interfaces if item.status == Interface.DELETED],
        'selected_interface_draft': selected_draft,
        'selected_interface': selected_interface,
        'selected_interface_dependents': 0,
        'interface_draft_form': draft_form,
        'interface_field_formset': field_formset,
    }


def interface_list_context(user):
    drafts = list(user.interface_drafts.select_related('interface__current_version'))
    interfaces = mark_interface_update_status(list(
        user.interfaces.select_related('current_version').prefetch_related(
            'current_version__fields__definition__current_version',
            'current_version__fields__field_version',
        ).order_by('name')
    ))
    return {
        'interface_drafts': drafts,
        'active_interfaces': [item for item in interfaces if item.status == Interface.ACTIVE],
        'deleted_interfaces': [item for item in interfaces if item.status == Interface.DELETED],
    }


def draft_detail_context(user, draft_id):
    draft = get_object_or_404(
        user.interface_drafts.select_related('interface__current_version').prefetch_related(
            'fields__definition__creator',
            'fields__definition__current_version',
        ),
        pk=draft_id,
    )
    draft.next_version_number = (
        draft.interface.current_version.version_number + 1
        if draft.interface_id and draft.interface.current_version_id else 1
    )
    return {
        'selected_interface_draft': draft,
        'interface_draft_form': InterfaceDraftForm(initial={
            'name': draft.name,
            'description': draft.description,
        }),
        'interface_field_formset': draft_field_formset(draft),
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
            'current_version__fields__definition__creator',
            'current_version__fields__definition__current_version',
            'current_version__fields__field_version',
        ),
        pk=interface_id,
    )
    mark_interface_update_status([interface])
    return render(request, 'interfaces/published_detail_pane.html', {
        'selected_interface': interface,
        'selected_interface_dependents': 0,
    })


def definition_detail(request, interface_id):
    visibility = Q(status=Interface.ACTIVE)
    if request.user.is_authenticated:
        visibility |= Q(creator=request.user)
    interface = get_object_or_404(
        Interface.objects.filter(visibility, current_version__isnull=False)
        .select_related('creator', 'current_version')
        .prefetch_related(
            'current_version__fields__definition__creator',
            'current_version__fields__definition__current_version',
            'current_version__fields__field_version',
            'current_version__fields__field_version__synonyms__target__creator',
        ),
        pk=interface_id,
    )
    return render(request, 'interfaces/definition_detail_content.html', {'interface_item': interface})


@login_required
def add_field_list(request, draft_id):
    draft = get_object_or_404(InterfaceDraft, pk=draft_id, creator=request.user)
    fields = list(
        FieldDefinition.objects.filter(status=FieldDefinition.ACTIVE, current_version__isnull=False)
        .select_related('creator', 'current_version')
        .order_by('creator__username', 'name')
    )
    return render(request, 'interfaces/add_field_list_pane.html', {
        'draft': draft,
        'created_fields': [item for item in fields if item.creator_id == request.user.pk],
    })


@login_required
def add_field_detail(request, draft_id, field_id):
    draft = get_object_or_404(InterfaceDraft, pk=draft_id, creator=request.user)
    candidate = get_object_or_404(
        FieldDefinition.objects.filter(status=FieldDefinition.ACTIVE, current_version__isnull=False)
        .select_related('creator', 'current_version')
        .prefetch_related('current_version__synonyms__target__creator'),
        pk=field_id,
    )
    return render(request, 'interfaces/add_field_detail_pane.html', {'candidate': candidate})


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
            'current_version__fields__definition__current_version',
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
                definition=field.definition,
                required=field.required,
                position=field.position,
            )
            for field in interface.current_version.fields.all()
        ])
    return redirect(f'/mypage/?section=interface&draft={draft.pk}')


def save_draft_forms(draft, draft_form, field_formset):
    existing_fields = {field.pk: field for field in draft.fields.all()}
    with transaction.atomic():
        draft.name = draft_form.cleaned_data['name'].strip()
        draft.description = draft_form.cleaned_data['description'].strip()
        draft.save(update_fields=['name', 'description', 'updated_at'])

        definition_ids = {
            form.cleaned_data['definition_id']
            for form in field_formset.forms
            if form.cleaned_data and not form.cleaned_data.get('DELETE')
        }
        definitions = {
            item.pk: item
            for item in FieldDefinition.objects.filter(
                pk__in=definition_ids,
                status=FieldDefinition.ACTIVE,
                current_version__isnull=False,
            ).select_related('current_version')
        }
        if len(definitions) != len(definition_ids):
            raise ValidationError('選択したFieldが見つかりません。')
        retained_ids = {
            form.cleaned_data['field_id']
            for form in field_formset.forms
            if (
                form.cleaned_data
                and not form.cleaned_data.get('DELETE')
                and form.cleaned_data.get('field_id')
            )
        }
        if not retained_ids.issubset(existing_fields):
            raise ValidationError('編集対象ではないFieldが含まれています。')
        draft.fields.exclude(pk__in=retained_ids).delete()
        position = 0
        for form in field_formset.forms:
            if not form.cleaned_data or form.cleaned_data.get('DELETE'):
                continue
            field_id = form.cleaned_data.get('field_id')
            field = existing_fields.get(field_id) if field_id else None
            if field and field.definition_id != form.cleaned_data['definition_id']:
                raise ValidationError('追加済みFieldの参照先は変更できません。')
            if field is None:
                field = InterfaceDraftField(draft=draft)
            field.definition = definitions[form.cleaned_data['definition_id']]
            field.required = form.cleaned_data['required']
            field.position = position
            field.save()
            position += 1


@login_required
@require_POST
def draft_update(request, draft_id):
    draft = get_object_or_404(
        InterfaceDraft.objects.prefetch_related('fields'),
        pk=draft_id,
        creator=request.user,
    )
    draft_form = InterfaceDraftForm(request.POST)
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


def field_form_initial(definition):
    version = definition.current_version
    return {
        'name': version.name,
        'description': version.description,
        'field_type': version.field_type,
        'options': '\n'.join(version.settings.get('options', [])),
        'synonym_targets': list(version.synonyms.values_list('target_id', flat=True)),
    }


@login_required
def field_management_list(request):
    fields = list(
        request.user.field_definitions.select_related('current_version').order_by('name')
    )
    return render(request, 'interfaces/field_management_list_pane.html', {
        'active_fields': [item for item in fields if item.status == FieldDefinition.ACTIVE],
        'deleted_fields': [item for item in fields if item.status == FieldDefinition.DELETED],
    })


@login_required
def field_create(request):
    return render(request, 'interfaces/field_editor_pane.html', {
        'field_form': FieldDefinitionForm(),
        'publication_version': 1,
        'selected_synonym_targets': [],
    })


def field_detail(request, field_id):
    visibility = Q(status=FieldDefinition.ACTIVE)
    if request.user.is_authenticated:
        visibility |= Q(creator=request.user)
    definition = get_object_or_404(
        FieldDefinition.objects.filter(visibility, current_version__isnull=False)
        .select_related('creator', 'current_version')
        .prefetch_related('current_version__synonyms__target__creator'),
        pk=field_id,
    )
    return render(request, 'interfaces/field_detail_pane.html', {'field_item': definition})


@login_required
def field_edit(request, field_id):
    definition = get_object_or_404(
        request.user.field_definitions.select_related('current_version').prefetch_related(
            'current_version__synonyms'
        ),
        pk=field_id,
        status=FieldDefinition.ACTIVE,
        current_version__isnull=False,
    )
    return render(request, 'interfaces/field_editor_pane.html', {
        'field_item': definition,
        'field_form': FieldDefinitionForm(
            definition=definition,
            initial=field_form_initial(definition),
        ),
        'publication_version': definition.current_version.version_number + 1,
        'selected_synonym_targets': [item.target for item in definition.current_version.synonyms.all()],
    })


@login_required
def add_synonym_list(request):
    source_id = request.GET.get('source')
    fields = FieldDefinition.objects.filter(
        status=FieldDefinition.ACTIVE,
        current_version__isnull=False,
    ).select_related('creator', 'current_version')
    if source_id:
        fields = fields.exclude(pk=source_id)
    fields = list(fields.order_by('creator__username', 'name'))
    return render(request, 'interfaces/add_synonym_list_pane.html', {
        'created_fields': [item for item in fields if item.creator_id == request.user.pk],
    })


@login_required
def add_synonym_detail(request, field_id):
    candidate = get_object_or_404(
        FieldDefinition.objects.filter(status=FieldDefinition.ACTIVE, current_version__isnull=False)
        .select_related('creator', 'current_version'),
        pk=field_id,
    )
    return render(request, 'interfaces/add_synonym_detail_pane.html', {'candidate': candidate})


@login_required
@require_POST
def field_publish(request, field_id=None):
    definition = None
    if field_id is not None:
        definition = get_object_or_404(FieldDefinition, pk=field_id, creator=request.user)
    form = FieldDefinitionForm(request.POST, definition=definition)
    if not form.is_valid():
        messages.error(request, ' '.join(
            str(error) for errors in form.errors.values() for error in errors
        ))
        target = f'/mypage/interfaces/manage/fields/{field_id}/edit/' if field_id else '/mypage/interfaces/manage/fields/new/'
        return redirect(target)
    try:
        definition, version = publish_field_definition(
            creator=request.user,
            definition=definition,
            name=form.cleaned_data['name'],
            description=form.cleaned_data['description'],
            field_type=form.cleaned_data['field_type'],
            settings=form.cleaned_data['settings'],
            synonym_target_ids=[item.pk for item in form.cleaned_data['synonym_targets']],
        )
    except ValidationError as error:
        messages.error(request, ' '.join(error.messages))
        return redirect('/mypage/?section=definition&kind=field')
    messages.success(request, f'{definition.name} v{version.version_number}を公開しました。')
    return redirect(f'/mypage/?section=definition&kind=field&field={definition.pk}')


@login_required
@require_POST
def field_delete(request, field_id):
    definition = get_object_or_404(FieldDefinition, pk=field_id, creator=request.user)
    definition.status = FieldDefinition.DELETED
    definition.save(update_fields=['status', 'updated_at'])
    messages.success(request, f'{definition.name}を削除しました。既存の実装では引き続き利用されます。')
    return redirect('/mypage/?section=definition&kind=field')


@login_required
@require_POST
def field_restore(request, field_id):
    definition = get_object_or_404(FieldDefinition, pk=field_id, creator=request.user)
    definition.status = FieldDefinition.ACTIVE
    definition.save(update_fields=['status', 'updated_at'])
    messages.success(request, f'{definition.name}を復元しました。')
    return redirect(f'/mypage/?section=definition&kind=field&field={definition.pk}')
