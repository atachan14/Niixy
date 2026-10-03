from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F, Max, Value
from django.db.models.functions import Concat
from django.urls import reverse

from .models import (
    FieldDefinition,
    FieldSynonym,
    FieldType,
    FieldVersion,
    Interface,
    InterfaceDraft,
    InterfaceField,
    InterfaceVersion,
    ThreadFieldBinding,
    ThreadFieldValue,
    ThreadDirectField,
    ThreadInterfaceImplementation,
    ThreadInterfaceValue,
)


def search_field_definitions(*, name='', description='', field_type=''):
    fields = FieldDefinition.objects.filter(
        status=FieldDefinition.ACTIVE,
        current_version__isnull=False,
    ).select_related('creator', 'current_version')
    name = name.strip()
    description = description.strip()
    field_type = field_type.strip()
    if name:
        fields = fields.annotate(
            search_identity=Concat('name', Value('@'), 'creator__username'),
        ).filter(search_identity__icontains=name)
    if description:
        fields = fields.filter(current_version__description__icontains=description)
    if field_type:
        fields = fields.filter(current_version__field_type=field_type)
    return fields.order_by('-updated_at', '-pk')


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


def publish_field_definition(
    *,
    creator,
    name,
    field_type,
    settings=None,
    description='',
    synonym_target_ids=(),
    definition=None,
):
    name = name.strip()
    settings = settings or {}
    if not name:
        raise ValidationError({'name': 'Field名を入力してください。'})

    candidate = type('FieldCandidate', (), {
        'pk': definition.pk if definition else 'new',
        'settings': settings,
        'field_type': field_type,
    })()
    validate_field_settings(candidate)

    with transaction.atomic():
        if definition is None:
            try:
                definition = FieldDefinition.objects.create(creator=creator, name=name)
            except IntegrityError as error:
                raise ValidationError({'name': '同じ名前のFieldがすでに存在します。'}) from error
        else:
            definition = FieldDefinition.objects.select_for_update().get(pk=definition.pk)
            if definition.creator_id != creator.pk:
                raise ValidationError('作成者以外はFieldを更新できません。')
            if definition.status != FieldDefinition.ACTIVE:
                raise ValidationError('削除済みFieldは更新できません。')
            if definition.current_version_id and definition.current_version.field_type != field_type:
                raise ValidationError({'field_type': 'Fieldの型を変更する場合は、新しいFieldを作成してください。'})

        targets = list(
            FieldDefinition.objects.filter(
                pk__in=set(synonym_target_ids),
                status=FieldDefinition.ACTIVE,
                current_version__isnull=False,
            ).select_related('current_version')
        )
        if len(targets) != len(set(synonym_target_ids)):
            raise ValidationError({'synonyms': '選択した片同義Targetが見つかりません。'})
        if definition.pk in {target.pk for target in targets}:
            raise ValidationError({'synonyms': 'Field自身を片同義Targetにはできません。'})
        if any(target.current_version.field_type != field_type for target in targets):
            raise ValidationError({'synonyms': '同じ型のFieldだけを片同義Targetにできます。'})

        latest_number = definition.versions.aggregate(latest=Max('version_number'))['latest'] or 0
        version = FieldVersion.objects.create(
            definition=definition,
            version_number=latest_number + 1,
            name=name,
            description=description.strip(),
            field_type=field_type,
            settings=settings,
        )
        FieldSynonym.objects.bulk_create([
            FieldSynonym(source_version=version, target=target, position=position)
            for position, target in enumerate(targets)
        ])
        definition.name = name
        definition.current_version = version
        try:
            definition.save(update_fields=['name', 'current_version', 'updated_at'])
        except IntegrityError as error:
            raise ValidationError({'name': '同じ名前のFieldがすでに存在します。'}) from error
    return definition, version


def expand_field_definition_ids(definition_ids):
    """Expand search fields through current one-way synonym edges."""
    expanded = set(definition_ids)
    pending = list(expanded)
    while pending:
        source_id = pending.pop()
        target_ids = FieldSynonym.objects.filter(
            source_version__definition_id=source_id,
            source_version__definition__current_version_id=F('source_version_id'),
        ).values_list('target_id', flat=True)
        for target_id in target_ids:
            if target_id not in expanded:
                expanded.add(target_id)
                pending.append(target_id)
    return expanded


@transaction.atomic
def publish_draft(draft_id):
    draft = (
        InterfaceDraft.objects.select_for_update()
        .select_related('creator')
        .prefetch_related('fields__definition__current_version')
        .get(pk=draft_id)
    )
    name = draft.name.strip()
    if not name:
        raise ValidationError({'name': 'Interface名を入力してください。'})

    fields = list(draft.fields.all())
    resolved_fields = []
    for field in fields:
        definition = field.definition
        field_version = definition.current_version
        if definition.status != FieldDefinition.ACTIVE or field_version is None:
            raise ValidationError({'fields': f'{definition.name}は現在利用できません。'})
        resolved_fields.append((field, definition, field_version))

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
            definition=definition,
            field_version=field_version,
            required=field.required,
            position=field.position,
        )
        for field, definition, field_version in resolved_fields
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
        for item in Interface.objects.filter(pk__in=interface_ids).select_related(
            'current_version'
        ).prefetch_related(
            'current_version__fields__definition__current_version',
            'current_version__fields__field_version__synonyms',
        )
    }
    if len(interfaces) != len(set(interface_ids)):
        raise ValidationError({'interfaces': '選択したInterfaceが見つかりません。'})

    resolved = []
    for interface_id in interface_ids:
        interface = interfaces[interface_id]
        if interface.status != Interface.ACTIVE or interface.current_version_id is None:
            raise ValidationError({'interfaces': f'{interface.name}は現在利用できません。'})
        for field in interface.current_version.fields.all():
            if (
                field.definition.status != FieldDefinition.ACTIVE
                or field.definition.current_version_id != field.field_version_id
            ):
                raise ValidationError({'interfaces': f'{interface.name}はFieldの更新が必要です。'})
        resolved.append(interface.current_version)
    return resolved


def resolve_direct_field_versions(definition_ids):
    if len(definition_ids) != len(set(definition_ids)):
        raise ValidationError({'direct_fields': '同じFieldを重複して追加できません。'})
    definitions = {
        item.pk: item
        for item in FieldDefinition.objects.filter(pk__in=definition_ids).select_related(
            'creator', 'current_version'
        ).prefetch_related('current_version__synonyms')
    }
    if len(definitions) != len(set(definition_ids)):
        raise ValidationError({'direct_fields': '選択したFieldが見つかりません。'})

    resolved = []
    for definition_id in definition_ids:
        definition = definitions[definition_id]
        if definition.status != FieldDefinition.ACTIVE or definition.current_version_id is None:
            raise ValidationError({'direct_fields': f'{definition.name}は現在利用できません。'})
        resolved.append(definition.current_version)
    return resolved


def normalize_field_value(field, raw_values, *, required=None):
    if required is None:
        required = field.required
    values = [value for value in raw_values if value != '']
    if not values:
        if required:
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


def _connected_field_components(fields):
    definitions = {field.definition_id for field in fields}
    graph = {definition_id: set() for definition_id in definitions}
    for field in fields:
        version = getattr(field, 'field_version', field)
        for target_id in version.synonyms.values_list('target_id', flat=True):
            if target_id in definitions:
                graph[field.definition_id].add(target_id)
                graph[target_id].add(field.definition_id)

    component_by_definition = {}
    for definition_id in definitions:
        if definition_id in component_by_definition:
            continue
        component = set()
        pending = [definition_id]
        while pending:
            current = pending.pop()
            if current in component:
                continue
            component.add(current)
            pending.extend(graph[current] - component)
        anchor = min(component)
        for item in component:
            component_by_definition[item] = anchor
    return component_by_definition


def prepare_thread_fields(direct_field_ids, direct_value_lists, interface_ids, interface_value_lists):
    direct_versions = resolve_direct_field_versions(direct_field_ids)
    versions = resolve_interface_versions(interface_ids)
    all_fields = direct_versions + [field for version in versions for field in version.fields.all()]
    component_by_definition = _connected_field_components(all_fields)
    supplied_values = {}
    prepared_direct_fields = []
    for version in direct_versions:
        value = normalize_field_value(
            version,
            direct_value_lists.get(str(version.field_key), []),
            required=True,
        )
        component = component_by_definition.get(version.definition_id, version.definition_id)
        supplied_values.setdefault(component, value)
        prepared_direct_fields.append((version, component))

    normalized = []
    for version in versions:
        field_values = []
        for field in version.fields.all():
            raw_values = interface_value_lists.get((version.interface_id, str(field.field_key)), [])
            required = field.required
            value = normalize_field_value(field, raw_values, required=False)
            component = component_by_definition.get(field.definition_id, field.definition_id)
            if value is not None:
                supplied_values.setdefault(component, value)
            field_values.append((field, component, required))
        normalized.append((version, field_values))

    prepared_interfaces = []
    for version, field_values in normalized:
        resolved_values = []
        for field, component, required in field_values:
            value = supplied_values.get(component)
            if required and value is None:
                raise ValidationError({str(field.field_key): f'{field.label}は必須です。'})
            resolved_values.append((field, value, component))
        prepared_interfaces.append((version, resolved_values))
    prepared_direct_fields = [
        (version, supplied_values[component], component)
        for version, component in prepared_direct_fields
    ]
    return prepared_direct_fields, prepared_interfaces


def prepare_thread_interfaces(interface_ids, value_lists):
    return prepare_thread_fields([], {}, interface_ids, value_lists)[1]


def save_thread_fields(thread, prepared_direct_fields, prepared_interfaces):
    values_by_component = {}
    for position, (version, value, component) in enumerate(prepared_direct_fields):
        shared_value = values_by_component.get(component)
        if shared_value is None:
            shared_value = ThreadFieldValue.objects.create(thread=thread, value=value)
            values_by_component[component] = shared_value
        binding, _ = ThreadFieldBinding.objects.get_or_create(
            thread=thread,
            definition=version.definition,
            defaults={'value': shared_value},
        )
        ThreadDirectField.objects.create(
            thread=thread,
            definition=version.definition,
            version=version,
            binding=binding,
            position=position,
        )

    for position, (version, field_values) in enumerate(prepared_interfaces):
        implementation = ThreadInterfaceImplementation.objects.create(
            thread=thread,
            interface=version.interface,
            version=version,
            position=position,
        )
        interface_values = []
        for field, value, component in field_values:
            if value is None:
                continue
            shared_value = values_by_component.get(component)
            if shared_value is None:
                shared_value = ThreadFieldValue.objects.create(thread=thread, value=value)
                values_by_component[component] = shared_value
            binding, _ = ThreadFieldBinding.objects.get_or_create(
                thread=thread,
                definition=field.definition,
                defaults={'value': shared_value},
            )
            if binding.value_id != shared_value.pk:
                shared_value = binding.value
                values_by_component[component] = shared_value
            interface_values.append(ThreadInterfaceValue(
                implementation=implementation,
                field=field,
                binding=binding,
            ))
        ThreadInterfaceValue.objects.bulk_create(interface_values)


def save_thread_interfaces(thread, prepared):
    save_thread_fields(thread, [], prepared)


def thread_field_catalog():
    fields = search_field_definitions().prefetch_related('current_version__synonyms')
    return [
        {
            'id': definition.pk,
            'detail_url': reverse('interfaces:field-detail', args=[definition.pk]),
            'name': definition.name,
            'creator': definition.creator.username,
            'version': definition.current_version.version_number,
            'updated_at': definition.updated_at,
            'description': definition.current_version.description,
            'key': str(definition.key),
            'type': definition.current_version.field_type,
            'type_label': definition.current_version.get_field_type_display(),
            'settings': definition.current_version.settings,
            'definition_id': definition.pk,
            'synonym_target_ids': list(
                definition.current_version.synonyms.values_list('target_id', flat=True)
            ),
        }
        for definition in fields
    ]


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
            'requires': [],
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
                            'definition_id': field.definition_id,
                            'synonym_target_ids': list(
                                field.field_version.synonyms.values_list('target_id', flat=True)
                            ),
                        }
                        for field in version.fields.all()
                    ],
                }
                for version in versions
            ],
        })
    return catalog
