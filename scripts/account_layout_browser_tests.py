"""Minimum AccountLayout loop on isolated SQLite + local Edge, PC/mobile."""
from pathlib import Path
import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase

from interfaces.models import InterfaceDraft, InterfaceDraftField, AccountLayoutApplication
from interfaces.services import publish_draft, publish_field_definition
from scripts.browser_test_server import SharedSQLiteStaticFilesHandler


class AccountLayoutBrowserTests(StaticLiveServerTestCase):
    static_handler = SharedSQLiteStaticFilesHandler

    def setUp(self):
        self.assertEqual(settings.DATABASES['default']['ENGINE'], 'django.db.backends.sqlite3')
        self.owner = get_user_model().objects.create_user('layout_browser')
        self.field, _ = publish_field_definition(creator=self.owner, name='紹介文', field_type='long_text')
        draft = InterfaceDraft.objects.create(creator=self.owner, name='Layout用AccountIF', kind='account')
        InterfaceDraftField.objects.create(draft=draft, definition=self.field, required=True, position=0)
        self.interface, _ = publish_draft(draft.pk)
        self.client.force_login(self.owner)

    def test_draft_publish_require_apply_and_natural_profile_pc_mobile(self):
        from playwright.sync_api import sync_playwright, expect
        output = Path(settings.BASE_DIR) / '.artifacts' / 'account-layout'
        output.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True)
            try:
                for viewport, size in [('desktop', {'width': 1280, 'height': 900}), ('mobile', {'width': 390, 'height': 844})]:
                    context = browser.new_context(viewport=size, is_mobile=viewport == 'mobile', has_touch=viewport == 'mobile')
                    context.add_cookies([{'name': settings.SESSION_COOKIE_NAME, 'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url': self.live_server_url}])
                    page = context.new_page(); page.set_default_timeout(10000)
                    errors, external = [], []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' and not msg.location.get('url', '').endswith('/favicon.ico') else None)
                    page.on('request', lambda request: external.append(request.url) if not request.url.startswith(self.live_server_url) else None)
                    page.goto(self.live_server_url + '/mypage/?section=module&type=layout&subtype=account')
                    page.locator('[data-layout-create-url]').click()
                    editor = page.locator('[data-layout-editor]')
                    expect(page).to_have_url(re.compile(r'layout_draft=\d+'))
                    editor.locator('input[name=name]').fill('Layout ' + viewport)
                    editor.locator(f'input[data-require-kind=interfaces][data-require-id="{self.interface.pk}"]').check()
                    editor.locator('[data-layout-add-item]').click()
                    editor.locator('.layout-item-row input').fill('intro')
                    editor.locator('textarea[name=html]').fill('<div class="card"><strong>{{intro.name}}</strong><p>{{intro.value}}</p><span>末尾まで表示</span></div>')
                    editor.locator('[data-layout-tab=css]').click()
                    editor.locator('textarea[name=css]').fill('.card{display:grid;grid-template-columns:1fr;gap:12px;padding:16px;background-color:#f2f4fa;border-radius:12px;} p{white-space:pre-wrap;color:#334455;} @media(max-width:600px){.card{padding:8px;}}')
                    editor.locator('[data-layout-save]').click()
                    expect(editor.locator('[data-layout-message]')).to_contain_text('Draftを保存しました')
                    page.reload()
                    expect(editor.locator('.layout-item-row input')).to_have_value('intro')
                    editor.locator('[data-layout-tab=preview]').click()
                    expect(editor.locator('[data-layout-preview-surface] [data-account-layout-surface]')).to_be_visible()
                    expect(editor.locator('[data-layout-preview-surface]')).to_contain_text('サンプル値')
                    page.screenshot(path=output / f'{viewport}-editor.png', full_page=True)
                    self.assertFalse(editor.evaluate('(el) => el.scrollWidth > el.clientWidth + 1'))
                    editor.locator('[data-layout-publish]').click()
                    detail = page.locator('[data-layout-detail]')
                    expect(page).to_have_url(re.compile(r'&layout=\d+'))
                    expect(detail).to_contain_text('Layout ' + viewport)
                    expect(detail.locator('[data-layout-apply]')).to_be_disabled()
                    detail.locator('[data-layout-require-url]').click()
                    requirement = page.locator('[data-layout-requirement]')
                    expect(requirement).to_contain_text('最新定義')
                    page.wait_for_function("() => { const el = document.querySelector('[data-layout-requirement]'); if (!el) return false; const r = el.getBoundingClientRect(); return r.left >= -1 && Math.abs(r.right - innerWidth) < 2; }")
                    long_value = '安全な紹介文\n' + '\n'.join('長い文章の折り返しと自然高さを確認します。' * 4 for _ in range(28)) + '\n<script src="https://example.invalid/x.js">& 末尾'
                    requirement.locator('[data-layout-require-inputs] textarea').fill(long_value)
                    page.screenshot(path=output / f'{viewport}-require.png', full_page=True)
                    requirement.locator('button[type=submit]').click()
                    expect(page.locator('[data-layout-requirement]')).to_have_count(0)
                    expect(detail.locator('[data-layout-apply]')).to_be_enabled()
                    detail.locator('[data-layout-apply]').click()
                    expect(detail.locator('[data-layout-message]')).to_contain_text('Profileに適用しました')
                    context.clear_cookies()
                    page.goto(self.live_server_url + '/accounts/layout_browser/')
                    surface = page.locator('[data-account-layout-surface]')
                    expect(surface).to_contain_text('安全な紹介文')
                    expect(surface.locator('span')).to_have_text('末尾まで表示')
                    self.assertGreater(surface.bounding_box()['height'], 512)
                    self.assertEqual(surface.evaluate("el => getComputedStyle(el).overflowY"), 'visible')
                    self.assertFalse(surface.evaluate('(el) => el.scrollWidth > el.clientWidth + 1'))
                    self.assertEqual(surface.locator('script, img, iframe').count(), 0)
                    self.assertEqual(surface.locator('p').evaluate('el => getComputedStyle(el).color'), 'rgb(51, 68, 85)')
                    self.assertNotEqual(page.locator('.identity-profile-placeholder > .field-help').evaluate('el => getComputedStyle(el).color'), 'rgb(51, 68, 85)')
                    self.assertIn('<script src=', surface.locator('p').inner_text())
                    surface.locator('span').scroll_into_view_if_needed()
                    expect(surface.locator('span')).to_be_in_viewport()
                    page.screenshot(path=output / f'{viewport}-profile-end.png', full_page=True)
                    page.locator('.account-overview-pane').evaluate('el => el.scrollTop = 0')
                    page.screenshot(path=output / f'{viewport}-profile.png', full_page=True)
                    page.locator('[data-open-account-modules]').click()
                    listing = page.locator('.profile-module-list-pane')
                    listing.locator('[data-module-type=layout]').click()
                    listing.locator('[data-module-subtypes=layout] [data-module-subtype=account]').click()
                    listing.locator('[data-module-panel="layout:self"] .module-summary-entry').filter(has_text='Layout ' + viewport).click()
                    public = page.locator('.profile-module-detail-pane')
                    expect(public).to_contain_text('AccountLayout')
                    expect(public.locator('[data-layout-apply], [data-layout-edit]')).to_have_count(0)
                    public.locator('[data-layout-require-url]').click()
                    expect(public.locator('[data-layout-requirement]')).to_contain_text('最新定義')
                    expect(public.locator('[data-layout-require-form]')).to_have_count(0)
                    public.locator('[data-layout-require-close]').click()
                    self.assertEqual(errors, [])
                    self.assertEqual(external, [])
                    if viewport == 'desktop':
                        # Reset via the same owner-only HTTP API so mobile exercises
                        # its own missing-Require Pane rather than inheriting a Mod.
                        context.add_cookies([{'name': settings.SESSION_COOKIE_NAME, 'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url': self.live_server_url}])
                        page.goto(self.live_server_url + '/mypage/')
                        csrf = page.locator('[name=csrfmiddlewaretoken]').first.input_value()
                        headers = {'X-CSRFToken': csrf}
                        response = page.request.post(self.live_server_url + '/accounts/layout_browser/layout/change/', data={'operation': 'remove'}, headers=headers)
                        self.assertTrue(response.ok)
                        applied = page.request.get(self.live_server_url + '/accounts/layout_browser/applied/data/').json()
                        response = page.request.post(self.live_server_url + '/accounts/layout_browser/applied/change/', data={'operation': 'remove_interface', 'id': applied['interfaces'][0]['id']}, headers=headers)
                        self.assertTrue(response.ok)
                    context.close()
            finally:
                browser.close()
        self.assertEqual(AccountLayoutApplication.objects.filter(account=self.owner).count(), 1)
