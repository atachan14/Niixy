"""Account-scoped, fixed-version Field applications and shared values."""
import hashlib
import json
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max
from django.urls import reverse

from .models import (AccountDirectField, AccountFieldBinding, AccountFieldValue,
    AccountInterfaceImplementation, AccountInterfaceValue, Interface)
from .services import (_connected_field_components, normalize_field_value,
    resolve_direct_field_versions, resolve_interface_versions, thread_field_catalog)


class MergeConfirmationRequired(Exception):
    def __init__(self, changes, token):
        self.changes = changes
        self.token = token


def raw_values(value):
    if value is None:
        return []
    if isinstance(value, bool):
        return ['true' if value else 'false']
    return [str(item) for item in value] if isinstance(value, list) else [str(value)]


def _field(version, required):
    return SimpleNamespace(definition_id=version.definition_id, field_version=version,
        field_type=version.field_type, settings=version.settings, field_key=version.field_key,
        label=version.label, required=required)


def applied_fields(account):
    direct = list(account.direct_fields.select_related('version', 'definition__creator', 'binding__value'))
    implementations = list(account.interface_implementations.select_related('version', 'interface__creator')
        .prefetch_related('values__field__field_version__synonyms', 'values__binding__value',
                         'version__fields__field_version__synonyms'))
    fields = [_field(item.version, True) for item in direct]
    fields += [field for implementation in implementations for field in implementation.version.fields.all()]
    return direct, implementations, fields


def _next_position(manager):
    return (manager.aggregate(last=Max('position'))['last'] or 0) + 1


def _validate_component(fields, value):
    types = {field.field_type for field in fields}
    if len(types) != 1:
        raise ValidationError('固定版Fieldの型が一致しないため値を共有できません。')
    for field in fields:
        normalized = normalize_field_value(field, raw_values(value), required=field.required)
        if normalized != value:
            raise ValidationError('固定版Fieldの制約が一致しないため値を共有できません。')


def _confirmation_token(account, payload, bindings, versions, changes):
    state = {'account': account.pk, 'payload': payload,
        'bindings': [(item.pk, item.definition_id, item.value_id, item.value.value) for item in bindings],
        'versions': [getattr(item, 'field_version', item).pk for item in versions], 'changes': changes}
    digest = hashlib.sha256(json.dumps(state, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return signing.dumps({'account': account.pk, 'digest': digest}, salt='account-field-merge')


def _token_matches(token, expected):
    try:
        return signing.loads(token, salt='account-field-merge', max_age=600) == signing.loads(expected, salt='account-field-merge')
    except (signing.BadSignature, TypeError):
        return False


@transaction.atomic
def change_application(account, payload, confirmation=None):
    account = get_user_model().objects.select_for_update().get(pk=account.pk)
    if not isinstance(payload, dict):
        raise ValidationError('操作が正しくありません。')
    operation = payload.get('operation')
    direct, implementations, fields = applied_fields(account)
    bindings = list(account.field_bindings.select_related('value').order_by('created_at', 'pk'))
    if operation in {'remove_field', 'remove_interface'}:
        manager = account.direct_fields if operation == 'remove_field' else account.interface_implementations
        try:
            item = manager.get(pk=payload.get('id'))
        except (manager.model.DoesNotExist, ValueError, TypeError) as error:
            raise ValidationError('適用済み項目が見つかりません。') from error
        item.delete()
        # Retain bindings/values still referenced by another application.
        account.field_bindings.filter(direct_implementations__isnull=True, interface_values__isnull=True).delete()
        account.field_values.filter(bindings__isnull=True).delete()
        return
    if operation in {'edit_value', 'edit_values'}:
        updates = payload.get('updates') if operation == 'edit_values' else [{'id': payload.get('id'), 'values': payload.get('values')}]
        if not isinstance(updates, list) or not updates:
            raise ValidationError('値が正しくありません。')
        prepared = {}
        for update in updates:
            try:
                binding = next(item for item in bindings if item.pk == int(update.get('id')))
            except (StopIteration, TypeError, ValueError, AttributeError) as error:
                raise ValidationError('値が見つかりません。') from error
            related = [field for field in fields if any(item.definition_id == field.definition_id
                and item.value_id == binding.value_id for item in bindings)]
            raw = update.get('values')
            if not isinstance(raw, list) or any(not isinstance(item, str) for item in raw):
                raise ValidationError('値が正しくありません。')
            value = normalize_field_value(related[0], raw, required=any(field.required for field in related))
            _validate_component(related, value)
            if binding.value_id in prepared and prepared[binding.value_id][1] != value:
                raise ValidationError('共有値に異なる値を指定できません。')
            prepared[binding.value_id] = (binding.value, value)
        for shared, value in prepared.values():
            if shared.value != value:
                shared.value = value
                shared.save(update_fields=['value', 'updated_at'])
        return
    if operation not in {'add_field', 'add_interface'}:
        raise ValidationError('操作が正しくありません。')
    try:
        definition_id = int(payload.get('id'))
    except (TypeError, ValueError) as error:
        raise ValidationError('選択項目が正しくありません。') from error
    supplied = payload.get('values', {})
    if not isinstance(supplied, dict) or any(not isinstance(value, list)
        or any(not isinstance(item, str) for item in value) for value in supplied.values()):
        raise ValidationError('値が正しくありません。')
    if operation == 'add_field':
        if account.direct_fields.filter(definition_id=definition_id).exists():
            raise ValidationError('同じFieldを重複して追加できません。')
        version = resolve_direct_field_versions([definition_id])[0]
        new_fields = [_field(version, True)]
    else:
        if account.interface_implementations.filter(interface_id=definition_id).exists():
            raise ValidationError('同じAccountIFを重複して追加できません。')
        version = resolve_interface_versions([definition_id])[0]
        if version.interface.kind != Interface.ACCOUNT:
            raise ValidationError('AccountIFだけを適用できます。')
        new_fields = list(version.fields.all())
    all_fields = fields + new_fields
    components = _connected_field_components(all_fields)
    plans = []
    changes = []
    for component in sorted(set(components.values())):
        component_fields = [field for field in all_fields if components[field.definition_id] == component]
        existing = [binding for binding in bindings if components.get(binding.definition_id) == component]
        incoming = [field for field in new_fields if components[field.definition_id] == component]
        if existing:
            shared = existing[0].value
            value = shared.value
        else:
            shared = None
            values = [(field, normalize_field_value(field, supplied.get(str(field.field_key), []), required=False)) for field in incoming]
            value = next((value for _, value in values if value is not None), None)
        _validate_component(component_fields, value)
        for binding in existing:
            if binding.value.value != value:
                label = next(field.label for field in component_fields if field.definition_id == binding.definition_id)
                changes.append({'field': label, 'before': binding.value.value, 'after': value})
        for field in incoming:
            if str(field.field_key) in supplied:
                given = normalize_field_value(field, supplied[str(field.field_key)], required=False)
                if given is not None and given != value:
                    changes.append({'field': field.label, 'before': given, 'after': value})
        plans.append((component_fields, existing, shared, value))
    if changes:
        expected = _confirmation_token(account, payload, bindings, all_fields, changes)
        if not _token_matches(confirmation, expected):
            raise MergeConfirmationRequired(changes, expected)
    # Validation and preview complete before writing any application or value.
    binding_by_definition = {binding.definition_id: binding for binding in bindings}
    for component_fields, existing, shared, value in plans:
        if shared is None:
            shared = AccountFieldValue.objects.create(account=account, value=value)
        if any(binding.value.value != value for binding in existing):
            shared.save(update_fields=['updated_at'])
        for binding in existing:
            if binding.value_id != shared.pk:
                binding.value = shared
                binding.save(update_fields=['value'])
        for field in component_fields:
            if field.definition_id not in binding_by_definition:
                binding_by_definition[field.definition_id] = AccountFieldBinding.objects.create(
                    account=account, definition_id=field.definition_id, value=shared)
    if operation == 'add_field':
        AccountDirectField.objects.create(account=account, definition=version.definition, version=version,
            binding=binding_by_definition[version.definition_id], position=_next_position(account.direct_fields))
    else:
        implementation = AccountInterfaceImplementation.objects.create(account=account,
            interface=version.interface, version=version, position=_next_position(account.interface_implementations))
        AccountInterfaceValue.objects.bulk_create([AccountInterfaceValue(implementation=implementation,
            field=field, binding=binding_by_definition[field.definition_id]) for field in new_fields])
    account.field_values.filter(bindings__isnull=True).delete()


def field_payload(version, required=False):
    return {'definition_id': version.definition_id, 'key': str(version.field_key), 'label': version.label,
        'type': version.field_type, 'type_label': version.get_field_type_display(), 'required': required,
        'settings': version.settings,
        'synonym_target_ids': list(version.synonyms.values_list('target_id', flat=True))}


def application_catalog():
    catalog = []
    for interface in Interface.objects.filter(kind=Interface.ACCOUNT, status=Interface.ACTIVE,
        current_version__isnull=False).select_related('creator', 'current_version'):
        try:
            version = resolve_interface_versions([interface.pk])[0]
        except ValidationError:
            continue
        catalog.append({'id': interface.pk, 'detail_url': reverse('interfaces:definition-detail', args=[interface.pk]),
            'name': version.name, 'creator': interface.creator.username, 'version': version.version_number,
            'kind': 'AccountIF', 'description': version.description, 'updated_at': interface.updated_at,
            'implementations': [{'id': interface.pk, 'name': version.name, 'creator': interface.creator.username,
                'version': version.version_number, 'fields': [field_payload(field.field_version, field.required) for field in version.fields.all()]}]})
    return {'fields': thread_field_catalog(), 'interfaces': catalog}


def display_value(value):
    if value is None:
        return '未入力'
    if isinstance(value, bool):
        return 'はい' if value else 'いいえ'
    if isinstance(value, list):
        return ' / '.join(str(item) for item in value)
    return str(value)


def application_payload(account):
    direct, implementations, _ = applied_fields(account)
    bindings = list(account.field_bindings.select_related('value', 'definition__creator').order_by('created_at', 'pk'))
    references = {}
    def add_reference(definition_id, version, required, applied_at):
        references.setdefault(definition_id, []).append((applied_at, version, required))
    for item in direct:
        add_reference(item.definition_id, item.version, True, (item.created_at, item.pk, 0))
    interface_definitions = set()
    for item in implementations:
        for value in item.values.all():
            interface_definitions.add(value.field.definition_id)
            add_reference(value.field.definition_id, value.field.field_version, value.field.required, (item.created_at, item.pk, 1))
    shared_references = {}
    for item in direct:
        shared_references.setdefault(item.binding.value_id, []).append({'kind': 'field', 'id': item.pk,
            'definition_id': item.definition_id, 'name': item.version.name, 'creator': item.definition.creator.username})
    for item in implementations:
        for value_id in {value.binding.value_id for value in item.values.all()}:
            shared_references.setdefault(value_id, []).append({'kind': 'interface', 'id': item.pk,
                'name': item.version.name, 'creator': item.interface.creator.username})
    direct_by_definition = {item.definition_id: item.pk for item in direct}
    fields = []
    for binding in bindings:
        if binding.definition_id not in references:
            continue
        refs = sorted(references[binding.definition_id], key=lambda item: item[0])
        version = refs[0][1]
        fields.append({'id': binding.pk, 'value_id': binding.value_id, 'direct_id': direct_by_definition.get(binding.definition_id),
            'definition_id': binding.definition_id, 'name': version.name,
            'creator': binding.definition.creator.username, 'version': version.version_number,
            'field': field_payload(version, any(ref[2] for ref in refs)),
            'value': binding.value.value, 'display_value': display_value(binding.value.value), 'raw_values': raw_values(binding.value.value),
            'updated_at': binding.value.updated_at, 'shared_with': shared_references.get(binding.value_id, [])})
    # Sort by actual Account value changes; reference additions do not touch values.
    fields.sort(key=lambda item: item['updated_at'], reverse=True)
    interface_items = []
    for item in implementations:
        values = sorted(item.values.all(), key=lambda value: (value.field.position, value.pk))
        interface_items.append({'id': item.pk, 'definition_id': item.interface_id, 'name': item.version.name,
            'creator': item.interface.creator.username, 'version': item.version.version_number,
            'updated_at': max((value.binding.value.updated_at for value in values), default=item.created_at),
            'values': [{'binding_id': value.binding.pk, 'value_id': value.binding.value_id,
                'field': field_payload(value.field.field_version, value.field.required),
                'shared_with': shared_references.get(value.binding.value_id, []),
                'value': value.binding.value.value, 'display_value': display_value(value.binding.value.value),
                'raw_values': raw_values(value.binding.value.value)} for value in values]})
    interface_items.sort(key=lambda item: item['updated_at'], reverse=True)
    return {'fields': fields, 'direct_fields': [{'id': item.pk, 'definition_id': item.definition_id} for item in direct],
        'interfaces': interface_items}
