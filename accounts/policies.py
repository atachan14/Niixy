from dataclasses import dataclass
from itertools import groupby


@dataclass(frozen=True)
class PolicyEvaluation:
    allowed: bool
    has_allow_conditions: bool
    unmet_allow_labels: tuple[str, ...]
    matched_deny_labels: tuple[str, ...]


def condition_matches(condition, user):
    return account_condition_matches(user, condition, actor=user)


def _condition_value(condition, name, default=None):
    if isinstance(condition, dict):
        return condition.get(name, default)
    return getattr(condition, name, default)


def account_condition_matches(account, condition, *, actor=None):
    definition = _condition_value(condition, 'definition', {}) or {}
    kind = _condition_value(condition, 'kind')
    is_authenticated = bool(account is not None and getattr(account, 'is_authenticated', True))

    if kind == 'default':
        code = definition.get('code')
        if code == 'guest':
            return not is_authenticated
        if code == 'account':
            return is_authenticated
        if code == 'self':
            account_id = definition.get('account_id')
            if account_id is not None:
                return is_authenticated and account.pk == account_id
            return bool(
                actor is not None
                and getattr(actor, 'is_authenticated', False)
                and is_authenticated
                and account.pk == actor.pk
            )
        return False

    if kind == 'account':
        return is_authenticated and account.pk == definition.get('account_id')

    if kind == 'room':
        if not is_authenticated or definition.get('relation') != 'member':
            return False
        return account.room_memberships.filter(room_id=definition.get('room_id')).exists()

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
