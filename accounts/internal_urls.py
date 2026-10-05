"""Resolve known Niixy URLs locally. Never fetch a supplied URL over HTTP."""
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError
from django.urls import Resolver404, resolve, reverse
from django.http import Http404

from .models import AccountList
from .reviews import target_account


@dataclass(frozen=True)
class InternalTarget:
    kind: str
    instance: object
    path: str


def origin(value):
    parts = urlsplit(value)
    if parts.scheme not in {'http', 'https'} or not parts.netloc or parts.username is not None or parts.password is not None:
        raise ValueError('invalid origin')
    port = parts.port
    if not parts.hostname:
        raise ValueError('missing host')
    host = parts.hostname.lower()
    if ':' in host:
        host = '[' + host + ']'
    suffix = '' if port is None or port == {'http': 80, 'https': 443}[parts.scheme] else ':' + str(port)
    return parts.scheme.lower() + '://' + host + suffix


def resolve_internal_url(request, value):
    invalid = ValidationError('既知のNiixyコンテンツまたはListの正規URLを入力してください。')
    if not value or len(value) > 2048 or any(ord(char) < 33 for char in value) or '\\' in value:
        raise invalid
    try:
        parts = urlsplit(value)
        if '?' in value or '#' in value or unquote(parts.path) != parts.path:
            raise invalid
        if parts.scheme or parts.netloc:
            known = {origin(request.build_absolute_uri('/'))}
            known.update(origin(item) for item in getattr(settings, 'NIIXY_REFERENCE_ORIGINS', []))
            if origin(value) not in known:
                raise invalid
        elif not value.startswith('/') or value.startswith('//'):
            raise invalid
        match = resolve(parts.path)
        if match.view_name == 'accounts:detail':
            account = target_account(match.kwargs['username'])
            path = reverse('accounts:detail', args=[account.username])
            target = InternalTarget('account', account, path)
        elif match.view_name == 'accounts:list-page':
            account_list = AccountList.objects.get(pk=match.kwargs['list_id'])
            path = reverse('accounts:list-page', args=[account_list.pk])
            target = InternalTarget('account-list', account_list, path)
        elif match.view_name.startswith('references:'):
            from .content_lists import get_target, list_query, route
            name = match.view_name.removeprefix('references:')
            if name in {'board-page', 'interface-page'}:
                kind = name.removesuffix('-page')
                instance = get_target(kind, match.kwargs['target_id'], request.user, require_view=False)
                path = route(kind, 'page', instance.pk)
                target = InternalTarget(kind, instance, path)
            elif name in {'board-list-page', 'interface-list-page'}:
                kind = name.removesuffix('-list-page')
                instance = list_query(kind).filter(pk=match.kwargs['list_id']).first()
                if instance is None:
                    raise invalid
                path = route(kind, 'list-page', instance.pk)
                target = InternalTarget(kind + '-list', instance, path)
            else:
                raise invalid
        else:
            raise invalid
        if parts.path != path:
            raise invalid
        return target
    except (ValueError, Resolver404, Http404, AccountList.DoesNotExist):
        raise invalid from None
