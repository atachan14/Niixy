from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.urls import reverse

from .models import (
    FieldType,
    Interface,
    InterfaceDraft,
    InterfaceField,
    InterfaceRequirement,
    InterfaceVersion,
    ThreadInterfaceImplementation,
    ThreadInterfaceValue,
)


def validate_field_settings(field):
    settings = field.settings
    if not isinstance(settings, dict):
        raise ValidationError({f'field:{field.pk}': 'Field設定はObject形式で入力してください。'})

    if field.field_type in {FieldType.SINGLE_CHOICE, FieldType.MULTIPLE_CHOICE}:
        options = settings.get('options')
        if not isinstance(options, list) or not options:
            raise ValidationError({f'field:{field.pk}': '選択型には一つ以上の選択肢が必要です。'})
        if any(not isinstance(option, str) or not option.strip() for option in options):
            raise ValidationError({f'field:{field.pk}': '選択肢は空でない文字列にしてください。'})
        normalized = [option.strip() for option in options]
        if len(normalized) != len(set(normalized)):
            raise ValidationError({f'field:{field.pk}': '同じ選択肢を重複して指定できません。'})
    elif settings:
        raise ValidationError({f'field:{field.pk}': 'このField型には設定を指定できません。'})


def requirement_reaches(requirement_version, target_interface_id, visited=None):
    visited = visited or set()
    if requirement_version.interface_id == target_interface_id:
        return True
    if requirement_version.pk in visited:
        return False
    visited.add(requirement_version.pk)
    return any(
        requirement_reaches(requirement.required_version, target_interface_id, visited)
        for requirement in requirement_version.requirements.select_related(
            'required_version__interface'
        )
    )


@transaction.atomic
def publish_draft(draft_id):
    draft = (
        InterfaceDraft.objects.select_for_update()
        .select_related('creator')
        .prefetch_related('fields', 'requirements__required_interface__current_version')
        .get(pk=draft_id)
    )
    name = draft.name.strip()
    if not name:
        raise ValidationError({'name': 'Interface名を入力してください。'})

    fields = list(draft.fields.all())
    for field in fields:
        validate_field_settings(field)

    if draft.interface_id is None:
        try:
            interface = Interface.objects.create(creator=draft.creator, kind=draft.kind, name=name)
        except IntegrityError as error:
            raise ValidationError({'name': '同じ名前のInterfaceがすでに存在します。'}) from error
    else:
        interface = Interface.objects.select_for_update().get(pk=draft.interface_id)
        if interface.creator_id != draft.creator_id:
            raise ValidationError('作成者以外はInterfaceを公開できません。')
        if interface.status != Interface.ACTIVE:
            raise ValidationError('削除済みInterfaceは公開できません。')

    requirements = list(draft.requirements.select_related('required_interface__current_version'))
    resolved_requirements = []
    for requirement in requirements:
        required_interface = requirement.required_interface
        if required_interface.status != Interface.ACTIVE or required_interface.current_version_id is None:
            raise ValidationError({'requirements': f'{required_interface.name}は現在利用できません。'})
        if required_interface.pk == interface.pk or requirement_reaches(required_interface.current_version, interface.pk):
            raise ValidationError({'requirements': 'InterfaceのRequire関係を循環させることはできません。'})
        resolved_requirements.append((requirement, required_interface.current_version))

    latest_number = interface.versions.aggregate(latest=Max('version_number'))['latest'] or 0
    version = InterfaceVersion.objects.create(
        interface=interface,
        version_number=latest_number + 1,
        name=name,
        description=draft.description.strip(),
    )
    InterfaceField.objects.bulk_create([
        InterfaceField(
            version=version,
            field_key=field.field_key,
            label=field.label.strip(),
            field_type=field.field_type,
            required=field.required,
            settings=field.settings,
            position=field.position,
        )
        for field in fields
    ])
    InterfaceRequirement.objects.bulk_create([
        InterfaceRequirement(
            version=version,
            required_interface=requirement.required_interface,
            required_version=required_version,
            position=requirement.position,
        )
        for requirement, required_version in resolved_requirements
    ])
    interface.name = name
    interface.kind = draft.kind
    interface.current_version = version
    interface.save(update_fields=['name', 'kind', 'current_version', 'updated_at'])
    draft.delete()
    return interface, version


def resolve_interface_versions(interface_ids):
    interfaces = {
        item.pk: item
        for item in Interface.objects.filter(pk__in=interface_ids).select_related('current_version')
    }
    if len(interfaces) != len(set(interface_ids)):
        raise ValidationError({'interfaces': '選択したInterfaceが見つかりません。'})

    resolved = []
    visited = set()

    def visit(interface):
        if interface.pk in visited:
            return
        if interface.status != Interface.ACTIVE or interface.current_version_id is None:
            raise ValidationError({'interfaces': f'{interface.name}は現在利用できません。'})
        for requirement in interface.current_version.requirements.select_related(
            'required_interface', 'required_version'
        ):
            required = requirement.required_interface
            if required.status != Interface.ACTIVE or required.current_version_id != requirement.required_version_id:
                raise ValidationError({'interfaces': f'{interface.name}のRequire関係は更新が必要です。'})
            visit(required)
        visited.add(interface.pk)
        resolved.append(interface.current_version)

    for interface_id in interface_ids:
        visit(interfaces[interface_id])
    return resolved


def normalize_field_value(field, raw_values):
    values = [value for value in raw_values if value != '']
    if not values:
        if field.required:
            raise ValidationError({str(field.field_key): f'{field.label}は必須です。'})
        return None

    raw = values[-1]
    try:
        if field.field_type in {FieldType.SHORT_TEXT, FieldType.LONG_TEXT}:
            return raw
        if field.field_type == FieldType.INTEGER:
            return int(raw)
        if field.field_type == FieldType.DECIMAL:
            return str(Decimal(raw))
        if field.field_type == FieldType.DATE:
            return date.fromisoformat(raw).isoformat()
        if field.field_type == FieldType.DATETIME:
            return datetime.fromisoformat(raw).isoformat()
        if field.field_type == FieldType.BOOLEAN:
            if raw not in {'true', 'false'}:
                raise ValueError
            return raw == 'true'
        options = field.settings.get('options', [])
        if field.field_type == FieldType.SINGLE_CHOICE:
            if raw not in options:
                raise ValueError
            return raw
        if field.field_type == FieldType.MULTIPLE_CHOICE:
            selected = list(dict.fromkeys(values))
            if any(value not in options for value in selected):
                raise ValueError
            return selected
    except (ValueError, InvalidOperation):
        raise ValidationError({str(field.field_key): f'{field.label}の値が正しくありません。'})
    raise ValidationError({str(field.field_key): f'{field.label}の型に対応していません。'})


def prepare_thread_interfaces(interface_ids, value_lists):
    versions = resolve_interface_versions(interface_ids)
    prepared = []
    for version in versions:
        field_values = []
        for field in version.fields.all():
            raw_values = value_lists.get((version.interface_id, str(field.field_key)), [])
            value = normalize_field_value(field, raw_values)
            if value is not None:
                field_values.append((field, value))
        prepared.append((version, field_values))
    return prepared


def save_thread_interfaces(thread, prepared):
    for position, (version, field_values) in enumerate(prepared):
        implementation = ThreadInterfaceImplementation.objects.create(
            thread=thread,
            interface=version.interface,
            version=version,
            position=position,
        )
        ThreadInterfaceValue.objects.bulk_create([
            ThreadInterfaceValue(implementation=implementation, field=field, value=value)
            for field, value in field_values
        ])


def thread_interface_catalog():
    catalog = []
    interfaces = Interface.objects.filter(
        kind=Interface.THREAD,
        status=Interface.ACTIVE,
        current_version__isnull=False,
    ).select_related('creator', 'current_version')
    for interface in interfaces:
        try:
            versions = resolve_interface_versions([interface.pk])
        except ValidationError:
            continue
        catalog.append({
            'id': interface.pk,
            'detail_url': reverse('interfaces:definition-detail', args=[interface.pk]),
            'name': interface.name,
            'creator': interface.creator.username,
            'version': interface.current_version.version_number,
            'kind': interface.get_kind_display(),
            'updated_at': interface.updated_at,
            'description': interface.current_version.description,
            'requires': [
                {
                    'id': version.interface_id,
                    'name': version.name,
                    'creator': version.interface.creator.username,
                    'version': version.version_number,
                }
                for version in versions[:-1]
            ],
            'implementations': [
                {
                    'id': version.interface_id,
                    'name': version.name,
                    'creator': version.interface.creator.username,
                    'version': version.version_number,
                    'fields': [
                        {
                            'key': str(field.field_key),
                            'label': field.label,
                            'type': field.field_type,
                            'type_label': field.get_field_type_display(),
                            'required': field.required,
                            'settings': field.settings,
                        }
                        for field in version.fields.all()
                    ],
                }
                for version in versions
            ],
        })
    return catalog
