"""Thread policy snapshots and form serialization; no parent Template evaluation."""
import json
import uuid
from types import SimpleNamespace

from django.core.exceptions import ValidationError

from accounts.policies import condition_groups, snapshot_policy_condition


CAPABILITIES = (('view', '閲覧'), ('write', '書込'))


def prepare_thread_policy(data, actor):
    """Validate all four sets before creating any Thread or post.

    Old form field names remain an input compatibility path; they do not add
    Room/Board restrictions to new Threads.
    """
    prepared = []
    for capability, _ in CAPABILITIES:
        for decision in ('allow', 'deny'):
            field = f'policy_{capability}_{decision}_groups'
            raw = data.get(field)
            if raw is None:
                groups = [
                    [{'kind': 'default', 'definition': {'code': audience}}]
                    for audience in ('guest', 'account')
                    if decision == 'allow' and data.get(f'{capability}_{audience}') == 'true'
                ]
            else:
                try:
                    groups = json.loads(raw)
                except (TypeError, ValueError) as error:
                    raise ValidationError({'policy': ['Policy条件が正しくありません。']}) from error
            if not isinstance(groups, list) or any(not isinstance(group, list) or not group for group in groups):
                raise ValidationError({'policy': ['Policy条件が正しくありません。']})
            for group in groups:
                group_key = uuid.uuid4()
                for position, condition in enumerate(group):
                    try:
                        kind, definition, label = snapshot_policy_condition(condition, actor)
                    except ValueError as error:
                        raise ValidationError({'policy': [str(error)]}) from error
                    prepared.append({
                        'capability': capability, 'decision': decision, 'group_key': group_key,
                        'position': position, 'kind': kind, 'definition': definition, 'label': label,
                    })
    return prepared


def save_thread_policy(thread, prepared):
    from .models import ThreadPolicyCondition
    ThreadPolicyCondition.objects.bulk_create([
        ThreadPolicyCondition(thread=thread, **condition) for condition in prepared
    ])


def policy_rows(conditions):
    conditions = list(conditions)
    rows = []
    for capability, label in CAPABILITIES:
        selected = [item for item in conditions if item.capability == capability]
        labels = {
            decision: [' AND '.join(item.label for item in group)
                       for group in condition_groups(item for item in selected if item.decision == decision)]
            for decision in ('allow', 'deny')
        }
        rows.append({'capability': capability, 'label': label,
                     'allow_labels': labels['allow'], 'deny_labels': labels['deny'],
                     'audiences': labels['allow']})
    return rows


def legacy_conditions(thread):
    """Read-only compatibility for old fixtures. Never add a parent Room gate."""
    rules = getattr(thread, '_prefetched_objects_cache', {}).get('access_rules')
    if rules is None:
        rules = list(thread.access_rules.all())
    conditions = [
        SimpleNamespace(capability=rule.capability, decision='allow', group_key=rule.audience,
                        position=0, pk=rule.pk, kind='default', definition={'code': rule.audience},
                        label='Guest' if rule.audience == 'guest' else 'NiixyAccount')
        for rule in rules
    ]
    return conditions


def default_thread_policy_groups():
    """Common initial values while Template support is a later version."""
    return {
        f'{capability}_{decision}': (
            [[{'kind': 'default', 'definition': {'code': audience},
               'label': 'Guest' if audience == 'guest' else 'NiixyAccount'}]
             for audience in ('guest', 'account')] if decision == 'allow' else []
        )
        for capability, _ in CAPABILITIES for decision in ('allow', 'deny')
    }

def thread_policy_editor_rows(prefix, groups):
    return [
        {'capability': capability, 'decision': decision,
         'label': f'{label}{"可能" if decision == "allow" else "不可"}',
         'target': f'thread-policy-{prefix}-{capability}-{decision}',
         'groups_json': json.dumps(groups[f'{capability}_{decision}'], ensure_ascii=False)}
        for capability, label in CAPABILITIES for decision in ('allow', 'deny')
    ]
