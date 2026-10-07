"""Basic invalid-POST regression on an isolated SQLite LiveServer."""
import json
import os
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase

from scripts.browser_test_server import SharedSQLiteStaticFilesHandler

VIEWPORTS = [('desktop', {'width': 1280, 'height': 720}),
             ('mobile', {'width': 390, 'height': 844})]
INVALID_NAMES = [('emoji', '山田😀', '絵文字は使えません。'),
                 ('width', 'あ' * 13, '表示名は全角12文字、半角24文字相当までです。')]


class BasicInformationBrowserTests(StaticLiveServerTestCase):
    static_handler = SharedSQLiteStaticFilesHandler

    def setUp(self):
        self.assertEqual(settings.DATABASES['default']['ENGINE'], 'django.db.backends.sqlite3')
        self.owner = get_user_model().objects.create_user('basic_qa_owner')
        self.owner.niixy_profile.display_name = '保存済み'
        self.owner.niixy_profile.save(update_fields=['display_name'])
        self.client.force_login(self.owner)
        self.session = self.client.cookies[settings.SESSION_COOKIE_NAME].value
        phase = os.environ.get('NIIXY_BASIC_QA_PHASE', 'after')
        self.assertIn(phase, ('before', 'after'))
        self.output = Path(settings.BASE_DIR) / '.artifacts' / 'basic-information-2026-10-07' / phase
        self.output.mkdir(parents=True, exist_ok=True)
        self.records = []

    def context(self, browser, name, size):
        context = browser.new_context(viewport=size, is_mobile=name == 'mobile', has_touch=name == 'mobile')
        context.add_cookies([{'name': settings.SESSION_COOKIE_NAME, 'value': self.session, 'url': self.live_server_url}])
        port = urlsplit(self.live_server_url).port
        errors, requests = [], []
        def guard(route):
            target = urlsplit(route.request.url)
            if (target.hostname in ('localhost', '127.0.0.1') and target.port != port) or target.hostname == 'niixy-psi.vercel.app':
                errors.append('forbidden endpoint: ' + target.netloc)
                route.abort()
            else:
                route.continue_()
        context.route('**/*', guard)
        page = context.new_page()
        page.set_default_timeout(10000)
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
        page.on('request', lambda request: requests.append((request.method, request.url)))
        return context, page, errors, requests

    def record(self, record):
        self.records.append(record)
        (self.output / f'{self._testMethodName}.json').write_text(
            json.dumps(self.records, ensure_ascii=False, indent=2), encoding='utf-8')
        print('BASIC_QA ' + json.dumps(record, ensure_ascii=False), flush=True)

    def assert_invalid_post(self, page, errors, requests, viewport, case, value, message):
        from playwright.sync_api import expect
        page.goto(self.live_server_url + '/mypage/', wait_until='networkidle')
        expect(page.locator('.mypage')).to_have_attribute('data-current-account', self.owner.username)
        page.locator('#open-basic-info').click()
        expect(page.locator('#id_display_name')).to_have_value('保存済み')
        page.locator('#id_display_name').fill(value)
        requests.clear()
        with page.expect_response(lambda response: response.request.method == 'POST' and urlsplit(response.url).path == '/mypage/') as posted:
            page.locator('.basic-info-form [type=submit]').click()
        response = posted.value
        page.wait_for_load_state('networkidle')
        expect(page.locator('.basic-info-form')).to_be_visible()
        page.wait_for_timeout(350)
        html = response.text()
        pane = page.locator('.basic-info-pane')
        box = pane.bounding_box()
        initializer_gets = [url for method, url in requests if method == 'GET'
                            and urlsplit(url).path == '/mypage/'
                            and parse_qs(urlsplit(url).query).get('_panes') == ['1']]
        observed = {
            'post_status': response.status,
            'server_error_present': message in html,
            'server_input_present': f'value="{value}"' in html,
            'browser_error_text': page.locator('.basic-info-form .field-error').all_text_contents(),
            'browser_input': page.locator('#id_display_name').input_value(),
            'initializer_gets': initializer_gets,
            'stage': page.locator('.mypage-workspace').get_attribute('data-ui-workspace-stage'),
            'pane_count': pane.count(),
            'right_edge': box['x'] + box['width'] if box else None,
            'overflow': page.evaluate('document.scrollingElement.scrollWidth-innerWidth'),
            'focused_input': page.locator('#id_display_name').evaluate('el=>el===document.activeElement'),
            'browser_errors': list(errors),
        }
        checks = {
            'server_rejected_and_kept_input': response.status == 200 and message in html and f'value="{value}"' in html,
            'error_kept': observed['browser_error_text'] == [message],
            'input_kept': observed['browser_input'] == value,
            'no_initializer_get': initializer_gets == [],
            'basic_visible_once': observed['stage'] == 'basic' and observed['pane_count'] == 1,
            'aligned_and_not_overflowing': box is not None and abs(observed['right_edge'] - page.viewport_size['width']) <= 1 and observed['overflow'] <= 2,
            'focus_and_no_errors': observed['focused_input'] and not errors,
        }
        page.screenshot(path=self.output / f'{viewport}-{case}.png', full_page=True)
        self.record({'viewport': viewport, 'case': case, 'observed': observed, 'checks': checks,
                     'result': 'passed' if all(checks.values()) else 'failed'})
        self.assertTrue(all(checks.values()), json.dumps({'observed': observed, 'checks': checks}, ensure_ascii=False))

    def test_invalid_post_retains_errors_and_input_desktop_mobile(self):
        from playwright.sync_api import sync_playwright, expect
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='msedge', headless=True)
            try:
                for viewport, size in VIEWPORTS:
                    for case, value, message in INVALID_NAMES:
                        with self.subTest(viewport=viewport, case=case):
                            context, page, errors, requests = self.context(browser, viewport, size)
                            try:
                                self.assert_invalid_post(page, errors, requests, viewport, case, value, message)
                                page.locator('#close-basic-info').click()
                                expect(page.locator('.mypage-workspace')).to_have_attribute('data-ui-workspace-stage', 'overview')
                                page.locator('#open-basic-info').click()
                                expect(page.locator('#id_display_name')).to_have_value('保存済み')
                                expect(page.locator('.basic-info-form .field-error')).to_have_count(0)
                                self.assertEqual(errors, [])
                            finally:
                                context.close()
            finally:
                browser.close()
        self.assertEqual(get_user_model().objects.get(pk=self.owner.pk).niixy_profile.display_name, '保存済み')

    def test_invalid_input_can_be_corrected_and_saved_desktop_mobile(self):
        from playwright.sync_api import sync_playwright, expect
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='msedge', headless=True)
            try:
                for viewport, size in VIEWPORTS:
                    with self.subTest(viewport=viewport):
                        context, page, errors, requests = self.context(browser, viewport, size)
                        try:
                            # Each viewport starts from the current stored value.
                            page.goto(self.live_server_url + '/mypage/', wait_until='networkidle')
                            page.locator('#open-basic-info').click()
                            page.locator('#id_display_name').fill('再試行😀')
                            with page.expect_navigation(wait_until='networkidle'):
                                page.locator('.basic-info-form [type=submit]').click()
                            expect(page.locator('.field-error')).to_have_text('絵文字は使えません。')
                            expect(page.locator('#id_display_name')).to_have_value('再試行😀')
                            corrected = '修正済みPC' if viewport == 'desktop' else '修正済み携帯'
                            page.locator('#id_display_name').fill(corrected)
                            with page.expect_navigation(wait_until='networkidle'):
                                page.locator('.basic-info-form [type=submit]').click()
                            expect(page.locator('#mypage-identity')).to_contain_text(corrected)
                            # Fresh overview has no DOM stage attribute until the first transition.
                            self.assertEqual(page.locator('.mypage-workspace').evaluate('el=>el.niixyWorkspace.stage'), 'overview')
                            page.locator('#open-basic-info').click()
                            expect(page.locator('#id_display_name')).to_have_value(corrected)
                            expect(page.locator('.field-error')).to_have_count(0)
                            page.wait_for_timeout(350)
                            box = page.locator('.basic-info-pane').bounding_box()
                            self.assertAlmostEqual(box['x'] + box['width'], size['width'], delta=1)
                            self.assertLessEqual(page.evaluate('document.scrollingElement.scrollWidth-innerWidth'), 2)
                            page.screenshot(path=self.output / f'{viewport}-correct-and-save-settled.png', full_page=True)
                            page.locator('#close-basic-info').click()
                            expect(page.locator('.mypage-workspace')).to_have_attribute('data-ui-workspace-stage', 'overview')
                            self.assertEqual(errors, [])
                            self.record({'viewport': viewport, 'case': 'correct-and-save', 'result': 'passed', 'browser_errors': errors})
                        finally:
                            context.close()
            finally:
                browser.close()
        self.assertEqual(get_user_model().objects.get(pk=self.owner.pk).niixy_profile.display_name, '修正済み携帯')
