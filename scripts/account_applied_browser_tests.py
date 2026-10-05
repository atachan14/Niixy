"""v0.12 Applied UI regression with isolated SQLite fixtures only."""
from pathlib import Path
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from interfaces.models import InterfaceDraft, InterfaceDraftField
from interfaces.services import publish_draft, publish_field_definition
from interfaces.account_applications import application_payload
from scripts.browser_test_server import SharedSQLiteStaticFilesHandler


class AccountAppliedBrowserTests(StaticLiveServerTestCase):
    static_handler = SharedSQLiteStaticFilesHandler

    def assert_pane_at_right(self, page, selector, viewport_width, workspace_width):
        page.wait_for_function("""({selector, width}) => {
          const pane = document.querySelector(selector);
          const viewport = document.querySelector('.mypage-viewport, .account-workspace');
          const track = document.querySelector('.mypage-workspace, .account-track');
          if (!pane || !viewport || !track || viewport.dataset.uiWorkspaceWidth !== width) return false;
          const rect = pane.getBoundingClientRect();
          const offset = parseFloat(track.style.getPropertyValue('--ui-workspace-offset')) || 0;
          const translation = new DOMMatrixReadOnly(getComputedStyle(track).transform).m41;
          return rect.width > 0 && rect.left >= -1
            && Math.abs(rect.right - window.innerWidth) <= 1
            && Math.abs(translation + offset) <= 1;
        }""", arg={'selector': selector, 'width': workspace_width})
        box = page.locator(selector).bounding_box()
        self.assertIsNotNone(box)
        self.assertAlmostEqual(box['x'] + box['width'], viewport_width, delta=1)

    def setUp(self):
        self.assertEqual(settings.DATABASES['default']['ENGINE'], 'django.db.backends.sqlite3')
        self.owner = get_user_model().objects.create_user('applied_browser')
        self.field, _ = publish_field_definition(creator=self.owner, name='Apply Text', field_type='short_text')
        number, _ = publish_field_definition(creator=self.owner, name='Apply Number', field_type='integer')
        draft = InterfaceDraft.objects.create(creator=self.owner, kind='account', name='Apply AccountIF')
        InterfaceDraftField.objects.create(draft=draft, definition=self.field, position=0, required=True)
        InterfaceDraftField.objects.create(draft=draft, definition=number, position=1)
        self.interface, _ = publish_draft(draft.pk)
        self.client.force_login(self.owner)

    def test_applied_add_edit_remove_public_tabs_pc_mobile(self):
        from playwright.sync_api import sync_playwright, expect
        output = Path(settings.BASE_DIR) / '.artifacts' / 'account-applied'
        output.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True)
            try:
                for viewport, size in [('desktop', {'width': 1280, 'height': 720}), ('mobile', {'width': 390, 'height': 844})]:
                    context = browser.new_context(viewport=size, is_mobile=viewport == 'mobile', has_touch=viewport == 'mobile')
                    context.add_cookies([{'name': settings.SESSION_COOKIE_NAME, 'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url': self.live_server_url}])
                    page = context.new_page(); page.set_default_timeout(7000); errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' and not msg.location.get('url', '').endswith('/favicon.ico') else None)
                    try:
                        page.goto(self.live_server_url + '/mypage/')
                        page.locator('#open-applied').click()
                        applied = page.locator('[data-applied-pane]')
                        expect(applied.locator('h2')).to_have_text('Applied一覧')
                        applied.locator('[data-add-applied="field"]').click()
                        listing = page.locator('.thread-field-list-pane')
                        listing.locator('.ui-tab-panel.is-active .ui-summary-item').filter(has_text='Apply Text@').click()
                        detail = page.locator('.thread-field-detail-pane')
                        detail.locator('.interface-implementation-editor input').fill('initial ' + viewport)
                        self.assert_pane_at_right(page, '.thread-field-detail-pane', size['width'], 'remaining')
                        detail.locator('.interface-detail-actions button').click()
                        expect(page.locator('.thread-create-module-selector-pane')).to_have_count(0)
                        field_item = applied.locator('[data-edit-applied-field]')
                        expect(field_item).to_contain_text('initial ' + viewport)
                        field_item.click()
                        editor = page.locator('[data-applied-editor]')
                        editor.locator('input').fill('edited ' + viewport)
                        editor.locator('[type="submit"]').click()
                        expect(page.locator('[data-applied-editor]')).to_have_count(0)
                        expect(field_item).to_contain_text('edited ' + viewport)
                        applied.locator('[data-ui-tab="applied-interface"]').click()
                        applied.locator('[data-add-applied="interface"]').click()
                        page.locator('.thread-create-module-list-pane .ui-tab-panel.is-active .ui-summary-item').filter(has_text='Apply AccountIF@').click()
                        detail = page.locator('.thread-create-module-detail-pane')
                        expect(detail.locator('h2')).to_have_text('AccountIF詳細')
                        detail.locator('.interface-implementation-editor input').nth(0).fill('edited ' + viewport)
                        detail.locator('.interface-implementation-editor input').nth(1).fill('42')
                        detail.locator('.interface-detail-actions button').click()
                        expect(page.locator('.thread-create-module-selector-pane')).to_have_count(0)
                        applied.locator('[data-ui-tab="applied-interface"]').click()
                        expect(applied.locator('[data-edit-applied-interface]')).to_contain_text('edited ' + viewport)
                        self.assert_pane_at_right(page, '[data-applied-pane]', size['width'], 'fixed')
                        page.screenshot(path=output / f'{viewport}-mypage.png', full_page=True)
                        applied.locator('[data-ui-tab="applied-field"]').click()
                        expect(applied.locator('[data-edit-applied-field]')).to_have_count(2)
                        expect(applied.locator('[data-edit-applied-field]').first).to_contain_text('Apply Number')
                        context.clear_cookies()
                        page.goto(self.live_server_url + '/accounts/applied_browser/')
                        page.locator('[data-open-account-account-if]').click()
                        public = page.locator('[data-account-applied-container]')
                        expect(public.locator('[data-ui-tab-panel="applied-field"] .ui-summary-item')).to_have_count(2)
                        expect(public).to_contain_text('最終更新')
                        expect(public.locator('[data-edit-applied-field]')).to_have_count(0)
                        public.locator('[data-ui-tab="applied-interface"]').click()
                        expect(public).to_contain_text('Apply AccountIF')
                        page.wait_for_function("""() => {
                          const pane = document.querySelector('#account-if-list-pane');
                          return pane && Math.abs(pane.getBoundingClientRect().right - window.innerWidth) <= 1;
                        }""")
                        public_box = page.locator('#account-if-list-pane').bounding_box()
                        self.assertAlmostEqual(public_box['x'] + public_box['width'], size['width'], delta=1)
                        page.screenshot(path=output / f'{viewport}-public.png', full_page=True)
                        page.locator('#close-account-if-list').click()
                        page.locator('[data-open-account-modules]').click()
                        expect(page.locator('.profile-module-list-pane')).to_be_visible()
                        context.add_cookies([{'name': settings.SESSION_COOKIE_NAME, 'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url': self.live_server_url}])
                        page.goto(self.live_server_url + '/mypage/?section=applied')
                        applied = page.locator('[data-applied-pane]')
                        applied.locator('[data-edit-applied-field]').filter(has_text='Apply Text@').click()
                        editor = page.locator('[data-applied-editor]')
                        expect(editor.locator('.field-help')).to_have_text('Apply AccountIFと共有されています。')
                        self.assert_pane_at_right(page, '[data-applied-editor]', size['width'], 'remaining')
                        page.screenshot(path=output / f'{viewport}-shared-editor.png', full_page=True)
                        page.locator('[data-applied-editor]').get_by_text('取り外す', exact=True).click()
                        expect(applied.locator('[data-edit-applied-field]')).to_have_count(2)  # IF reference survives.
                        applied.locator('[data-ui-tab="applied-interface"]').click()
                        applied.locator('[data-edit-applied-interface]').click()
                        page.locator('[data-applied-editor]').get_by_text('取り外す', exact=True).click()
                        applied.locator('[data-ui-tab="applied-field"]').click()
                        expect(applied.locator('[data-edit-applied-field]')).to_have_count(0)
                        self.assertEqual(errors, [])
                    finally:
                        page.screenshot(path=output / f'{viewport}-final.png', full_page=True)
                        context.close()
            finally: browser.close()
        self.assertEqual(application_payload(self.owner)['fields'], [])

    def test_empty_account_if_disables_save_but_allows_removal(self):
        from playwright.sync_api import sync_playwright, expect
        from interfaces.account_applications import change_application

        draft = InterfaceDraft.objects.create(creator=self.owner, kind='account', name='Empty AccountIF')
        empty_if, _ = publish_draft(draft.pk)
        change_application(self.owner, {'operation': 'add_interface', 'id': empty_if.pk, 'values': {}})
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True)
            context = browser.new_context(viewport={'width': 1280, 'height': 720})
            context.add_cookies([{'name': settings.SESSION_COOKIE_NAME,
                'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url': self.live_server_url}])
            page = context.new_page()
            try:
                page.goto(self.live_server_url + '/mypage/?section=applied')
                applied = page.locator('[data-applied-pane]')
                applied.locator('[data-ui-tab="applied-interface"]').click()
                applied.locator('[data-edit-applied-interface]').filter(has_text='Empty AccountIF@').click()
                editor = page.locator('[data-applied-editor]')
                self.assert_pane_at_right(page, '[data-applied-editor]', 1280, 'remaining')
                expect(editor.locator('[type="submit"]')).to_be_disabled()
                remove = editor.get_by_text('取り外す', exact=True)
                expect(remove).to_be_enabled()
                remove.click()
                expect(applied.locator('[data-edit-applied-interface]')).to_have_count(0)
            finally:
                context.close()
                browser.close()

    def test_merge_preview_requires_user_confirm_and_late_response_cannot_reopen(self):
        from playwright.sync_api import sync_playwright, expect
        from interfaces.account_applications import change_application
        second, _ = publish_field_definition(creator=self.owner, name='Other Text', field_type='short_text')
        bridge, _ = publish_field_definition(creator=self.owner, name='Merge Bridge', field_type='short_text',
            synonym_target_ids=[self.field.pk, second.pk])
        change_application(self.owner, {'operation': 'add_field', 'id': self.field.pk, 'values': {str(self.field.key): ['first']}})
        change_application(self.owner, {'operation': 'add_field', 'id': second.pk, 'values': {str(second.key): ['second']}})
        output = Path(settings.BASE_DIR) / '.artifacts' / 'account-applied'
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True)
            context = browser.new_context(viewport={'width': 1280, 'height': 720})
            context.add_cookies([{'name': settings.SESSION_COOKIE_NAME, 'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url': self.live_server_url}])
            page = context.new_page(); page.set_default_timeout(7000)
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' and not msg.location.get('url', '').endswith('/favicon.ico') else None)
            try:
                page.goto(self.live_server_url + '/mypage/?section=applied')
                page.locator('[data-add-applied="field"]').click()
                page.locator('.thread-field-list-pane .ui-tab-panel.is-active .ui-summary-item').filter(has_text='Merge Bridge@').click()
                detail = page.locator('.thread-field-detail-pane')
                detail.locator('.interface-implementation-editor input').fill('incoming')
                detail.locator('.interface-detail-actions > button').click()
                preview = detail.locator('[data-merge-preview]')
                expect(preview).to_contain_text('second')
                expect(preview).to_contain_text('first')
                expect(detail.locator('.interface-implementation-editor input')).to_have_value('incoming')
                page.screenshot(path=output / 'desktop-merge-preview.png', full_page=True)
                preview.get_by_text('確認して保存', exact=True).click()
                expect(page.locator('.thread-create-module-selector-pane')).to_have_count(0)
                expect(page.locator('[data-edit-applied-field]')).to_have_count(3)
                for field in page.locator('[data-edit-applied-field]').all(): expect(field).to_contain_text('first')
                page.locator('[data-edit-applied-field]').first.click()
                page.locator('[data-applied-editor] input').fill('late')
                page.evaluate("""() => { const original = window.fetch;
                  window.fetch = async (...args) => {
                    const response = await original(...args);
                    if (String(args[0]).includes('/applied/change/')) await new Promise(resolve => setTimeout(resolve, 600));
                    return response;
                  };
                }""")
                page.locator('[data-applied-editor] [type="submit"]').click()
                page.locator('#mypage-identity').click()
                page.wait_for_timeout(800)
                expect(page.locator('[data-applied-pane]')).to_have_count(0)
                expect(page.locator('[data-applied-editor]')).to_have_count(0)
                self.assertEqual(errors, [])
            finally:
                context.close(); browser.close()
        self.assertEqual({item['value'] for item in application_payload(self.owner)['fields']}, {'late'})

    def test_latest_edit_freeze_and_pending_recovery_pc_mobile(self):
        from playwright.sync_api import sync_playwright, expect
        from interfaces.account_applications import change_application
        output = Path(settings.BASE_DIR) / '.artifacts' / 'account-versions'
        output.mkdir(parents=True, exist_ok=True)
        for name, size in [('desktop', {'width': 1280, 'height': 720}), ('mobile', {'width': 390, 'height': 844})]:
            field, _ = publish_field_definition(creator=self.owner, name='Version Choice ' + name,
                field_type='single_choice', settings={'options': ['old']})
            interfaces = []
            for prefix in ['Frozen IF ', 'Ready IF ']:
                draft = InterfaceDraft.objects.create(creator=self.owner, kind='account', name=prefix + name)
                InterfaceDraftField.objects.create(draft=draft, definition=field, position=0, required=True)
                interface, _ = publish_draft(draft.pk); interfaces.append(interface)
                change_application(self.owner, {'operation': 'add_interface', 'id': interface.pk,
                    'values': {str(field.key): ['old']}})
            frozen, ready = interfaces
            publish_field_definition(creator=self.owner, definition=field, name=field.name,
                field_type='single_choice', settings={'options': ['new']})
            extra, _ = publish_field_definition(creator=self.owner, name='Extra ' + name, field_type='integer')
            draft = InterfaceDraft.objects.create(creator=self.owner, interface=ready, kind='account', name=ready.name)
            InterfaceDraftField.objects.create(draft=draft, definition=field, position=0, required=True)
            InterfaceDraftField.objects.create(draft=draft, definition=extra, position=1, required=True)
            publish_draft(draft.pk)
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel='msedge', headless=True)
                context = browser.new_context(viewport=size, is_mobile=name == 'mobile', has_touch=name == 'mobile')
                context.add_cookies([{'name': settings.SESSION_COOKIE_NAME,
                    'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url': self.live_server_url}])
                page = context.new_page(); page.set_default_timeout(8000); errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.on('console', lambda message: errors.append(message.text) if message.type == 'error'
                    and not message.location.get('url', '').endswith('/favicon.ico') else None)
                try:
                    page.goto(self.live_server_url + '/mypage/?section=applied')
                    applied = page.locator('[data-applied-pane]')
                    applied.locator('[data-ui-tab="applied-interface"]').click()
                    expect(applied.locator('[data-application-state="frozen"]')).to_have_count(1)
                    applied.locator('[data-edit-applied-interface]').filter(has_text=frozen.name).click()
                    editor = page.locator('[data-applied-editor]')
                    expect(editor.locator('[type="submit"]')).to_be_disabled()
                    expect(editor.locator('select')).to_be_disabled()
                    editor.locator('.ui-pane-header button').click()
                    applied.locator('[data-ui-tab="applied-field"]').click()
                    applied.locator('[data-edit-applied-field]').click()
                    editor = page.locator('[data-applied-editor]')
                    editor.locator('select').select_option('new')
                    editor.locator('[type="submit"]').click()
                    expect(editor.locator('[data-merge-preview]')).to_contain_text('old')
                    before = page.request.get(self.live_server_url + '/accounts/applied_browser/applied/data/').json()
                    self.assertEqual(before['fields'][0]['value'], 'old')
                    self.assert_pane_at_right(page, '[data-applied-editor]', size['width'], 'remaining')
                    self.assertTrue(editor.locator('form').evaluate('el => el.scrollWidth <= el.clientWidth + 1'))
                    self.assertNotIn('definition_id', editor.locator('[data-merge-preview]').inner_text())
                    page.screenshot(path=output / f'{name}-field-preview.png', full_page=True)
                    editor.locator('[data-merge-preview] button').click()
                    expect(page.locator('[data-applied-editor]')).to_have_count(0)
                    expect(applied.locator('[data-edit-applied-field]')).to_contain_text('new')
                    applied.locator('[data-ui-tab="applied-interface"]').click()
                    expect(applied.locator('[data-application-state="pending"]')).to_have_count(1)
                    applied.locator('[data-edit-applied-interface]').filter(has_text=ready.name).click()
                    editor = page.locator('[data-applied-editor]')
                    expect(editor.locator('select')).to_have_value('new')
                    editor.locator('input[type="number"]').fill('12')
                    editor.locator('[type="submit"]').click()
                    expect(editor.locator('[data-merge-preview]')).to_contain_text('Extra')
                    before = page.request.get(self.live_server_url + '/accounts/applied_browser/applied/data/').json()
                    self.assertEqual(len(before['fields']), 1)
                    self.assertTrue(editor.locator('form').evaluate('el => el.scrollWidth <= el.clientWidth + 1'))
                    page.screenshot(path=output / f'{name}-recovery-preview.png', full_page=True)
                    editor.locator('[data-merge-preview] button').click()
                    expect(page.locator('[data-applied-editor]')).to_have_count(0)
                    applied.locator('[data-ui-tab="applied-interface"]').click()
                    expect(applied.locator('[data-application-state="active"]')).to_have_count(1)
                    context.clear_cookies()
                    page.goto(self.live_server_url + '/accounts/applied_browser/')
                    page.locator('[data-open-account-account-if]').click()
                    public = page.locator('[data-account-applied-container]')
                    public.locator('[data-ui-tab="applied-interface"]').click()
                    expect(public.locator('[data-application-state="active"]')).to_have_count(1)
                    expect(public.locator('[data-application-state="frozen"]')).to_have_count(1)
                    expect(public).to_contain_text('new'); expect(public).to_contain_text('12')
                    page.screenshot(path=output / f'{name}-public.png', full_page=True)
                    self.assertEqual(errors, [])
                finally:
                    context.close(); browser.close()
            for interface in interfaces:
                item = self.owner.interface_implementations.get(interface=interface)
                change_application(self.owner, {'operation': 'remove_interface', 'id': item.pk})
