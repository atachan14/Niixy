"""Compatibility and recovery boundaries shared with future Layout/conditions.

Availability belongs to the definition; application state belongs to the Account.
Reading a profile never mutates either one.
"""
from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import AccountInterfaceImplementation, AccountInterfaceValue, FieldDefinition, Interface
from .services import _connected_field_components, normalize_field_value


@dataclass(frozen=True)
class InterfaceAvailability:
    compatible: bool
    usable: bool
    reasons: tuple[str, ...]


def interface_availability(interface):
    version = interface.current_version
    reasons = []
    if version is None:
        reasons.append('公開版がありません。')
    else:
        for field in version.fields.select_related('definition').all():
            if field.definition.status != FieldDefinition.ACTIVE or field.definition.current_version_id != field.field_version_id:
                reasons.append(f'{field.definition.name} の最新版への対応が必要です。')
    compatible = not reasons
    if interface.status != Interface.ACTIVE:
        reasons.append('このInterfaceは取り下げられています。')
    return InterfaceAvailability(compatible, compatible and interface.status == Interface.ACTIVE, tuple(reasons))


def application_state(implementation):
    if not interface_availability(implementation.interface).compatible:
        return AccountInterfaceImplementation.FROZEN
    if implementation.state == implementation.ACTIVE:
        if any(field.definition.current_version_id != field.field_version_id
               for field in implementation.version.fields.select_related('definition').all()):
            return implementation.PENDING
        values = list(implementation.values.select_related('field', 'binding'))
        fallback = {}
        if any(value.binding.version_id is None for value in values):
            from .account_applications import account_bindings
            fallback = {binding.pk: binding.version_id for binding in account_bindings(implementation.account)}
        if any((value.binding.version_id or fallback.get(value.binding_id)) != value.field.field_version_id
               for value in values):
            return implementation.PENDING
    return implementation.state


def active_account_interfaces(account):
    """Use this boundary for features/implemented conditions; display is separate."""
    return [item for item in account.interface_implementations.select_related('interface__current_version', 'version')
            if application_state(item) == AccountInterfaceImplementation.ACTIVE]


def _raw(value):
    if value is None:
        return []
    if isinstance(value, bool):
        return ['true' if value else 'false']
    return [str(item) for item in value] if isinstance(value, list) else [str(value)]


def recovery_fields(implementation, bindings):
    availability = interface_availability(implementation.interface)
    if not availability.usable:
        return None
    fields = list(implementation.interface.current_version.fields.select_related('field_version').all())
    by_definition = {item.definition_id: item for item in bindings}
    for field in fields:
        binding = by_definition.get(field.definition_id)
        if binding is None or binding.version_id != field.field_version_id:
            return None
        try:
            normalized = normalize_field_value(field, _raw(binding.value.value))
        except ValidationError:
            return None
        if normalized != binding.value.value:
            return None
    # Reconnecting independent values needs a preview, even when equal.
    versions = [item.version for item in bindings]
    components = _connected_field_components(versions)
    for field in fields:
        component = components[field.definition_id]
        if len({item.value_id for item in bindings if components[item.definition_id] == component}) > 1:
            return None
    return fields


@transaction.atomic
def refresh_account_interfaces(account):
    account = get_user_model().objects.select_for_update().get(pk=account.pk)
    from .account_applications import account_bindings
    bindings = account_bindings(account)
    by_definition = {item.definition_id: item for item in bindings}
    for item in account.interface_implementations.select_related('interface__current_version', 'version'):
        if not interface_availability(item.interface).compatible:
            state = AccountInterfaceImplementation.FROZEN
        elif application_state(item) == AccountInterfaceImplementation.ACTIVE:
            continue  # Ordinary publication keeps the already displayed version.
        else:
            fields = recovery_fields(item, bindings)
            state = AccountInterfaceImplementation.PENDING if fields is None else AccountInterfaceImplementation.ACTIVE
            if fields is not None:
                item.values.all().delete()
                AccountInterfaceValue.objects.bulk_create([
                    AccountInterfaceValue(implementation=item, field=field, binding=by_definition[field.definition_id])
                    for field in fields
                ])
                item.version = item.interface.current_version
        item.state = state
        item.save(update_fields=['state', 'version'])


def refresh_interface_accounts(interface_ids):
    ids = AccountInterfaceImplementation.objects.filter(interface_id__in=interface_ids).values_list('account_id', flat=True).distinct()
    for account in get_user_model().objects.filter(pk__in=ids).order_by('pk'):
        refresh_account_interfaces(account)
