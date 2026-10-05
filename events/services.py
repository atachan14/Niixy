from django.core.exceptions import ValidationError
from django.db.models import Prefetch

from accounts.mutes import prepare_muted_posts
from interfaces.services import prepare_thread_fields

from .models import Thread, ThreadAccessRule, ThreadPlacement, ThreadPost


def thread_queryset():
    return (
        Thread.objects.select_related('creator__niixy_profile')
        .prefetch_related(
            'access_rules',
            'policy_conditions',
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


def prepare_thread_for_view(thread, viewer, muted_ids=None):
    view_policy = thread.evaluate_policy(viewer, ThreadAccessRule.VIEW)
    write_policy = thread.evaluate_policy(viewer, ThreadAccessRule.WRITE)
    thread.can_view = thread.allows(viewer, ThreadAccessRule.VIEW)
    thread.can_write = thread.can_view and write_policy.allowed
    thread.view_policy = view_policy
    thread.write_policy = write_policy
    thread.unmet_write_requirements = write_policy.unmet_allow_labels
    thread.matched_write_denials = write_policy.matched_deny_labels
    if thread.can_view:
        posts = thread.posts.all()
        prepare_muted_posts(posts, viewer, muted_ids)
        if not hasattr(thread, "_prefetched_objects_cache"):
            thread._prefetched_objects_cache = {}
        thread._prefetched_objects_cache["posts"] = posts
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
