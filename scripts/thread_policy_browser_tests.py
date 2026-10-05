"""ThreadPolicy form regressions on an isolated SQLite live server."""
import json
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from scripts.browser_test_server import SharedSQLiteStaticFilesHandler
from events.models import Thread, ThreadPlacement, ThreadPost
from events.policies import prepare_thread_policy, save_thread_policy
from rooms.models import Board
from rooms.services import create_room


class ThreadPolicyBrowserTests(StaticLiveServerTestCase):
    static_handler = SharedSQLiteStaticFilesHandler

    def setUp(self):
        self.assertEqual(settings.DATABASES['default']['ENGINE'], 'django.db.backends.sqlite3')
        from django.core.signals import got_request_exception
        import sys, traceback
        self.server_errors = []
        def capture_exception(sender, **kwargs):
            self.server_errors.append(''.join(traceback.format_exception(*sys.exc_info())))
        got_request_exception.connect(capture_exception, weak=False)
        self.addCleanup(got_request_exception.disconnect, capture_exception)

        self.owner = get_user_model().objects.create_user('policy_browser')
        self.room, _ = create_room(submission_id=uuid4(), owner=self.owner, name='Policy Browser Room',
                                  description='', latitude='35.681236', longitude='139.767125')
        self.board = Board.objects.get()
        self.thread = Thread.objects.create(creator=self.owner, title='Denied Browser Thread')
        ThreadPost.objects.create(thread=self.thread, creator=self.owner, number=1, body='PRIVATE BROWSER BODY')
        ThreadPlacement.objects.create(thread=self.thread, kind='board', board=self.board)
        data = {f'policy_{cap}_{decision}_groups': '[]'
                for cap in ('view', 'write') for decision in ('allow', 'deny')}
        data['policy_view_allow_groups'] = json.dumps([[{'kind': 'default', 'definition': {'code': 'account'}}]])
        save_thread_policy(self.thread, prepare_thread_policy(data, self.owner))

    def check_editor(self, page, form, *, guest=False):
        form.locator('details:has([data-thread-policy-editor]) > summary').click()
        editor = form.locator('[data-thread-policy-editor]')
        self.assertEqual(editor.locator('[data-account-condition-groups-input]').count(), 4)
        for cap in ('view', 'write'):
            groups = json.loads(editor.locator(f'[name="policy_{cap}_allow_groups"]').input_value())
            self.assertEqual([group[0]['definition']['code'] for group in groups], ['guest', 'account'])
        editor.locator('[data-account-condition-target]').first.locator('button').first.click()
        form.evaluate('(el) => el.reset()')
        page.wait_for_timeout(50)
        self.assertEqual(len(json.loads(editor.locator('[name="policy_view_allow_groups"]').input_value())), 2)

        editor.locator('[data-open-account-conditions]').nth(1).click()
        page.locator('[data-browse-account-conditions]').click()
        page.wait_for_selector('[data-account-selector-content] .ui-summary-item')
        selector = page.locator('.account-selector-pane')
        self.assertFalse(selector.locator('[data-account-condition-kind="field"]').is_visible())
        self.assertFalse(selector.locator('[data-account-condition-kind="account_interface"]').is_visible())
        labels = selector.locator('[data-account-selector-content] .ui-summary-item-title').all_text_contents()
        self.assertIn('Guest', labels)
        self.assertEqual(len(labels), 1 if guest else 3, labels)
        selector.locator('[data-account-selector-content] .ui-summary-item').filter(has_text='Guest').click()
        history = page.locator('.account-condition-pane')
        history.locator('.account-condition-summary .ui-summary-item').filter(has_text='Guest').click()
        page.wait_for_selector('.account-condition-summary .ui-summary-item.is-selected')
        history.locator('[data-add-account-condition-group]').click()
        history.locator('[data-close-account-conditions]').click()
        groups = json.loads(editor.locator('[name="policy_view_deny_groups"]').input_value())
        self.assertEqual(groups[0][0]['definition']['code'], 'guest')
        form.evaluate('(el) => el.reset()')
        page.wait_for_timeout(50)
        self.assertEqual(json.loads(editor.locator('[name="policy_view_deny_groups"]').input_value()), [])

    def test_pc_mobile_policy_forms_and_denied_detail(self):
        from playwright.sync_api import sync_playwright
        output = Path(settings.BASE_DIR) / '.artifacts' / 'thread-policy'
        output.mkdir(parents=True, exist_ok=True)
        self.client.force_login(self.owner)
        session = self.client.cookies[settings.SESSION_COOKIE_NAME].value
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True)
            try:
                for name, size in [('desktop', {'width': 1280, 'height': 720}), ('mobile', {'width': 390, 'height': 844})]:
                    with self.subTest(viewport=name):
                        context = browser.new_context(viewport=size, is_mobile=name == 'mobile', has_touch=name == 'mobile')
                        context.add_cookies([{'name': settings.SESSION_COOKIE_NAME, 'value': session, 'url': self.live_server_url}])
                        page = context.new_page()
                        page.set_default_timeout(10000)
                        errors = []
                        failed_urls = []
                        failed_requests = []
                        page.on('requestfailed', lambda request: failed_requests.append((request.url.split('?')[0], request.failure)) if request.url.startswith(self.live_server_url) else None)
                        page.on('response', lambda response: failed_urls.append(response.url) if response.status >= 400 else None)
                        page.on('pageerror', lambda error: errors.append(str(error)))
                        page.on('console', lambda msg: errors.append((msg.text, msg.location)) if msg.type == 'error' and not msg.location.get('url', '').endswith('/favicon.ico') else None)
                        try:
                            page.goto(f'{self.live_server_url}/rooms/{self.room.pk}/?boards=1', wait_until='domcontentloaded')
                            page.locator(f'#room-list-content [data-open-board="{self.board.pk}"]').click()
                            page.locator('[data-board-create-toggle]').click()
                            form = page.locator('[data-board-thread-create]')
                            self.check_editor(page, form)
                            page.wait_for_timeout(500)
                            page.screenshot(path=output / f'{name}-board-policy.png', full_page=True)

                            page.goto(self.live_server_url + '/', wait_until='domcontentloaded')
                            page.locator('#niimap-create-toggle').click()
                            page.evaluate('map.fire("click", {lngLat: {lng: 139.767125, lat: 35.681236}})')
                            page.locator('#open-thread-create').click()
                            self.check_editor(page, page.locator('#thread-create-form'))
                            page.wait_for_timeout(500)
                            page.screenshot(path=output / f'{name}-map-policy.png', full_page=True)

                            context.clear_cookies()
                            page.goto(self.live_server_url + '/', wait_until='domcontentloaded')
                            page.locator('#niimap-create-toggle').click()
                            page.evaluate('map.fire("click", {lngLat: {lng: 139.767125, lat: 35.681236}})')
                            page.locator('#open-thread-create').click()
                            self.check_editor(page, page.locator('#thread-create-form'), guest=True)

                            response = page.request.get(f'{self.live_server_url}/accounts/{self.owner.username}/threads/{self.thread.pk}/')
                            self.assertEqual(response.status, 200)
                            self.assertIn('data-thread-view-unavailable', response.text())
                            self.assertNotIn('PRIVATE BROWSER BODY', response.text())
                            self.assertNotIn('thread-reply-form', response.text())
                            self.assertNotIn('data-thread-post-count', response.text())
                            self.assertNotIn('ui-placement-row', response.text())
                            page.goto(f'{self.live_server_url}/accounts/{self.owner.username}/?pane=thread&thread={self.thread.pk}', wait_until='domcontentloaded')
                            page.locator('[data-thread-view-unavailable]').wait_for()
                            self.assertNotIn('undefined', page.locator('#account-thread-detail-title').inner_text())
                            page.wait_for_timeout(500)
                            close_box = page.locator('#close-account-thread-detail').bounding_box()
                            self.assertLessEqual(close_box['x'] + close_box['width'], size['width'] + 1)
                            self.assertGreaterEqual(close_box['x'], 0)
                            page.screenshot(path=output / f'{name}-denied-thread.png', full_page=True)
                            for _ in range(6):
                                page.reload(wait_until='domcontentloaded')
                                page.locator('[data-thread-view-unavailable]').wait_for()
                                page.wait_for_timeout(100)
                            page.locator('#close-account-thread-detail').click()
                            self.assertEqual(errors, [], (errors, failed_urls))
                        finally:
                            page.screenshot(path=output / f'{name}-final.png', full_page=True)
                            if failed_requests or failed_urls:
                                print('Local browser failures:', failed_requests, [url.split('?')[0] for url in failed_urls if url.startswith(self.live_server_url)])
                                print('Isolated server exceptions:', self.server_errors)
                            context.close()
            finally:
                browser.close()
