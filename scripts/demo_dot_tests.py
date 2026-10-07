"""Approved demo dataset QA, isolated SQLite only; no login/session creation."""
import json
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client

from events.models import Thread, ThreadPost
from interfaces.models import AccountLayoutApplication, AccountInterfaceImplementation
from rooms.models import Board, Room
from rooms.services import create_room
from scripts.browser_test_server import SharedSQLiteStaticFilesHandler
from scripts.demo_dot_seed import seed_demo, preservation_snapshot, assert_preserved, DISCLAIMER


class DemoDotTests(StaticLiveServerTestCase):
    static_handler = SharedSQLiteStaticFilesHandler

    def test_existing_case_insensitive_username_collision_is_atomic(self):
        self.assertEqual(settings.DATABASES['default']['ENGINE'], 'django.db.backends.sqlite3')
        get_user_model().objects.create_user('Dot', password=None)
        before = preservation_snapshot()
        with self.assertRaisesRegex(AssertionError, 'username collision'):
            seed_demo()
        self.assertEqual(preservation_snapshot(), before)

    def test_seed_replay_guest_policy_and_desktop_mobile(self):
        from playwright.sync_api import expect, sync_playwright
        self.assertEqual(settings.DATABASES['default']['ENGINE'], 'django.db.backends.sqlite3')
        existing = get_user_model().objects.create_user('demo_fixture_existing', password=None)
        create_room(submission_id=uuid4(), owner=existing, name='Unrelated fixture Room', description='Keep this',
                    latitude='35.67', longitude='139.75')
        before = preservation_snapshot()
        result = seed_demo()
        self.assertTrue(result['created'])
        after = preservation_snapshot()
        assert_preserved(before, after)
        expected = {'auth.User': 5, 'rooms.Room': 2, 'rooms.Board': 11, 'events.Thread': 9,
                    'events.ThreadPost': 21, 'interfaces.FieldDefinition': 5, 'interfaces.Interface': 2,
                    'interfaces.AccountLayout': 1}
        for label, number in expected.items():
            self.assertEqual(len(after[label]) - len(before[label]), number, label)
        replay = seed_demo()
        self.assertFalse(replay['created'])
        self.assertEqual(replay['accounts'], result['accounts'])
        self.assertEqual(replay['threads'], result['threads'])
        self.assertEqual(preservation_snapshot(), after)
        users = get_user_model().objects.filter(username__in=['dot', 'dot2', 'dot3', 'dot4', 'dot5'])
        self.assertEqual(AccountLayoutApplication.objects.filter(account__in=users).count(), 5)
        self.assertEqual(AccountInterfaceImplementation.objects.filter(account__in=users, state='active').count(), 5)
        guest = AnonymousUser()
        for thread in Thread.objects.filter(creator__in=users):
            self.assertTrue(thread.allows(guest, 'view'))
            self.assertFalse(thread.allows(guest, 'write'))
            self.assertIn(DISCLAIMER, thread.posts.get(number=1).body)
        for board in Board.objects.filter(creator__in=users):
            self.assertTrue(board.evaluate_policy(guest, 'view').allowed)
        for post in ThreadPost.objects.filter(creator__in=users):
            self.assertIn(DISCLAIMER, post.body)
        urls = ['/']
        for key in ('accounts', 'boards', 'responses'):
            urls.extend(item['url'] for item in result[key])
        for key in ('rooms', 'fields', 'interfaces', 'threads', 'lists'):
            urls.extend(item['url'] for item in result[key].values())
        urls.append(result['layout']['url'])
        client = Client()
        for url in urls:
            response = client.get(url)
            self.assertEqual(response.status_code, 200, url)
        self.assertNotIn(settings.SESSION_COOKIE_NAME, client.cookies)
        output = Path(settings.BASE_DIR) / '.artifacts/demo-dot-2026-10-07/sqlite'
        output.mkdir(parents=True, exist_ok=True)
        records = []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True)
            try:
                for viewport, size in [('desktop', {'width': 1280, 'height': 720}),
                                       ('mobile', {'width': 390, 'height': 844})]:
                    context = browser.new_context(viewport=size, is_mobile=viewport == 'mobile', has_touch=viewport == 'mobile')
                    errors = []
                    allowed = urlsplit(self.live_server_url)

                    def guard(route):
                        target = urlsplit(route.request.url)
                        if (route.request.method not in ('GET', 'HEAD') or
                                (target.hostname in ('127.0.0.1', 'localhost') and target.port != allowed.port) or
                                target.hostname == 'niixy-psi.vercel.app'):
                            errors.append('forbidden QA request: ' + route.request.method + ' ' + target.netloc)
                            route.abort()
                        else:
                            route.continue_()

                    context.route('**/*', guard)
                    context.route('https://cdn.geolonia.com/style/**', lambda route: route.fulfill(
                        status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'},
                        body=json.dumps({'version': 8, 'sources': {}, 'layers': [
                            {'id': 'background', 'type': 'background', 'paint': {'background-color': '#f7f6f2'}}]})))
                    page = context.new_page()
                    page.set_default_timeout(7000)
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.on('console', lambda message: errors.append(message.text) if message.type == 'error'
                            and not message.location.get('url', '').endswith('/favicon.ico') else None)
                    try:
                        for label, path in [
                                ('profile', result['accounts'][3]['url']),
                                ('thread', result['threads']['design']['url']),
                                ('modules', result['lists']['module']['url']),
                                ('room', result['rooms']['making']['url'])]:
                            response = page.goto(self.live_server_url + path, wait_until='networkidle')
                            self.assertEqual(response.status, 200)
                            if label == 'profile':
                                surface = page.locator('[data-account-layout-surface]')
                                expect(surface.locator('h2')).to_have_text('試して振り返る')
                                expect(surface.locator('.note')).to_contain_text('ログイン不可')
                            elif label == 'thread':
                                expect(page.locator('body')).to_contain_text(DISCLAIMER)
                                expect(page.locator('body')).to_contain_text('制作中')
                            elif label == 'modules':
                                expect(page.locator('body')).to_contain_text('使える部品（デモ）')
                                expect(page.locator('body')).to_contain_text('デモ活動カード')
                            else:
                                expect(page.locator('body')).to_contain_text('共同制作のデモRoom')
                            self.assertLessEqual(page.evaluate('document.scrollingElement.scrollWidth - innerWidth'), 2)
                            page.screenshot(path=output / f'{viewport}-{label}.png', full_page=True)
                            records.append({'viewport': viewport, 'page': label, 'path': path, 'http_status': 200,
                                            'horizontal_overflow_px': page.evaluate('document.scrollingElement.scrollWidth - innerWidth')})
                            if label == 'profile':
                                page.locator('[data-open-account-account-if]').click()
                                expect(page.locator('#account-if-list-pane')).to_be_visible()
                                page.locator('#account-if-list-pane [data-ui-tab="applied-interface"]').click()
                                expect(page.locator('#account-if-list-pane')).to_contain_text('活動プロフィールIF（デモ）')
                                page.locator('#account-if-list-pane [data-ui-tab="applied-field"]').click()
                                expect(page.locator('#account-if-list-pane')).to_contain_text('練習回数（デモ）')
                                page.wait_for_timeout(350)
                                self.assertLessEqual(page.evaluate('document.scrollingElement.scrollWidth - innerWidth'), 2)
                                page.screenshot(path=output / f'{viewport}-applied.png', full_page=True)
                        self.assertEqual(errors, [])
                    finally:
                        context.close()
            finally:
                browser.close()
        assert_preserved(before, preservation_snapshot())
        summary = {'created_deltas': expected, 'rerun_created': False, 'rerun_no_changes': True,
                   'existing_rows_preserved': True, 'guest_http_pages': len(urls),
                   'guest_thread_write_allowed': False, 'browser_errors': [], 'browser': records,
                   'manifest': result}
        (output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        print('DEMO_SQLITE_QA ' + json.dumps({key: value for key, value in summary.items() if key != 'manifest'}, ensure_ascii=True), flush=True)
