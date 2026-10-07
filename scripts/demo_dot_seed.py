"""Append one explicitly approved fictional demo batch; no schema or server changes.

Default CLI action is a plan with no Django/DB initialization. Shared writes require
--action apply-neon, the exact public SHA, and the existing private inventory.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import UUID, uuid5

BATCH = 'niixy-demo-dot-20261007-v1'
PUBLIC_SHA = 'ddef8887100d93aa435d2e0eb506eef6689ddf2a'
NAMESPACE = UUID('ac9efa60-e5eb-4edb-9a01-e46080b88f11')
DISCLAIMER = 'これはNiixyの架空デモです。実在の人物・団体・作品・開催予定ではありません。'
LOCATION_NOTE = '地図の座標は公共空間付近への仮の配置で、実際の活動場所や施設を表しません。'
PERSONAS = [
    ('dot', '読書会サンプル', '物語を一緒に読む', '架空の短編集を題材に、感想や問いを持ち寄る読書会の見本です。'),
    ('dot2', '共同制作デモ', '小さな冊子を作る', '架空のZINE制作で、アイデア・役割・進捗を共有する見本です。'),
    ('dot3', '作品紹介サンプル', '作品の背景を伝える', '架空の作品「月のしおり」を紹介し、制作過程も公開する見本です。'),
    ('dot4', '学習記録デモ', '試して振り返る', '日付に依存しない学びの一巡を記録し、Fieldで回数や振り返りを整理する見本です。'),
    ('dot5', 'イベント見本', '展示の読み方を案内', '実際の開催や参加募集ではなく、作品展示の案内文や公開Listを見せる見本です。'),
]
FIELD_SPECS = [
    ('theme', 'テーマ（デモ）', 'short_text', {}),
    ('intro', '活動紹介（デモ）', 'long_text', {}),
    ('stage', '制作段階（デモ）', 'single_choice', {'options': ['構想', '制作中', '公開見本']}),
    ('reflection', '振り返り（デモ）', 'long_text', {}),
    ('count', '練習回数（デモ）', 'integer', {}),
]
THREAD_SPECS = [
    ('guide', 0, 'read_notice', 'デモの歩き方', 'RoomのBoard、Peopleの公開List、Profileのカード、AppliedとModuleを順に見ると、同じ活動を複数の機能で整理する例になります。見本用Accountはログインできません。', None, {}),
    ('reading', 0, 'read_chat', '架空の短編集を持ち寄る', '架空の短編集「風のポケット」を題材にした読書会の見本です。好きな一節の紹介、問い、次に読む視点をResponseに分けて記録します。', ('物語を一緒に読む', '公開見本'), {}),
    ('learning', 3, 'read_chat', '学びの一巡を記録する', '試す、観察する、振り返る、もう一度試すという流れの見本です。カレンダー上の予定ではなく、練習回数と気づきをFieldで残します。', None, {'count': '6', 'reflection': '説明を書いてから試すと、どこで迷ったかを振り返りやすくなりました。'}),
    ('making_guide', 1, 'make_notice', '共同制作の進め方の見本', '架空の冊子制作を、構成相談と制作ノートに分ける例です。Roomの初期Boardに加えて、用途別のBoardも使います。実在の仕事や依頼ではありません。', None, {}),
    ('zine', 1, 'make_chat', '架空ZINEの構成相談', '架空の冊子「小さな余白」の構成相談です。導入、作品ページ、あとがきを分担し、Responseで順に考えを足す見本です。', ('小さな冊子の共同制作', '制作中'), {}),
    ('design', 2, 'design', '色と余白の制作ノート', '架空ZINEの制作ノートです。ThreadIFでテーマと段階をまとめ、直接追加したFieldで振り返りを記録する組合せを見せています。', ('読みやすい紙面の試作', '制作中'), {'reflection': '色の数を減らし、余白をそろえると、見出しと本文の関係が分かりやすくなりました。'}),
    ('work', 2, 'account_work', '架空作品・月のしおり', '架空の短い作品「月のしおり」の紹介見本です。月明かりで本のページを探す小さな物語を想定し、作品の意図をThreadIFで添えています。画像・Album機能を実装済みとして扱う例ではありません。', ('本と月を題材にした架空作品', '公開見本'), {}),
    ('exhibit', 4, 'map_shelf', 'いつでも読める展示案内', '実際のイベントではない、架空の展示案内の見本です。会期や予約は設定せず、BoardListとThreadListを使って作品と制作過程へ案内します。', None, {}),
    ('observation', 3, None, '観察から始める学習メモ', 'NiiMapに直接置くThreadの見本です。実際の観察地点や個人の所在地ではありません。気づきを言葉にし、練習回数と振り返りを直接Fieldに残します。', None, {'count': '3', 'reflection': '同じ対象を三つの言い方で説明し、伝わる表現を比べました。'}),
]
REPLY_SPECS = [
    ('reading', 2, '紹介役の見本Responseです。結末よりも、主人公が選ぶ言葉に注目して読む案を出します。'),
    ('reading', 3, '学び役の見本Responseです。最初の感想と読み直した感想を分けて記録すると、視点の変化が見えそうです。'),
    ('reading', 0, 'まとめ役の見本Responseです。今回は「気になる言葉を一つ持ち寄る」という読み方の例にします。'),
    ('learning', 0, '見本Responseです。回数だけでなく、次に試すことを一つ書くと、学習記録を次の一巡へつなげられそうです。'),
    ('learning', 3, '振り返りの見本Responseです。次は一文で説明してから、具体例を足す方法を試す想定です。'),
    ('zine', 2, '作品担当の見本Responseです。作品ページごとに短いテーマを付けて、冊子全体のつながりを見せる案です。'),
    ('zine', 1, '構成担当の見本Responseです。導入から各作品へ進み、最後に制作ノートへ案内する構成にします。'),
    ('zine', 4, '案内担当の見本Responseです。初めて読む人向けの入口を公開ThreadListにまとめる例にします。'),
    ('design', 1, '制作担当の見本Responseです。二つの配色を比べ、本文の読みやすさを優先する想定です。'),
    ('design', 2, '振り返りの見本Responseです。次の試作では、見出しの高さをそろえて比較する想定です。'),
    ('work', 4, '展示案内の見本Responseです。作品紹介と制作過程へのリンクを別々に示すと、興味に合わせて読めそうです。'),
    ('observation', 3, '学習の見本Responseです。短い説明、具体例、振り返りを一組にして、次の練習にも使う想定です。'),
]


def submission(key):
    return uuid5(NAMESPACE, BATCH + '/' + key)


def plan():
    return {'batch': BATCH, 'accounts': [{'username': p[0], 'display_name': p[1]} for p in PERSONAS],
            'rooms': 2, 'boards': 11, 'threads': 9, 'responses': 12, 'opening_posts': 9,
            'public_lists': 5, 'fields': 5, 'interfaces': {'account': 1, 'thread': 1},
            'account_if_applications': 5, 'account_layouts': 1, 'account_layout_applications': 5,
            'new_map_markers': 4, 'evaluations': 0}


def preservation_snapshot():
    from django.apps import apps
    from django.contrib.auth import get_user_model
    from django.core.serializers.json import DjangoJSONEncoder
    result = {}
    for model in apps.get_models():
        if not model._meta.managed or not (model._meta.app_label in ('accounts', 'rooms', 'interfaces', 'events') or model == get_user_model()):
            continue
        if model._meta.label in ('events.Station', 'events.Locality'):
            continue
        fields = [field.attname for field in model._meta.concrete_fields]
        if model == get_user_model():
            fields = ['pk', 'is_active', 'is_staff', 'is_superuser', 'date_joined', 'last_login']
        assert model.objects.count() < 50000, 'Preservation row bound exceeded'
        result[model._meta.label] = {
            str(row['pk']): hashlib.sha256(json.dumps(row, cls=DjangoJSONEncoder, sort_keys=True,
                ensure_ascii=False).encode('utf-8')).hexdigest()
            for row in model.objects.order_by('pk').values('pk', *fields).iterator(chunk_size=250)}
    return result


def assert_preserved(before, after):
    for label, rows in before.items():
        for pk, digest in rows.items():
            assert after[label].get(pk) == digest, 'Existing row changed in ' + label


def _response(view, actor, path, payload, **kwargs):
    from django.test import RequestFactory
    request = RequestFactory().post(path, payload, HTTP_HOST='127.0.0.1')
    request.user = actor
    response = view(request, **kwargs)
    assert response.status_code in (200, 201), 'Canonical action rejected: ' + path + ' ' + str(response.status_code) + ' ' + response.content.decode('utf-8')
    return json.loads(response.content)


def manifest():
    from django.contrib.auth import get_user_model
    from django.urls import reverse
    from accounts.models import AccountList
    from events.models import Thread, ThreadPost, ThreadList, ResponseList
    from interfaces.models import FieldDefinition, Interface, InterfaceList, AccountLayout
    from rooms.models import Room, Board, Collection
    users = [get_user_model().objects.get(username=p[0]) for p in PERSONAS]
    for user, persona in zip(users, PERSONAS):
        assert not user.is_active and not user.is_staff and not user.is_superuser and not user.has_usable_password()
        assert user.email == '' and user.niixy_profile.display_name == persona[1]
    rooms = {key: Room.objects.get(submission_id=submission('room/' + key)) for key in ('reading', 'making')}
    assert all(BATCH in room.description and room.owner_id in {u.pk for u in users} for room in rooms.values())
    fields = {key: FieldDefinition.objects.get(creator=users[1], name=name) for key, name, _, _ in FIELD_SPECS}
    interfaces = {
        'account': Interface.objects.get(creator=users[0], name='活動プロフィールIF（デモ）'),
        'thread': Interface.objects.get(creator=users[1], name='作品・学びカードIF（デモ）')}
    layout = AccountLayout.objects.get(creator=users[2], name='デモ活動カード')
    threads = {spec[0]: Thread.objects.get(submission_id=submission('thread/' + spec[0])) for spec in THREAD_SPECS}
    responses = [ThreadPost.objects.get(submission_id=submission('response/' + str(index))) for index in range(len(REPLY_SPECS))]
    for thread in threads.values():
        assert DISCLAIMER in thread.posts.get(number=1).body
    lists = {
        'people': (AccountList.objects.get(owner=users[0], submission_id=submission('list/people')), 'accounts:list-page'),
        'board': (Collection.objects.get(account=users[4], list_submission_id=submission('list/board')), 'references:board-list-page'),
        'thread': (ThreadList.objects.get(owner=users[1], submission_id=submission('list/thread')), 'references:thread-list-page'),
        'response': (ResponseList.objects.get(owner=users[3], submission_id=submission('list/response')), 'references:response-list-page'),
        'module': (InterfaceList.objects.get(owner=users[2], submission_id=submission('list/module')), 'references:interface-list-page')}
    boards = list(Board.objects.filter(creator__in=users).order_by('pk'))
    return {'batch': BATCH, 'public_sha': PUBLIC_SHA, 'plan': plan(),
            'accounts': [{'id': u.pk, 'username': u.username, 'display_name': u.niixy_profile.display_name,
                          'url': reverse('accounts:detail', args=[u.username])} for u in users],
            'rooms': {key: {'id': room.pk, 'url': reverse('rooms:detail', args=[room.pk]), 'name': room.name} for key, room in rooms.items()},
            'boards': [{'id': board.pk, 'url': reverse('references:board-page', args=[board.pk]), 'name': board.name} for board in boards],
            'fields': {key: {'id': f.pk, 'version_id': f.current_version_id, 'url': reverse('references:field-page', args=[f.pk])} for key, f in fields.items()},
            'interfaces': {key: {'id': i.pk, 'version_id': i.current_version_id, 'url': reverse('references:interface-page', args=[i.pk])} for key, i in interfaces.items()},
            'layout': {'id': layout.pk, 'version_id': layout.current_version_id, 'url': reverse('references:layout-page', args=[layout.pk])},
            'threads': {key: {'id': t.pk, 'url': reverse('references:thread-page', args=[t.pk]), 'title': t.title} for key, t in threads.items()},
            'responses': [{'id': post.pk, 'thread_id': post.thread_id, 'number': post.number,
                           'url': reverse('references:response-page', args=[post.pk])} for post in responses],
            'lists': {key: {'id': item.pk, 'url': reverse(route, args=[item.pk]), 'name': item.name} for key, (item, route) in lists.items()}}


def seed_demo():
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.urls import reverse
    from accounts.forms import NIIXY_ID_PATTERN, clean_display_name_value
    from accounts import lists as account_lists, content_lists
    from events import views as event_views
    from interfaces.account_applications import change_application
    from interfaces import account_layouts
    from interfaces.models import InterfaceDraft, InterfaceDraftField, AccountLayoutDraft
    from interfaces.services import publish_field_definition, publish_draft
    from rooms.models import Room, Board
    from rooms.services import create_room, create_board
    from rooms import views as room_views
    with transaction.atomic():
        if Room.objects.filter(submission_id=submission('room/reading')).exists():
            return dict(manifest(), created=False)
        User = get_user_model()
        assert not any(User.objects.filter(username__iexact=p[0]).exists() for p in PERSONAS), 'Demo username collision; existing Accounts preserved'
        users = []
        for username, display_name, _, _ in PERSONAS:
            assert NIIXY_ID_PATTERN.fullmatch(username)
            clean_display_name_value(display_name)
            user = User.objects.create_user(username=username, email='', password=None,
                                           is_active=False, is_staff=False, is_superuser=False)
            user.niixy_profile.display_name = display_name
            user.niixy_profile.save(update_fields=['display_name'])
            users.append(user)
        fields = {}
        for key, name, field_type, options in FIELD_SPECS:
            fields[key], _ = publish_field_definition(creator=users[1], name=name, field_type=field_type,
                settings=options, description=DISCLAIMER)
        interfaces = {}
        for kind, owner, name, keys in [
                ('account', users[0], '活動プロフィールIF（デモ）', ['theme', 'intro']),
                ('thread', users[1], '作品・学びカードIF（デモ）', ['theme', 'stage'])]:
            draft = InterfaceDraft.objects.create(creator=owner, kind=kind, name=name, description=DISCLAIMER)
            for position, key in enumerate(keys):
                InterfaceDraftField.objects.create(draft=draft, definition=fields[key], position=position, required=True)
            interfaces[kind], _ = publish_draft(draft.pk)
        for user, (_, _, theme, intro) in zip(users, PERSONAS):
            change_application(user, {'operation': 'add_interface', 'id': interfaces['account'].pk,
                'values': {str(fields['theme'].key): [theme], str(fields['intro'].key):
                           [DISCLAIMER + '\n見本用Accountはログインできません。\n' + intro]}})
        change_application(users[3], {'operation': 'add_field', 'id': fields['count'].pk,
                                     'values': {str(fields['count'].key): ['3']}})
        layout_payload = {
            'name': 'デモ活動カード', 'description': DISCLAIMER,
            'html': '<section class="demo-card"><p class="badge">架空デモ・見本用Account</p><h2>{{theme.value}}</h2><p>{{intro.value}}</p><p class="note">ログイン不可。活動内容・作品・開催予定は架空の例です。</p></section>',
            'css': '.demo-card {display:grid; gap:12px; padding:20px; background-color:#eef7f3; color:#183c32; border-radius:12px;} .badge {font-weight:700;} .note {font-size:14px;} @media (max-width:600px) {.demo-card {padding:16px;}}',
            'requirements': {'fields': [], 'interfaces': [interfaces['account'].pk]},
            'items': [{'alias': key, 'field_id': fields[key].pk} for key in ('theme', 'intro')]}
        draft = AccountLayoutDraft.objects.create(creator=users[2])
        version = account_layouts.save_draft(users[2], draft.pk, layout_payload, publish=True,
                                           token=account_layouts.preview(users[2], layout_payload)['token'])
        for user in users:
            account_layouts.apply_layout(user, version.layout_id, expected_version=version.pk)
        rooms = {}
        for key, owner, name, coords in [
                ('reading', users[0], '読書と学びのデモRoom', ('35.681236', '139.767125')),
                ('making', users[1], '共同制作のデモRoom', ('35.714700', '139.773200'))]:
            rooms[key], _ = create_room(submission_id=submission('room/' + key), owner=owner, name=name,
                description=DISCLAIMER + '\n' + LOCATION_NOTE + '\n' + BATCH,
                latitude=coords[0], longitude=coords[1])
            for user in users:
                if user != owner:
                    _response(room_views.room_join, user, reverse('rooms:join', args=[rooms[key].pk]), {}, room_id=rooms[key].pk)
        boards = {}
        for key, room_key in [('read', 'reading'), ('make', 'making')]:
            initial = list(Board.objects.filter(placement__collection__room=rooms[room_key]).order_by('pk'))
            assert len(initial) == 2
            boards[key + '_notice'], boards[key + '_chat'] = initial
        boards['design'], _ = create_board(submission_id=submission('board/design'), actor=users[1],
            collection=rooms['making'].collections.get(name='Main'), name='制作ノート（デモ）', description=DISCLAIMER)
        boards['map_shelf'], _ = create_board(submission_id=submission('board/map_shelf'), actor=users[4],
            name='作品展示の見本Board', description=DISCLAIMER + '\n' + LOCATION_NOTE,
            latitude='35.680880', longitude='139.766080')
        boards['account_work'] = Board.objects.get(placement__collection__account=users[2])
        public_view = [[{'kind': 'default', 'definition': {'code': code}}] for code in ('guest', 'account')]
        demo_write = [[{'kind': 'account', 'definition': {'account_id': u.pk}}] for u in users]
        policy = {f'policy_{capability}_{decision}_groups': json.dumps(groups)
                  for capability, decision, groups in [('view', 'allow', public_view), ('view', 'deny', []),
                                                       ('write', 'allow', demo_write), ('write', 'deny', [])]}
        threads = {}
        for key, actor_index, board_key, title, body, interface_values, direct_values in THREAD_SPECS:
            actor = users[actor_index]
            payload = {'submission_id': str(submission('thread/' + key)), 'title': '【デモ】' + title,
                       'body': DISCLAIMER + '\n\n' + body, **policy}
            if interface_values:
                payload['interface_ids'] = [str(interfaces['thread'].pk)]
                for field_key, value in zip(('theme', 'stage'), interface_values):
                    payload[f'interface_value_{interfaces["thread"].pk}_{fields[field_key].key}'] = [value]
            if direct_values:
                payload['direct_field_ids'] = [str(fields[k].pk) for k in direct_values]
                for field_key, value in direct_values.items():
                    payload[f'direct_field_value_{fields[field_key].key}'] = [value]
            if board_key is None:
                payload.update(latitude='35.713950', longitude='139.774100')
                result = _response(event_views.thread_create, actor, reverse('events:thread-create'), payload)
            else:
                board = boards[board_key]
                if board_key.startswith('read_'):
                    scope = {'room_id': rooms['reading'].pk}
                    route = reverse('rooms:board-thread-create', args=[rooms['reading'].pk, board.pk])
                elif board_key.startswith('make_') or board_key == 'design':
                    scope = {'room_id': rooms['making'].pk}
                    route = reverse('rooms:board-thread-create', args=[rooms['making'].pk, board.pk])
                elif board_key == 'account_work':
                    scope = {'username': actor.username}
                    route = reverse('accounts:board-thread-create', args=[actor.username, board.pk])
                else:
                    scope = {}
                    route = reverse('events:board-thread-create', args=[board.pk])
                result = _response(room_views.board_thread_create, actor, route, payload, board_id=board.pk, **scope)
            threads[key] = result['thread_id']
        from events.models import ThreadPost
        responses = []
        for index, (key, actor_index, body) in enumerate(REPLY_SPECS):
            _response(event_views.thread_post_create, users[actor_index],
                reverse('events:thread-post-create', args=[threads[key]]),
                {'submission_id': str(submission('response/' + str(index))), 'body': DISCLAIMER + '\n\n' + body}, thread_id=threads[key])
            responses.append(ThreadPost.objects.get(submission_id=submission('response/' + str(index))))
        people = _response(account_lists.create, users[0], reverse('accounts:list-create'),
            {'submission_id': str(submission('list/people')), 'name': 'デモの案内役'})
        for user in users[1:]:
            _response(account_lists.add, users[0], reverse('accounts:list-add', args=[people['list_id']]),
                {'target_url': reverse('accounts:detail', args=[user.username])}, list_id=people['list_id'])
        target_sets = [
            ('board', users[4], '会場と作品の棚（デモ）', [('board', boards[k].pk) for k in ('read_chat', 'design', 'map_shelf')]),
            ('thread', users[1], '制作の流れ（デモ）', [('thread', threads[k]) for k in ('zine', 'design', 'work')]),
            ('response', users[3], '振り返りの例（デモ）', [('response', responses[i].pk) for i in (1, 4, 9)]),
            ('interface', users[2], '使える部品（デモ）', [('interface', i.pk) for i in interfaces.values()]
                + [('field', f.pk) for f in fields.values()] + [('layout', version.layout_id)])]
        for kind, owner, name, targets in target_sets:
            key = 'module' if kind == 'interface' else kind
            item = _response(content_lists.create, owner, content_lists.route(kind, 'list-create'),
                {'submission_id': str(submission('list/' + key)), 'name': name}, kind=kind)
            for target_kind, target_id in targets:
                _response(content_lists.add, owner, content_lists.route(kind, 'list-add', item['list_id']),
                    {'target_url': reverse('references:' + target_kind + '-page', args=[target_id])}, kind=kind, list_id=item['list_id'])
        return dict(manifest(), created=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--action', choices=('plan', 'apply-neon'), default='plan')
    parser.add_argument('--public-sha')
    parser.add_argument('--private-dir', type=Path)
    args = parser.parse_args()
    if args.action == 'plan':
        print(json.dumps(plan(), ensure_ascii=True, indent=2))
        return
    assert args.public_sha == PUBLIC_SHA and args.private_dir, 'Explicit public SHA/private inventory required'
    repo = Path(__file__).resolve().parents[1]
    assert not args.private_dir.resolve().is_relative_to(repo), 'Private backup/artifacts must stay outside Git repository'
    sys.path.insert(0, str(repo))
    critical = ['accounts', 'events', 'interfaces', 'rooms', 'templates', 'config']
    for revision_args in ([PUBLIC_SHA, 'HEAD'], ['HEAD']):
        check = subprocess.run(['git', 'diff', '--quiet', *revision_args, '--', *critical], cwd=repo)
        assert check.returncode == 0, 'Public backend or working files differ; shared seed blocked'
    inventory = json.loads((args.private_dir / 'niixy-demo-20261007-inventory.json').read_text(encoding='utf-8'))
    assert inventory['public_sha'] == PUBLIC_SHA, 'Inventory public SHA mismatch'
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
    import django
    django.setup()
    from django.conf import settings
    from django.db import connection, transaction
    from django.db.migrations.executor import MigrationExecutor
    assert connection.vendor == 'postgresql' and settings.DATABASES['default']['HOST'].endswith('.neon.tech')
    args.private_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.private_dir / (BATCH + '-manifest.json')
    intent_path = args.private_dir / (BATCH + '-intent.json')
    if not intent_path.exists():
        intent_path.write_text(json.dumps({'public_sha': PUBLIC_SHA, 'plan': plan()}, ensure_ascii=False, indent=2), encoding='utf-8')
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            cursor.execute("SET LOCAL statement_timeout = '20s'")
            cursor.execute("SET LOCAL lock_timeout = '3s'")
            cursor.execute('SELECT pg_try_advisory_xact_lock(%s)', [int.from_bytes(hashlib.sha256(BATCH.encode()).digest()[:8], 'big', signed=True)])
            assert cursor.fetchone()[0], 'This demo batch is already running; no concurrent seed'
        executor = MigrationExecutor(connection)
        assert not executor.migration_plan(executor.loader.graph.leaf_nodes()), 'Pending migrations; shared seed blocked'
        before = preservation_snapshot()
        result = seed_demo()
        after = preservation_snapshot()
        assert_preserved(before, after)
        result['created_ids'] = {label: sorted(set(rows) - set(before[label])) for label, rows in after.items() if set(rows) - set(before[label])}
        result['existing_rows_preserved'] = True
        result['write_transaction'] = 'repeatable read; batch advisory lock; inserts/new-batch updates only'
        witness = args.private_dir / (BATCH + '-preapply-witness.json')
        if not witness.exists():
            witness.write_text(json.dumps(before, indent=2), encoding='utf-8')
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text(encoding='utf-8'))
        assert previous['accounts'] == result['accounts'] and previous['threads'] == result['threads'], 'Existing manifest mismatch; preserved'
        if not result['created']:
            print(json.dumps({'batch': BATCH, 'created': False, 'already_complete': True, 'no_write': True}))
            connection.close()
            return
    manifest_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'batch': BATCH, 'created': result['created'], 'plan': plan(),
                      'existing_rows_preserved': True, 'manifest_saved': True}, ensure_ascii=True))
    connection.close()


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('Demo seed stopped: ' + type(error).__name__)
        sys.exit(1)
