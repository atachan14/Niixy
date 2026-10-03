from django.core.exceptions import ValidationError
from django.db.models import Prefetch

from interfaces.services import prepare_thread_fields

from .models import Thread, ThreadAccessRule, ThreadPlacement, ThreadPost


def thread_queryset():
    return (
        Thread.objects.select_related('creator__niixy_profile')
        .prefetch_related(
            'access_rules',
            Prefetch(
                'placements',
                queryset=ThreadPlacement.objects.select_related(
                    'board__placement__collection__room',
                ),
            ),
            Prefetch('posts', queryset=ThreadPost.objects.select_related('creator__niixy_profile')),
            'interface_implementations__version__interface__creator',
            'interface_implementations__values__field',
            'direct_fields__version__definition__creator',
            'direct_fields__binding__value',
            'field_bindings__value',
        )
    )


def prepare_thread_for_view(thread, viewer):
    from rooms.services import room_for_thread

    thread.can_view = thread.allows(viewer, ThreadAccessRule.VIEW)
    room = room_for_thread(thread)
    thread.can_write = thread.allows(viewer, ThreadAccessRule.WRITE) and (
        room is None or room.has_member(viewer)
    )
    return thread


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
