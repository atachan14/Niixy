from django.core.exceptions import ValidationError

from interfaces.services import prepare_thread_fields


def prepare_thread_modules(data):
    try:
        direct_field_ids = [int(value) for value in data.getlist('direct_field_ids')]
        interface_ids = [int(value) for value in data.getlist('interface_ids')]
    except ValueError as error:
        raise ValidationError({'fields': ['FieldまたはInterfaceの指定が正しくありません。']}) from error

    direct_value_lists = {}
    interface_value_lists = {}
    for key in data:
        if key.startswith('direct_field_value_'):
            direct_value_lists[key.removeprefix('direct_field_value_')] = data.getlist(key)
            continue
        if not key.startswith('interface_value_'):
            continue
        try:
            _, _, interface_id, field_key = key.split('_', 3)
            interface_value_lists[(int(interface_id), field_key)] = data.getlist(key)
        except (ValueError, TypeError) as error:
            raise ValidationError({'interfaces': ['Interfaceの入力値が正しくありません。']}) from error

    return prepare_thread_fields(
        direct_field_ids,
        direct_value_lists,
        interface_ids,
        interface_value_lists,
    )
