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

def snapshot_policy_condition(condition, actor):
    """Validate a supported Account condition and construct its trusted label."""
    from django.contrib.auth import get_user_model
    from rooms.models import Room

    if not isinstance(condition, dict) or not isinstance(condition.get('definition'), dict):
        raise ValueError('Account条件が正しくありません。')
    kind = condition.get('kind')
    definition = condition['definition']
    if kind == 'default':
        code = definition.get('code')
        if code == 'self':
            if not actor.is_authenticated:
                raise ValueError('自分のNiixyIDはLogin中のみ利用できます。')
            return 'account', {'account_id': actor.pk}, f'@{actor.username}'
        if code not in {'guest', 'account'}:
            raise ValueError('このDefault条件はまだPolicyで利用できません。')
        return kind, {'code': code}, 'Guest' if code == 'guest' else 'NiixyAccount'
    if kind == 'account':
        try:
            account = get_user_model().objects.select_related('niixy_profile').get(pk=definition.get('account_id'))
        except (get_user_model().DoesNotExist, TypeError, ValueError) as error:
            raise ValueError('Accountが見つかりません。') from error
        return kind, {'account_id': account.pk}, account.niixy_profile.display_label
    if kind == 'room':
        try:
            room = Room.objects.get(pk=definition.get('room_id'))
        except (Room.DoesNotExist, TypeError, ValueError) as error:
            raise ValueError('Roomが見つかりません。') from error
        if definition.get('relation', 'member') != 'member':
            raise ValueError('Room条件が正しくありません。')
        return kind, {'room_id': room.pk, 'relation': 'member'}, f'{room.name}に参加'
    raise ValueError('このAccount条件はまだPolicyで利用できません。')
