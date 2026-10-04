from dataclasses import dataclass
from itertools import groupby


@dataclass(frozen=True)
class PolicyEvaluation:
    allowed: bool
    has_allow_conditions: bool
    unmet_allow_labels: tuple[str, ...]
    matched_deny_labels: tuple[str, ...]


def condition_matches(condition, user):
    definition = condition.definition
    if condition.kind == 'default':
        code = definition.get('code')
        if code == 'guest':
            return not user.is_authenticated
        if code == 'account':
            return user.is_authenticated
        if code == 'self':
            return user.is_authenticated and user.pk == definition.get('account_id')
        return False

    if condition.kind == 'account':
        return user.is_authenticated and user.pk == definition.get('account_id')

    if condition.kind == 'room':
        if not user.is_authenticated or definition.get('relation') != 'member':
            return False
        return user.room_memberships.filter(room_id=definition.get('room_id')).exists()

    # AccountIF and Field conditions will use this same boundary once their
    # Account-side implementations exist.
    return False


def condition_groups(conditions):
    ordered = sorted(conditions, key=lambda item: (str(item.group_key), item.position, item.pk or 0))
    return [list(group) for _, group in groupby(ordered, key=lambda item: item.group_key)]


def _group_label(group):
    return ' AND '.join(condition.label for condition in group)


def evaluate_policy(conditions, user):
    conditions = list(conditions)
    allow_groups = condition_groups(condition for condition in conditions if condition.decision == 'allow')
    deny_groups = condition_groups(condition for condition in conditions if condition.decision == 'deny')

    matched_allow = [group for group in allow_groups if all(condition_matches(item, user) for item in group)]
    matched_deny = [group for group in deny_groups if all(condition_matches(item, user) for item in group)]
    unmet_allow = [] if matched_allow else allow_groups

    return PolicyEvaluation(
        allowed=bool(matched_allow) and not matched_deny,
        has_allow_conditions=bool(allow_groups),
        unmet_allow_labels=tuple(_group_label(group) for group in unmet_allow),
        matched_deny_labels=tuple(_group_label(group) for group in matched_deny),
    )
