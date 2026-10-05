"""Account applications: historical display, latest-version edits, shared values."""
import hashlib
import json
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Max
from django.urls import reverse

from .models import (AccountDirectField, AccountFieldBinding, AccountFieldValue,
    AccountInterfaceImplementation, AccountInterfaceValue, FieldDefinition, Interface)
from .services import (_connected_field_components, normalize_field_value,
    resolve_direct_field_versions, resolve_interface_versions, thread_field_catalog)
from .versioning import application_state, interface_availability, refresh_account_interfaces


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
    implementations = list(account.interface_implementations.select_related('version', 'interface__creator',
        'interface__current_version').prefetch_related('values__field__field_version__synonyms',
        'values__binding__value', 'values__binding__version__synonyms', 'version__fields__field_version__synonyms'))
    fields = [_field(item.version, True) for item in direct]
    fields += [field for item in implementations if application_state(item) == item.ACTIVE
               for field in item.version.fields.all()]
    return direct, implementations, fields


def account_bindings(account):
    """Resolve the nullable rollout column without writing during public reads.

    New code always writes a version. Old code may insert NULL while deployments
    overlap; its first remaining application is the historical representative.
    """
    bindings = list(account.field_bindings.select_related('value', 'version', 'definition__creator',
        'definition__current_version').prefetch_related('version__synonyms').order_by('created_at', 'pk'))
    for binding in bindings:
        if binding.version_id is not None:
            continue
        refs = [((item.created_at, item.pk, 0), item.version)
                for item in account.direct_fields.filter(binding=binding).select_related('version')]
        refs += [((item.implementation.created_at, item.implementation_id, 1), item.field.field_version)
                 for item in binding.interface_values.select_related('implementation', 'field__field_version')]
        version = min(refs, key=lambda ref: ref[0])[1] if refs else binding.definition.current_version
        if version is None:
            raise ValidationError('適用Fieldの公開版が見つかりません。')
        binding.version = version
    return bindings


def _next_position(manager):
    return (manager.aggregate(last=Max('position'))['last'] or 0) + 1


def _validate_component(fields, value):
    if len({field.field_type for field in fields}) != 1:
        raise ValidationError('共有Fieldの型が一致しません。')
    for field in fields:
        if normalize_field_value(field, raw_values(value), required=field.required) != value:
            raise ValidationError('共有Fieldの制約が一致しません。')


def _token_matches(token, expected):
    try:
        return signing.loads(token, salt='account-field-merge', max_age=600) == signing.loads(expected, salt='account-field-merge')
    except (signing.BadSignature, TypeError):
        return False


def _preview_token(account, payload, bindings, implementations, definitions, changes, target_version):
    state = {'account': account.pk, 'payload': payload,
        'bindings': [(b.pk, b.definition_id, b.version_id, b.value_id, b.value.value) for b in bindings],
        'interfaces': [(i.pk, i.version_id, i.state, i.interface.current_version_id, i.interface.status) for i in implementations],
        'definitions': [(d.pk, d.current_version_id, d.status) for d in definitions], 'changes': changes,
        'target_version': (type(target_version).__name__, target_version.pk) if target_version else None}
    digest = hashlib.sha256(json.dumps(state, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return signing.dumps({'account': account.pk, 'digest': digest}, salt='account-field-merge')


def _id(value):
    try:
        return int(value)
    except (ValueError, TypeError) as error:
        raise ValidationError('項目が正しくありません。') from error


def _supplied_values(payload):
    supplied = payload.get('values', {})
    if not isinstance(supplied, dict) or any(not isinstance(v, list) or any(not isinstance(s, str) for s in v) for v in supplied.values()):
        raise ValidationError('値が正しくありません。')
    return supplied


@transaction.atomic
def change_application(account, payload, confirmation=None):
    if not isinstance(payload, dict):
        raise ValidationError('操作が正しくありません。')
    operation = payload.get('operation')
    # Publishers lock definitions before applications; use the same lock order.
    definition_ids = set(account.field_bindings.values_list('definition_id', flat=True))
    interface_ids = set(account.interface_implementations.values_list('interface_id', flat=True))
    if operation == 'add_field':
        definition_ids.add(_id(payload.get('id')))
    if operation == 'add_interface':
        interface_ids.add(_id(payload.get('id')))
    definition_ids.update(FieldDefinition.objects.filter(interface_bindings__version__interface_id__in=interface_ids,
        interface_bindings__version__interface__current_version_id=F('interface_bindings__version_id'))
        .values_list('pk', flat=True))
    definitions = list(FieldDefinition.objects.select_for_update().filter(pk__in=definition_ids).order_by('pk')
        .select_related('current_version').prefetch_related('current_version__synonyms'))
    list(Interface.objects.select_for_update().filter(pk__in=interface_ids).order_by('pk'))
    account = get_user_model().objects.select_for_update().get(pk=account.pk)
    direct, implementations, _ = applied_fields(account)
    bindings = account_bindings(account)
    by_definition = {b.definition_id: b for b in bindings}
    if operation in {'remove_field', 'remove_interface'}:
        manager = account.direct_fields if operation == 'remove_field' else account.interface_implementations
        try:
            item = manager.get(pk=_id(payload.get('id')))
        except manager.model.DoesNotExist as error:
            raise ValidationError('適用済み項目が見つかりません。') from error
        affected = [item.binding_id] if operation == 'remove_field' else list(item.values.values_list('binding_id', flat=True))
        from .account_layouts import removal_guard
        removal_guard(account, operation, item)
        item.delete()
        account.field_bindings.filter(pk__in=affected, direct_implementations__isnull=True, interface_values__isnull=True).delete()
        account.field_values.filter(bindings__isnull=True).delete()
        refresh_account_interfaces(account)
        return
    if operation not in {'add_field', 'add_interface', 'edit_value', 'edit_values', 'update_interface'}:
        raise ValidationError('操作が正しくありません。')

    versions = {b.definition_id: b.version for b in bindings}
    required = {definition_id: False for definition_id in versions}
    for item in direct:
        required[item.definition_id] = True
    for item in implementations:
        if application_state(item) == item.ACTIVE:
            for field in item.version.fields.all():
                required[field.definition_id] = required.get(field.definition_id, False) or field.required
    touched = set()
    raw_updates = {}
    new_fields = []
    target = None
    target_version = None
    changes = []
    if operation in {'add_field', 'add_interface', 'update_interface'}:
        supplied = _supplied_values(payload)
        selected_id = _id(payload.get('id'))
        if operation == 'add_field':
            if any(item.definition_id == selected_id for item in direct):
                raise ValidationError('同じFieldを重複して追加できません。')
            target_version = resolve_direct_field_versions([selected_id])[0]
            new_fields = [_field(target_version, True)]
        else:
            if operation == 'update_interface':
                target = next((item for item in implementations if item.pk == selected_id), None)
                if target is None:
                    raise ValidationError('適用済みAccountIFが見つかりません。')
                if application_state(target) == target.FROZEN:
                    raise ValidationError('凍結中はAccountIF経由で編集できません。Field一覧から更新できます。')
                selected_id = target.interface_id
                # Replace this application's requirements, retaining other active constraints.
                required = {key: any(item.definition_id == key for item in direct) for key in versions}
                for item in implementations:
                    if item.pk != target.pk and application_state(item) == item.ACTIVE:
                        for field in item.version.fields.all():
                            required[field.definition_id] = required.get(field.definition_id, False) or field.required
            elif any(item.interface_id == selected_id for item in implementations):
                raise ValidationError('同じAccountIFを重複して追加できません。')
            target_version = resolve_interface_versions([selected_id])[0]
            if target_version.interface.kind != Interface.ACCOUNT:
                raise ValidationError('AccountIFだけを適用できます。')
            new_fields = list(target_version.fields.all())
            if target is not None and target.version_id != target_version.pk:
                changes.append({'kind': 'interface_version', 'field': target_version.name,
                    'before': target.version.version_number, 'after': target_version.version_number,
                    'before_fields': [field_payload(f.field_version, f.required) for f in target.version.fields.all()],
                    'after_fields': [field_payload(f.field_version, f.required) for f in new_fields],
                    'before_definition': {'name': target.version.name, 'description': target.version.description},
                    'after_definition': {'name': target_version.name, 'description': target_version.description}})
        for field in new_fields:
            version = field.field_version
            versions[field.definition_id] = version
            required[field.definition_id] = required.get(field.definition_id, False) or field.required
            touched.add(field.definition_id)
            if str(field.field_key) in supplied:
                raw_updates[field.definition_id] = supplied[str(field.field_key)]
            if target is not None and field.definition_id not in by_definition:
                changes.append({'kind': 'field_addition', 'field': field.label, 'before': None, 'after': version.version_number})
    else:
        # interface-origin requests must use the explicit latest-version IF path.
        if payload.get('interface_id') is not None:
            raise ValidationError('AccountIF編集は最新版の更新操作から行ってください。')
        updates = payload.get('updates') if operation == 'edit_values' else [{'id': payload.get('id'), 'values': payload.get('values')}]
        if not isinstance(updates, list) or not updates:
            raise ValidationError('値が正しくありません。')
        seen_shared = {}
        for update in updates:
            if not isinstance(update, dict):
                raise ValidationError('値が正しくありません。')
            binding = next((b for b in bindings if b.pk == _id(update.get('id'))), None)
            if binding is None:
                raise ValidationError('値が見つかりません。')
            raw = update.get('values')
            if not isinstance(raw, list) or any(not isinstance(s, str) for s in raw):
                raise ValidationError('値が正しくありません。')
            if binding.value_id in seen_shared and seen_shared[binding.value_id] != raw:
                raise ValidationError('共有値に異なる値を指定できません。')
            seen_shared[binding.value_id] = raw
            raw_updates[binding.definition_id] = raw
            touched.add(binding.definition_id)

    # An edited/connected shared Value advances every affected definition to latest.
    # Existing shared edges are retained; removal of a synonym never silently splits values.
    latest_by_id = {d.pk: d.current_version for d in definitions if d.status == FieldDefinition.ACTIVE and d.current_version_id}
    while True:
        before = set(touched)
        shared_ids = {b.value_id for b in bindings if b.definition_id in touched}
        touched.update(b.definition_id for b in bindings if b.value_id in shared_ids)
        for definition_id in touched:
            if definition_id not in latest_by_id:
                raise ValidationError('更新対象Fieldの最新版が利用できません。')
            versions[definition_id] = latest_by_id[definition_id]
        components = _connected_field_components(list(versions.values()))
        component_ids = {components[key] for key in touched}
        touched.update(key for key, component in components.items() if component in component_ids)
        if touched == before:
            break
    for key in sorted(touched):
        binding = by_definition.get(key)
        version = versions[key]
        if binding is not None and binding.version_id != version.pk:
            changes.append({'kind': 'field_version', 'field': version.name,
                'before': binding.version.version_number, 'after': version.version_number,
                'value': binding.value.value,
                'before_definition': field_payload(binding.version), 'after_definition': field_payload(version)})

    # Union current synonyms and already-shared bindings.
    groups = {key: {key} for key in versions}
    def join(keys):
        merged = set().union(*(groups[key] for key in keys))
        for key in merged:
            groups[key] = merged
    for component in set(components.values()):
        join([key for key in versions if components[key] == component])
    for value_id in {b.value_id for b in bindings}:
        join([b.definition_id for b in bindings if b.value_id == value_id])
    plans = []
    for keys in {tuple(sorted(groups[key])) for key in touched}:
        existing = [b for b in bindings if b.definition_id in keys]
        fields = [_field(versions[key], required.get(key, False)) for key in keys]
        normalized_updates = {key: normalize_field_value(_field(versions[key], False), raw, required=False)
                              for key, raw in raw_updates.items() if key in keys}
        shared = existing[0].value if existing else None
        # Explicit Field/IF edits replace the value, except when merging independent values.
        merging = len({b.value_id for b in existing}) > 1
        editing = operation in {'edit_value', 'edit_values', 'update_interface'}
        if existing:
            winner_key = existing[0].definition_id
            if editing and not merging and normalized_updates:
                candidate_values = list(normalized_updates.values())
                if any(value != candidate_values[0] for value in candidate_values):
                    raise ValidationError('共有値に異なる値を指定できません。')
                value = candidate_values[0]
            elif merging and editing:
                value = normalized_updates.get(winner_key, shared.value)
            else:
                value = shared.value
                # Applying latest onto a frozen-only old binding can explicitly repair invalid input.
                try:
                    _validate_component(fields, value)
                except ValidationError:
                    if winner_key not in normalized_updates:
                        raise
                    value = normalized_updates[winner_key]
        else:
            value = next((v for v in normalized_updates.values() if v is not None), None)
        _validate_component(fields, value)
        for binding in existing:
            if binding.value.value != value and (merging or not editing or changes):
                changes.append({'kind': 'value', 'field': versions[binding.definition_id].name,
                                'before': binding.value.value, 'after': value})
        for key, supplied_value in normalized_updates.items():
            if supplied_value is not None and supplied_value != value:
                changes.append({'kind': 'value', 'field': versions[key].name, 'before': supplied_value, 'after': value})
        if merging and not any(change['kind'] == 'value' for change in changes):
            changes.append({'kind': 'value_merge', 'field': fields[0].label, 'before': len({b.value_id for b in existing}), 'after': 1})
        plans.append((keys, existing, shared, value))

    if changes:
        for keys, existing, shared, value in plans:
            for key in keys:
                if key not in by_definition:
                    changes.append({'kind': 'value', 'field': versions[key].name, 'before': None, 'after': value})
    if confirmation and not changes:
        # Another confirmed edit may have removed the original version diff.
        # A stale confirmation must not silently overwrite its newer value.
        changes.append({'kind': 'revalidation', 'field': '更新内容', 'before': '以前の確認',
                        'after': '現在の版・値・参照を再確認してください。', 'before_fields': [],
                        'after_fields': [field_payload(versions[key], required.get(key, False)) for key in sorted(touched)]})
        for keys, existing, shared, value in plans:
            for binding in existing:
                if binding.value.value != value:
                    changes.append({'kind': 'value', 'field': versions[binding.definition_id].name,
                                    'before': binding.value.value, 'after': value})
    if changes:
        if operation in {'add_field', 'add_interface'}:
            changes.append({'kind': 'application', 'field': target_version.name, 'before': '未適用',
                            'after': target_version.version_number})
        expected = _preview_token(account, payload, bindings, implementations, definitions, changes, target_version)
        if not _token_matches(confirmation, expected):
            raise MergeConfirmationRequired(changes, expected)
    for keys, existing, shared, value in plans:
        if shared is None:
            shared = AccountFieldValue.objects.create(account=account, value=value)
        elif shared.value != value:
            shared.value = value
            shared.save(update_fields=['value', 'updated_at'])
        for key in keys:
            binding = by_definition.get(key)
            if binding is None:
                binding = AccountFieldBinding.objects.create(account=account, definition_id=key, version=versions[key], value=shared)
                by_definition[key] = binding
            else:
                binding.version = versions[key]
                binding.value = shared
                binding.save(update_fields=['version', 'value'])
            account.direct_fields.filter(definition_id=key).update(version=versions[key])
    if operation == 'add_field':
        AccountDirectField.objects.create(account=account, definition=target_version.definition, version=target_version,
            binding=by_definition[target_version.definition_id], position=_next_position(account.direct_fields))
    if operation in {'add_interface', 'update_interface'}:
        if target is None:
            target = AccountInterfaceImplementation.objects.create(account=account, interface=target_version.interface,
                version=target_version, position=_next_position(account.interface_implementations))
        else:
            target.values.all().delete()
            target.version = target_version
            target.state = target.ACTIVE
            target.save(update_fields=['version', 'state'])
        AccountInterfaceValue.objects.bulk_create([AccountInterfaceValue(implementation=target, field=field,
            binding=by_definition[field.definition_id]) for field in new_fields])
    account.field_values.filter(bindings__isnull=True).delete()
    refresh_account_interfaces(account)


def field_payload(version, required=False):
    return {'definition_id': version.definition_id, 'key': str(version.field_key), 'label': version.label,
        'version': version.version_number, 'version': version.version_number, 'type': version.field_type, 'type_label': version.get_field_type_display(), 'required': required,
        'settings': version.settings, 'description': version.description,
        'synonym_target_ids': list(version.synonyms.values_list('target_id', flat=True)),
        'synonym_labels': [f'{item.target.name}@{item.target.creator.username}'
                           for item in version.synonyms.select_related('target__creator')]}


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
    bindings = account_bindings(account)
    by_definition = {b.definition_id: b for b in bindings}
    direct_by_definition = {item.definition_id: item.pk for item in direct}
    required = {item.definition_id: True for item in direct}
    references = {}
    for item in direct:
        references.setdefault(item.binding.value_id, []).append({'kind': 'field', 'id': item.pk,
            'definition_id': item.definition_id, 'name': item.version.name, 'creator': item.definition.creator.username})
    for item in implementations:
        for value_id in {v.binding.value_id for v in item.values.all()}:
            references.setdefault(value_id, []).append({'kind': 'interface', 'id': item.pk,
                'name': item.version.name, 'creator': item.interface.creator.username})
        if application_state(item) == item.ACTIVE:
            for f in item.version.fields.all():
                required[f.definition_id] = required.get(f.definition_id, False) or f.required
    fields = []
    for binding in bindings:
        version = binding.version
        latest = binding.definition.current_version
        fields.append({'id': binding.pk, 'value_id': binding.value_id, 'direct_id': direct_by_definition.get(binding.definition_id),
            'definition_id': binding.definition_id, 'name': version.name, 'creator': binding.definition.creator.username,
            'version': version.version_number, 'field': field_payload(version, required.get(binding.definition_id, False)),
            'edit_field': field_payload(latest, required.get(binding.definition_id, False)) if latest else None,
            'value': binding.value.value, 'display_value': display_value(binding.value.value), 'raw_values': raw_values(binding.value.value),
            'updated_at': binding.value.updated_at, 'shared_with': references.get(binding.value_id, [])})
    fields.sort(key=lambda item: item['updated_at'], reverse=True)
    interface_items = []
    for item in implementations:
        values = sorted(item.values.all(), key=lambda value: (value.field.position, value.pk))
        state = application_state(item)
        availability = interface_availability(item.interface)
        edit_values = []
        if availability.usable:
            for field in item.interface.current_version.fields.all():
                binding = by_definition.get(field.definition_id)
                edit_values.append({'binding_id': binding.pk if binding else None, 'value_id': binding.value_id if binding else None,
                    'field': field_payload(field.field_version, field.required),
                    'raw_values': raw_values(binding.value.value) if binding else [],
                    'shared_with': references.get(binding.value_id, []) if binding else []})
        interface_items.append({'id': item.pk, 'definition_id': item.interface_id, 'name': item.version.name,
            'creator': item.interface.creator.username, 'version': item.version.version_number,
            'state': state, 'state_label': dict(item.STATE_CHOICES)[state], 'reasons': availability.reasons,
            'editable': availability.usable and state != item.FROZEN,
            'latest_version': item.interface.current_version.version_number if item.interface.current_version_id else None,
            'edit_values': edit_values,
            'updated_at': max((v.binding.value.updated_at for v in values), default=item.created_at),
            'values': [{'binding_id': v.binding.pk, 'value_id': v.binding.value_id,
                'field': field_payload(by_definition[v.field.definition_id].version, v.field.required),
                'shared_with': references.get(v.binding.value_id, []),
                'value': v.binding.value.value, 'display_value': display_value(v.binding.value.value),
                'raw_values': raw_values(v.binding.value.value)} for v in values]})
    interface_items.sort(key=lambda item: item['updated_at'], reverse=True)
    return {'fields': fields, 'direct_fields': [{'id': item.pk, 'definition_id': item.definition_id} for item in direct],
            'interfaces': interface_items}
