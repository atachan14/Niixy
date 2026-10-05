"""AccountLayout publication/application. Public reads never write to the DB."""
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max

from .models import (AccountLayout, AccountLayoutDraft, AccountLayoutVersion,
    AccountLayoutRequireField, AccountLayoutRequireIF, AccountLayoutItem,
    AccountLayoutApplication, FieldDefinition, Interface)
from .layout_renderer import ALIAS, fail, html_fragment, stylesheet, render_document
from .account_applications import account_bindings, display_value
from .versioning import interface_availability, application_state


def ids(value):
    if not isinstance(value, list) or len(value) > 32 or any(type(i) is not int or i < 1 for i in value) or len(set(value)) != len(value):
        fail('Requireは重複なし・各32件以内のIDで選択してください。')
    return value


def prepare(payload):
    if not isinstance(payload, dict):
        fail('Layoutの入力を確認してください。')
    name, description = payload.get('name', ''), payload.get('description', '')
    if not isinstance(name, str) or not name.strip() or len(name) > 120:
        fail('名前は1〜120文字で書いてください。')
    if not isinstance(description, str) or len(description) > 2000:
        fail('詳細は2,000文字以内で書いてください。')
    requirements = payload.get('requirements', {})
    if not isinstance(requirements, dict) or set(requirements) - {'fields', 'interfaces'}:
        fail('RequireField / RequireAccountIFを選択してください。')
    field_ids, interface_ids = ids(requirements.get('fields', [])), ids(requirements.get('interfaces', []))
    fields = list(FieldDefinition.objects.filter(pk__in=field_ids).select_related('current_version', 'creator').order_by('pk'))
    interfaces = list(Interface.objects.filter(pk__in=interface_ids, kind=Interface.ACCOUNT).select_related('current_version', 'creator').order_by('pk'))
    if len(fields) != len(field_ids) or len(interfaces) != len(interface_ids):
        fail('Requireの定義が見つかりません。AccountIFだけを選択できます。')
    candidates = {}
    for f in fields:
        if f.status != f.ACTIVE or not f.current_version_id:
            fail(f'{f.name} の最新版は利用できません。')
        candidates[f.pk] = f.current_version
    for interface in interfaces:
        availability = interface_availability(interface)
        if not availability.usable:
            fail(f'{interface.name}: ' + ' '.join(availability.reasons))
        for f in interface.current_version.fields.select_related('field_version').all():
            candidates[f.definition_id] = f.field_version
    items = payload.get('items', [])
    if not isinstance(items, list) or len(items) > 32:
        fail('Itemは32件以内で追加してください。')
    aliases, prepared_items = set(), []
    for item in items:
        if not isinstance(item, dict) or set(item) != {'alias', 'field_id'} or not isinstance(item['alias'], str) or not ALIAS.fullmatch(item['alias']):
            fail('Item変数名は英字から始まる英数字・アンダースコア、32文字以内で書いてください。')
        alias = item['alias']
        if alias in aliases:
            fail(f'変数名「{alias}」が重複しています。')
        aliases.add(alias)
        if type(item['field_id']) is not int or item['field_id'] not in candidates:
            fail(f'Item「{alias}」のFieldを先にRequireへ追加してください。RequireAccountIF内のFieldも使えます。')
        prepared_items.append((alias, candidates[item['field_id']]))
    html, css = payload.get('html', ''), payload.get('css', '')
    html_fragment(html, aliases)
    stylesheet(css)
    return {'name': name.strip(), 'description': description, 'html': html, 'css': css,
            'requirements': {'fields': field_ids, 'interfaces': interface_ids}, 'items': items,
            'fields': fields, 'interfaces': interfaces, 'prepared_items': prepared_items,
            'candidates': candidates}


def dependency_signature(data):
    return {'fields': [(f.pk, f.current_version_id) for f in data['fields']],
            'interfaces': [(i.pk, i.current_version_id) for i in data['interfaces']],
            'items': [(a, f.pk) for a, f in data['prepared_items']]}


def preview_token(account, payload, data):
    return signing.dumps({'account': account.pk, 'payload': payload, 'dependencies': dependency_signature(data)}, salt='account-layout-preview', compress=True)


def check_token(token, account, payload, data):
    try:
        actual = signing.loads(token, salt='account-layout-preview', max_age=600)
        # JSON serialization turns tuples into lists.
        expected = signing.loads(preview_token(account, payload, data), salt='account-layout-preview')
    except (signing.BadSignature, TypeError):
        fail('公開前にプレビューで内容と最新版の依存を確認してください。')
    if actual != expected:
        fail('入力または依存の最新版が変わりました。プレビューを更新してから公開してください。')


def values_for(account, items, *, sample=False):
    bindings = {b.definition_id: b for b in account_bindings(account)}
    return {alias: {'name': f.name, 'value': display_value(bindings[f.definition_id].value.value)
                   if f.definition_id in bindings else 'サンプル値' if sample else '未入力'} for alias, f in items}


def preview(account, payload):
    data = prepare(payload)
    return {'document': render_document(data['html'], data['css'], [a for a, _ in data['prepared_items']],
                        values_for(account, data['prepared_items'], sample=True)),
            'token': preview_token(account, payload, data)}


@transaction.atomic
def save_draft(account, draft_id, payload, *, publish=False, token=None):
    data = prepare(payload)
    # Same publisher lock order as Field/IF application foundation.
    dep_ids = set(data['candidates'])
    list(FieldDefinition.objects.select_for_update().filter(pk__in=dep_ids).order_by('pk'))
    list(Interface.objects.select_for_update().filter(pk__in=data['requirements']['interfaces']).order_by('pk'))
    original = AccountLayoutDraft.objects.get(pk=draft_id, creator=account)
    layout = AccountLayout.objects.select_for_update().get(pk=original.layout_id) if original.layout_id else None
    account = get_user_model().objects.select_for_update().get(pk=account.pk)
    draft = AccountLayoutDraft.objects.select_for_update().get(pk=draft_id, creator=account)
    data = prepare(payload)
    if publish:
        check_token(token, account, payload, data)
    if AccountLayout.objects.filter(creator=account, name__iexact=data['name']).exclude(pk=draft.layout_id).exists():
        fail('同じ名前のAccountLayoutがあるため、別の名前を使ってください。')
    for key in ('name', 'description', 'html', 'css', 'requirements', 'items'):
        setattr(draft, key, data[key])
    draft.save()
    if not publish:
        return draft
    if layout is None:
        layout = AccountLayout.objects.create(creator=account, name=data['name'])
    number = (layout.versions.aggregate(n=Max('version_number'))['n'] or 0) + 1
    version = AccountLayoutVersion.objects.create(layout=layout, version_number=number,
        **{key: data[key] for key in ('name', 'description', 'html', 'css')})
    for f in data['fields']:
        AccountLayoutRequireField.objects.create(version=version, field_version=f.current_version)
    for i in data['interfaces']:
        AccountLayoutRequireIF.objects.create(version=version, interface_version=i.current_version)
    for alias, f in data['prepared_items']:
        AccountLayoutItem.objects.create(version=version, alias=alias, field_version=f)
    layout.name, layout.current_version = data['name'], version
    layout.save(update_fields=['name', 'current_version', 'updated_at'])
    draft.delete()
    return version


def draft_payload(draft):
    return {key: getattr(draft, key) for key in ('name', 'description', 'html', 'css', 'requirements', 'items')}


@transaction.atomic
def edit_draft(account, layout_id):
    layout = AccountLayout.objects.select_for_update().get(pk=layout_id, creator=account)
    existing = AccountLayoutDraft.objects.filter(layout=layout).first()
    if existing:
        return existing
    v = layout.current_version
    return AccountLayoutDraft.objects.create(creator=account, layout=layout,
        name=v.name, description=v.description, html=v.html, css=v.css,
        requirements={'fields': list(v.require_fields.values_list('field_version__definition_id', flat=True)),
                      'interfaces': list(v.require_interfaces.values_list('interface_version__interface_id', flat=True))},
        items=[{'alias': i.alias, 'field_id': i.field_version.definition_id} for i in v.items.select_related('field_version')])


def availability(version):
    reasons = []
    for r in version.require_fields.select_related('field_version__definition'):
        f = r.field_version
        if f.definition.status != f.definition.ACTIVE or f.definition.current_version_id != f.pk:
            reasons.append(f'{f.name} の最新版への対応が必要です。')
    for r in version.require_interfaces.select_related('interface_version__interface__current_version'):
        v, interface = r.interface_version, r.interface_version.interface
        if interface.current_version_id != v.pk or not interface_availability(interface).usable:
            reasons.append(f'{v.name} の最新版への対応が必要です。')
    return reasons


def requirement_status(account, version):
    bindings = {b.definition_id: b for b in account_bindings(account)}
    implementations = {i.interface_id: i for i in account.interface_implementations.select_related('interface__current_version', 'version')}
    result = []
    for r in version.require_fields.select_related('field_version__definition__creator'):
        f = r.field_version; b = bindings.get(f.definition_id)
        result.append({'kind': 'field', 'id': f.definition_id, 'version': f.version_number, 'name': f.name,
                       'creator': f.definition.creator.username, 'ready': b is not None and b.version_id == f.pk,
                       'reason': '未適用または版更新が必要です。'})
    for r in version.require_interfaces.select_related('interface_version__interface__creator'):
        v = r.interface_version; i = implementations.get(v.interface_id)
        result.append({'kind': 'interface', 'id': v.interface_id, 'version': v.version_number, 'name': v.name,
                       'creator': v.interface.creator.username,
                       'ready': i is not None and i.version_id == v.pk and application_state(i) == i.ACTIVE,
                       'reason': 'AccountIFの実際の適用・更新が必要です。Fieldだけでは代替できません。'})
    return result


@transaction.atomic
def apply_layout(account, layout_id, expected_version=None):
    layout = AccountLayout.objects.select_related('current_version').get(pk=layout_id)
    version = layout.current_version
    if expected_version is not None and version.pk != expected_version:
        fail('Layoutの公開版が変わりました。詳細を読み直してください。')
    field_ids = set(version.require_fields.values_list('field_version__definition_id', flat=True))
    field_ids.update(version.require_interfaces.values_list('interface_version__fields__definition_id', flat=True))
    list(FieldDefinition.objects.select_for_update().filter(pk__in=field_ids).order_by('pk'))
    list(Interface.objects.select_for_update().filter(pk__in=version.require_interfaces.values_list('interface_version__interface_id', flat=True)).order_by('pk'))
    layout = AccountLayout.objects.select_for_update().get(pk=layout_id)
    if layout.current_version_id != version.pk:
        fail('Layoutの公開版が変わりました。詳細を読み直してください。')
    account = get_user_model().objects.select_for_update().get(pk=account.pk)
    reasons = availability(version)
    if reasons:
        fail(' '.join(reasons))
    missing = [r for r in requirement_status(account, version) if not r['ready']]
    if missing:
        fail('必要Modを先に適用・更新してください: ' + '、'.join(r['name'] for r in missing))
    AccountLayoutApplication.objects.update_or_create(account=account, defaults={'version': version})


def removal_guard(account, operation, item):
    application = AccountLayoutApplication.objects.filter(account=account).select_related('version').first()
    if application is None:
        return
    v = application.version
    if operation == 'remove_interface' and v.require_interfaces.filter(interface_version__interface_id=item.interface_id).exists():
        fail('使用中のAccountLayoutが必要とするAccountIFです。先にLayoutを変更・取り外してください。')
    needed = set(v.require_fields.values_list('field_version__definition_id', flat=True))
    needed.update(v.items.values_list('field_version__definition_id', flat=True))
    if operation == 'remove_field':
        lost = {item.definition_id} if not item.binding.interface_values.exists() else set()
    else:
        lost = {val.binding.definition_id for val in item.values.select_related('binding')
                if not val.binding.direct_implementations.exists() and not val.binding.interface_values.exclude(implementation=item).exists()}
    if needed & lost:
        fail('使用中のAccountLayoutが表示するFieldです。先にLayoutを変更・取り外してください。')


def profile_context(account):
    app = AccountLayoutApplication.objects.filter(account=account).select_related('version__layout').first()
    if app is None:
        return {}
    v = app.version
    items = [(i.alias, i.field_version) for i in v.items.select_related('field_version')]
    return {'account_layout_application': app,
            'account_layout_document': render_document(v.html, v.css, [a for a, _ in items], values_for(account, items)),
            'account_layout_frozen': bool(availability(v)) or any(not r['ready'] for r in requirement_status(account, v))}
