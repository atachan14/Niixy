import hashlib
import json

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from interfaces.models import FieldDefinition

from .models import AccountCondition


DEFAULT_ACCOUNT_CONDITIONS = [
    ('self', '自分のNiixyID'),
    ('guest', 'Guest'),
    ('account', 'NiixyAccount'),
    ('follow', 'Follow'),
    ('follower', 'Follower'),
    ('mute', 'Mute'),
    ('muter', 'Muter'),
    ('love', 'Love'),
    ('lover', 'Lover'),
    ('hate', 'Hate'),
    ('hater', 'Hater'),
]
DEFAULT_LABELS = dict(DEFAULT_ACCOUNT_CONDITIONS)


def default_condition_label(user, code):
    if code == 'self':
        return f'@{user.username}' if user.is_authenticated else 'Guest'
    return DEFAULT_LABELS[code]


def condition_fingerprint(kind, definition):
    canonical = json.dumps({'kind': kind, 'definition': definition}, ensure_ascii=True, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode()).hexdigest()


def condition_payload(condition):
    return {
        'id': condition.pk,
        'kind': condition.kind,
        'definition': condition.definition,
        'label': condition.label,
        'active': condition.active,
    }


def seed_default_conditions(user):
    if not user.is_authenticated:
        return
    for code, _ in reversed(DEFAULT_ACCOUNT_CONDITIONS):
        definition = {'code': code}
        label = default_condition_label(user, code)
        condition, created = AccountCondition.objects.get_or_create(
            owner=user,
            fingerprint=condition_fingerprint(AccountCondition.DEFAULT, definition),
            defaults={
                'kind': AccountCondition.DEFAULT,
                'definition': definition,
                'label': label,
            },
        )
        if not created and condition.label != label:
            condition.label = label
            condition.save(update_fields=['label'])


def account_condition_catalog(user, *, include_inactive=False):
    if not user.is_authenticated:
        return [{
            'id': 'default:guest',
            'kind': AccountCondition.DEFAULT,
            'definition': {'code': 'guest'},
            'label': default_condition_label(user, 'guest'),
            'active': True,
        }]
    seed_default_conditions(user)
    conditions = user.account_conditions.all()
    if not include_inactive:
        conditions = conditions.filter(active=True)
    return [condition_payload(condition) for condition in conditions]


@transaction.atomic
def save_account_condition(user, *, kind, definition, condition_id=None):
    if kind == AccountCondition.DEFAULT:
        code = definition.get('code')
        if code not in DEFAULT_LABELS:
            raise ValueError('Account条件が正しくありません。')
        label = default_condition_label(user, code)
        definition = {'code': code}
    elif kind == AccountCondition.ACCOUNT:
        try:
            account = get_user_model().objects.select_related('niixy_profile').get(pk=definition.get('account_id'))
        except (get_user_model().DoesNotExist, TypeError, ValueError) as error:
            raise ValueError('Accountが見つかりません。') from error
        definition = {'account_id': account.pk}
        label = account.niixy_profile.display_label
    elif kind == AccountCondition.FIELD:
        try:
            field = FieldDefinition.objects.select_related(
                'creator', 'current_version'
            ).get(
                pk=definition.get('field_id'),
                status=FieldDefinition.ACTIVE,
                current_version__isnull=False,
            )
        except (FieldDefinition.DoesNotExist, TypeError, ValueError) as error:
            raise ValueError('Fieldが見つかりません。') from error
        operator = str(definition.get('operator', '')).strip()
        value = str(definition.get('value', '')).strip()
        allowed_operators = {'', 'contains', 'not_contains', 'equals', 'gte', 'lte', 'true', 'false'}
        if operator not in allowed_operators:
            raise ValueError('Field条件が正しくありません。')
        if not value:
            operator = ''
        definition = {
            'field_id': field.pk,
            'field_version_id': field.current_version_id,
            'operator': operator,
            'value': value,
        }
        identity = f'{field.name}@{field.creator.username}'
        label = f'{identity}を実装' if not value else f'{identity}: {value}'
    else:
        raise ValueError('このAccount条件はまだ利用できません。')

    fingerprint = condition_fingerprint(kind, definition)
    condition = None
    previous = None
    if condition_id is not None:
        try:
            previous = AccountCondition.objects.select_for_update().get(pk=condition_id, owner=user)
        except (AccountCondition.DoesNotExist, TypeError, ValueError) as error:
            raise ValueError('編集するAccount条件が見つかりません。') from error
        condition = AccountCondition.objects.select_for_update().filter(
            owner=user,
            fingerprint=fingerprint,
        ).exclude(pk=previous.pk).first()
        if condition is None:
            condition = previous
        else:
            previous.active = False
            previous.save(update_fields=['active'])
    if condition is None:
        condition, _ = AccountCondition.objects.get_or_create(
            owner=user,
            fingerprint=fingerprint,
            defaults={'kind': kind, 'definition': definition, 'label': label},
        )
    condition.kind = kind
    condition.definition = definition
    condition.fingerprint = fingerprint
    condition.label = label
    condition.active = True
    condition.last_used_at = timezone.now()
    condition.save(update_fields=['kind', 'definition', 'fingerprint', 'label', 'active', 'last_used_at'])
    return condition
