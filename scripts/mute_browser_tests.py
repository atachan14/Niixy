"""Representative desktop/mobile Mute + existing Workspace smoke, SQLite only."""
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase

from accounts.models import AccountMute, AccountReview
from events.models import Thread, ThreadAccessRule, ThreadPlacement, ThreadPost
from rooms.models import Board
from rooms.services import create_board, create_room
from scripts.browser_test_server import SharedSQLiteStaticFilesHandler


class MuteBrowserTests(StaticLiveServerTestCase):
    static_handler = SharedSQLiteStaticFilesHandler

    def setUp(self):
        self.assertEqual(settings.DATABASES['default']['ENGINE'], 'django.db.backends.sqlite3')
        User = get_user_model()
        self.viewer = User.objects.create_user('mute_browser_viewer')
        self.target = User.objects.create_user('mute_browser_target')
        self.other = User.objects.create_user('mute_browser_other')
        self.target.niixy_profile.display_name = 'ミュート対象'
        self.target.niixy_profile.save()
        for index in range(21):
            muter = User.objects.create_user(f'mute_browser_fixture_{index}')
            muter.niixy_profile.display_name = '表示名のあるミュート作者'
            muter.niixy_profile.save()
            AccountMute.objects.create(muter=muter, muted_account=self.target)
        AccountReview.objects.create(author=self.viewer, target=self.target, sentiment='love', body='Muteから独立したReview本文')
        self.room, _ = create_room(submission_id=uuid4(), owner=self.target, name='Mute Browser Room',
            description='SQLite only', latitude='35.681236', longitude='139.767125')
        self.board = Board.objects.get(placement__collection__room=self.room, name='掲示板')
        self.map_board, _ = create_board(submission_id=uuid4(), name='Muted Map Board', actor=self.target,
            latitude='35.681236', longitude='139.767125')
        for creator, location in [(self.target, self.board), (self.target, None), (self.other, None)]:
            thread = Thread.objects.create(creator=creator, title='Mute Browser Thread')
            ThreadPost.objects.create(thread=thread, number=1, creator=creator, body='開始本文')
            ThreadPost.objects.create(thread=thread, number=2, creator=self.target, body='ミュートする返信本文')
            ThreadPlacement.objects.create(thread=thread, kind='board' if location else 'niimap', board=location,
                latitude=None if location else '35.681236', longitude=None if location else '139.767125')
            for capability in ['view', 'write']:
                for audience in ['guest', 'account']:
                    ThreadAccessRule.objects.create(thread=thread, capability=capability, audience=audience)
            if not location and creator == self.target: self.hidden_thread = thread
            if creator == self.other: self.shown_thread = thread
        self.client.force_login(self.viewer)

    def test_unsaved_review_mute_confirmation_pc_mobile(self):
        from playwright.sync_api import sync_playwright, expect
        from scripts.browser_smoke import wait_for_trail_count
        output = Path(settings.BASE_DIR) / '.artifacts' / 'mute'
        output.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True)
            try:
                for name, size in [('desktop', {'width': 1280, 'height': 900}), ('mobile', {'width': 390, 'height': 844})]:
                    context = browser.new_context(viewport=size, is_mobile=name == 'mobile', has_touch=name == 'mobile')
                    context.add_cookies([{'name': settings.SESSION_COOKIE_NAME, 'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url': self.live_server_url}])
                    page = context.new_page(); page.set_default_timeout(10000)
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' and not msg.location.get('url', '').endswith('/favicon.ico') else None)
                    page.goto(self.live_server_url + '/accounts/mute_browser_target/')
                    section = page.locator('.account-overview-pane [data-review-section]')
                    mute = section.locator('[data-mute-form] button')
                    form = page.locator('[data-review-form]')
                    # Count writes without recording their contents.
                    page.evaluate("""() => { window.muteWrites = 0; window.originalMuteFetch = window.fetch;
                        window.fetch = (...args) => {
                            if (String(args[0]).endsWith('/mute/')) window.muteWrites += 1;
                            return window.originalMuteFetch(...args);
                        }; }""")
                    # An unchanged Review needs no confirmation; a dirty closed
                    # draft does, even if the visible editing Pane is absent.
                    section.locator('[data-review-edit=love]').first.click()
                    expect(form).to_be_visible()
                    form.locator('[data-review-cancel]').click(); wait_for_trail_count(page, 0)
                    with page.expect_navigation(): mute.click()
                    expect(mute).to_have_attribute('aria-pressed', 'true')
                    with page.expect_navigation(): mute.click()
                    expect(mute).to_have_attribute('aria-pressed', 'false')
                    page.evaluate("""() => { window.muteWrites = 0; window.originalMuteFetch = window.fetch;
                        window.fetch = (...args) => {
                            if (String(args[0]).endsWith('/mute/')) window.muteWrites += 1;
                            return window.originalMuteFetch(...args);
                        }; }""")
                    section.locator('[data-review-edit=hate]').first.click()
                    expect(form).to_be_visible()
                    form.locator('textarea').fill('保持する未保存Review ' + name)
                    expect(section.locator('[data-review-edit=love]').first).to_have_attribute('aria-pressed', 'true')
                    # Exercise an open-editor Mute submit, then normal UI after Close.
                    def dismiss(dialog):
                        self.assertIn('未保存のReview', dialog.message)
                        dialog.dismiss()
                    page.once('dialog', dismiss)
                    section.locator('[data-mute-form]').evaluate("el => el.dispatchEvent(new Event('submit', {bubbles: true, cancelable: true}))")
                    expect(form.locator('textarea')).to_have_value('保持する未保存Review ' + name)
                    expect(form).to_be_visible()
                    self.assertEqual(page.evaluate('window.muteWrites'), 0)
                    # A failed confirmed Mute freezes input while pending and
                    # restores it without discarding the Review afterward.
                    page.evaluate("""() => { window.guardFetch = window.fetch; window.fetch = (...args) =>
                        String(args[0]).endsWith('/mute/') ? new Promise(resolve => {
                            window.releaseGuardWrite = () => resolve(new Response(JSON.stringify({error: 'QA保留後の通信失敗'}), {status: 503, headers: {'Content-Type': 'application/json'}}));
                        }) : window.guardFetch(...args); }""")
                    page.once('dialog', lambda dialog: dialog.accept())
                    section.locator('[data-mute-form]').evaluate("el => el.dispatchEvent(new Event('submit', {bubbles: true, cancelable: true}))")
                    expect(form.locator('textarea')).to_be_disabled()
                    expect(form.locator('[type=submit]')).to_be_disabled()
                    page.evaluate('() => window.releaseGuardWrite()')
                    expect(section.locator('.review-error')).to_contain_text('QA保留後の通信失敗')
                    expect(form.locator('textarea')).to_be_enabled()
                    expect(form.locator('textarea')).to_have_value('保持する未保存Review ' + name)
                    expect(mute).to_have_attribute('aria-pressed', 'false')
                    page.evaluate('() => { window.fetch = window.guardFetch; }')
                    form.locator('[data-review-cancel]').click(); wait_for_trail_count(page, 0)
                    page.once('dialog', dismiss); mute.click()
                    expect(mute).to_have_attribute('aria-pressed', 'false')
                    self.assertEqual(page.evaluate('window.muteWrites'), 0)
                    section.locator('[data-review-edit=love]').first.click()
                    expect(form.locator('textarea')).to_have_value('保持する未保存Review ' + name)
                    page.screenshot(path=output / f'{name}-draft-retained.png')
                    form.locator('[data-review-cancel]').click(); wait_for_trail_count(page, 0)
                    # Another Account's closed Review draft also survives a
                    # cancelled Mute, because reload would otherwise discard it.
                    section.locator('[data-review-tab=muter]').click()
                    section.locator('.muter-summary').first.click(); wait_for_trail_count(page, 1)
                    nested = page.locator('.ui-workspace-trail-pane [data-review-section]')
                    nested.locator('[data-review-edit=love]').first.click(); wait_for_trail_count(page, 2)
                    form.locator('textarea').fill('別Accountの未保存Review ' + name)
                    form.locator('[data-review-cancel]').click(); wait_for_trail_count(page, 1)
                    nested_mute = nested.locator('[data-mute-form] button')
                    page.once('dialog', dismiss); nested_mute.click()
                    self.assertEqual(page.evaluate('window.muteWrites'), 0)
                    nested.locator('[data-review-edit=love]').first.click(); wait_for_trail_count(page, 2)
                    expect(form.locator('textarea')).to_have_value('別Accountの未保存Review ' + name)
                    form.locator('[data-review-cancel]').click(); wait_for_trail_count(page, 1)
                    page.locator('.ui-workspace-trail-header .icon-button').click(); wait_for_trail_count(page, 0)
                    # Confirmed discard still performs the requested Mute,
                    # while the persisted Love/Review body remains unchanged.
                    page.once('dialog', lambda dialog: dialog.accept())
                    with page.expect_navigation(): mute.click()
                    expect(mute).to_have_attribute('aria-pressed', 'true')
                    expect(section.locator('[data-review-edit=love]').first).to_have_attribute('aria-pressed', 'true')
                    expect(section.locator('.review-post .thread-post-body')).to_have_text('Muteから独立したReview本文')
                    with page.expect_navigation(): mute.click()
                    expect(mute).to_have_attribute('aria-pressed', 'false')
                    self.assertEqual(errors, [])
                    context.close()
            finally:
                browser.close()

    def test_mute_pc_mobile_and_existing_workspace_smoke(self):
        from playwright.sync_api import sync_playwright, expect
        from scripts.browser_smoke import main as smoke_main
        output = Path(settings.BASE_DIR) / '.artifacts' / 'mute'
        output.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True)
            try:
                for name, size in [('desktop', {'width': 1280, 'height': 900}), ('mobile', {'width': 390, 'height': 844})]:
                    context = browser.new_context(viewport=size, is_mobile=name == 'mobile', has_touch=name == 'mobile')
                    context.add_cookies([{'name': settings.SESSION_COOKIE_NAME, 'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url': self.live_server_url}])
                    page = context.new_page(); page.set_default_timeout(10000)
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' and not msg.location.get('url', '').endswith('/favicon.ico') else None)
                    target_url = self.live_server_url + '/accounts/mute_browser_target/'
                    page.goto(target_url)
                    section = page.locator('.account-overview-pane [data-review-section]')
                    mute = section.locator('[data-mute-form] button')
                    expect(mute).to_have_attribute('aria-pressed', 'false')
                    expect(section.locator('[data-review-edit=love]').first).to_have_attribute('aria-pressed', 'true')
                    # Rejected write keeps state usable; retry uses the same desired state.
                    page.evaluate("""() => { window.muteFetch = window.fetch; window.fetch = (...args) =>
                        String(args[0]).endsWith('/mute/') ? Promise.resolve(new Response(JSON.stringify({error: 'QA通信失敗'}), {status: 503, headers: {'Content-Type': 'application/json'}})) : window.muteFetch(...args); }""")
                    mute.click(); expect(section.locator('.review-error')).to_contain_text('QA通信失敗')
                    expect(mute).to_have_attribute('aria-pressed', 'false'); expect(mute).to_be_enabled()
                    page.evaluate('() => { window.fetch = window.muteFetch; }')
                    with page.expect_navigation(): mute.click()
                    expect(mute).to_have_attribute('aria-pressed', 'true')
                    expect(section.locator('[data-review-edit=love]').first).to_have_attribute('aria-pressed', 'true')
                    expect(section.locator('[data-review-tab=muter]')).to_contain_text('22')
                    section.locator('[data-review-tab=muter]').click()
                    expect(section.locator('.muter-summary')).to_have_count(8)
                    section.locator('[data-review-expand]').click()
                    expect(section.locator('.muter-summary')).to_have_count(10)
                    section.locator('[data-review-go-page="2"]').click()
                    expect(section).to_have_attribute('data-review-page', '2')
                    section.locator('[data-review-go-page="3"]').click()
                    expect(section.locator('.muter-summary')).to_have_count(2)
                    section.locator('[data-review-collapse]').click()
                    expect(section.locator('.muter-summary')).to_have_count(8)
                    section.scroll_into_view_if_needed()
                    bounds = section.evaluate("el => { const box = el.getBoundingClientRect(); return {left: box.left, right: box.right, viewport: innerWidth, scroll: el.scrollWidth, client: el.clientWidth}; }")
                    self.assertGreaterEqual(bounds['left'], -1, bounds)
                    self.assertLessEqual(bounds['right'], bounds['viewport'] + 1, bounds)
                    self.assertLessEqual(bounds['scroll'], bounds['client'] + 1, bounds)
                    page.screenshot(path=output / f'{name}-muter.png')
                    # A reply stays numbered and can be temporarily displayed.
                    page.goto(self.live_server_url + f'/?thread={self.shown_thread.pk}')
                    detail = page.locator(f'[data-thread-detail-pane="{self.shown_thread.pk}"]')
                    expect(detail).to_be_visible()
                    response = detail.locator('[data-thread-post-number="2"] [data-muted-response]')
                    expect(response).to_be_visible(); expect(response.locator('.thread-post-body')).to_be_hidden()
                    response.locator('summary').click(); expect(response.locator('.thread-post-body')).to_be_visible()
                    response.locator('summary').click(); expect(response.locator('.thread-post-body')).to_be_hidden()
                    self.assertEqual(page.locator('#thread-markers').evaluate('el => JSON.parse(el.textContent).map(item => item.id)'), [self.shown_thread.pk])
                    self.assertEqual(page.locator('#room-markers').evaluate('el => JSON.parse(el.textContent)'), [])
                    self.assertEqual(page.locator('#board-markers').evaluate('el => JSON.parse(el.textContent)'), [])
                    expect(page.locator('#thread-list')).to_be_visible()
                    page.screenshot(path=output / f'{name}-response.png')
                    page.goto(self.live_server_url + f'/?thread={self.hidden_thread.pk}')
                    expect(page.locator(f'[data-thread-detail-pane="{self.hidden_thread.pk}"]')).to_be_visible()
                    expect(page.locator(f'#thread-list .thread-item[data-thread-id="{self.hidden_thread.pk}"]')).to_have_count(0)
                    # Board/Room direct navigation remains available.
                    page.goto(self.live_server_url + f'/?board={self.map_board.pk}')
                    expect(page.locator('.ui-workspace-trail-pane [data-board-thread-create]')).to_be_visible()
                    page.goto(self.live_server_url + f'/rooms/{self.room.pk}/')
                    expect(page.locator('.room-overview-pane')).to_be_visible()
                    page.goto(target_url)
                    with page.expect_navigation(): mute.click()
                    expect(mute).to_have_attribute('aria-pressed', 'false')
                    expect(section.locator('[data-review-edit=love]').first).to_have_attribute('aria-pressed', 'true')
                    page.goto(self.live_server_url + '/')
                    self.assertEqual(len(page.locator('#thread-markers').evaluate('el => JSON.parse(el.textContent)')), 2)
                    self.assertEqual(len(page.locator('#room-markers').evaluate('el => JSON.parse(el.textContent)')), 1)
                    self.assertEqual(len(page.locator('#board-markers').evaluate('el => JSON.parse(el.textContent)')), 1)
                    context.clear_cookies(); page.goto(target_url)
                    expect(mute).to_be_disabled(); expect(section.locator('[data-review-tab=muter]')).to_contain_text('21')
                    self.assertEqual(errors, [])
                    context.close()
            finally:
                browser.close()
        # Run the existing script entry point on the verified isolated server.
        with patch('sys.argv', ['scripts/browser_smoke.py', '--base-url', self.live_server_url,
                               '--output-dir', str(Path(settings.BASE_DIR) / '.artifacts' / 'browser-smoke')]):
            self.assertEqual(smoke_main(), 0)
