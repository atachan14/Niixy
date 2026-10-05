"""Interface action regressions against isolated SQLite only."""
from pathlib import Path
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from scripts.browser_test_server import SharedSQLiteStaticFilesHandler
from interfaces.models import Interface, InterfaceDraft
from interfaces.services import publish_draft


class InterfaceBrowserTests(StaticLiveServerTestCase):
    static_handler = SharedSQLiteStaticFilesHandler

    def setUp(self):
        self.assertEqual(settings.DATABASES['default']['ENGINE'], 'django.db.backends.sqlite3')
        self.owner = get_user_model().objects.create_user('interface_browser')
        self.client.force_login(self.owner)

    def run_action(self, action):
        from playwright.sync_api import sync_playwright, expect
        output = Path(settings.BASE_DIR) / '.artifacts' / 'interface-actions'
        output.mkdir(parents=True, exist_ok=True)
        saved_cases=[]
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True)
            try:
                for viewport, size in [('desktop', {'width':1280,'height':720}), ('mobile', {'width':390,'height':844})]:
                    for kind in ('account', 'thread', 'thread_post'):
                        with self.subTest(viewport=viewport, kind=kind, action=action):
                            context = browser.new_context(viewport=size, is_mobile=viewport=='mobile', has_touch=viewport=='mobile')
                            context.add_cookies([{'name':settings.SESSION_COOKIE_NAME,'value':self.client.cookies[settings.SESSION_COOKIE_NAME].value,'url':self.live_server_url}])
                            page=context.new_page();page.set_default_timeout(7000)
                            errors=[]
                            page.on('pageerror', lambda error: errors.append(str(error)))
                            responses=[]
                            page.on('response', lambda r: responses.append((r.url, r.status)) if '/drafts/' in r.url else None)
                            page.on('console', lambda msg: errors.append(msg.text) if msg.type=='error' and not msg.location.get('url','').endswith('/favicon.ico') else None)
                            try:
                                page.goto(f'{self.live_server_url}/mypage/?section=module&type=interface&subtype={kind}')
                                panel=page.locator('[data-module-panel="interface:self"]')
                                panel.locator('.module-create-action button').click()
                                page.locator('#interface-draft-form').wait_for()
                                name=f'{viewport}-{kind}-{action}'
                                page.locator('#id_name').fill(name)
                                page.locator('#id_description').fill('Preserved input')
                                button = page.locator(f'[form="interface-draft-form"][value="{action}"]')
                                if action == 'publish':
                                    button.evaluate('(button) => { button.form.requestSubmit(button); button.form.requestSubmit(button); }')
                                else:button.click()
                                expect(page.locator('.interface-detail-pane')).to_have_count(0)
                                collection='editing' if action=='save' else 'self'
                                expect(page.locator(f'[data-module-collection="{collection}"]')).to_have_attribute('aria-selected','true')
                                expect(page.locator(f'[data-module-panel="interface:{collection}"]')).to_contain_text(name)
                                self.assertNotIn('draft=',page.url)
                                saved_cases.append((name,kind))
                                page.reload();expect(page.locator(f'[data-module-collection="{collection}"]')).to_have_attribute('aria-selected','true')
                                page.locator('[data-close-module-list]').click()
                                self.assertEqual(errors,[])
                            except Exception:
                                print('DEBUG', page.url, errors, responses, page.locator('[data-interface-operation-message]').all_text_contents(), page.evaluate('moduleNavigationGeneration'), page.locator('#interface-draft-form').count())
                                raise
                            finally:
                                page.screenshot(path=output/f'{viewport}-{kind}-{action}.png',full_page=True)
                                context.close()
            finally:browser.close()

        for name,kind in saved_cases:
            if action=='save':self.assertTrue(InterfaceDraft.objects.filter(name=name,description='Preserved input',kind=kind).exists())
            else:
                self.assertFalse(InterfaceDraft.objects.filter(name=name).exists())
                self.assertTrue(Interface.objects.filter(name=name,kind=kind,current_version__version_number=1).exists())

    def test_save_closes_editor_to_editing_list(self):
        self.run_action('save')

    def test_publish_returns_to_owned_list(self):
        self.run_action('publish')

    def test_validation_network_failure_and_edit_publication(self):
        from playwright.sync_api import sync_playwright, expect
        output = Path(settings.BASE_DIR) / '.artifacts' / 'interface-actions'
        output.mkdir(parents=True, exist_ok=True)
        existing=InterfaceDraft.objects.create(creator=self.owner, kind='thread', name='Duplicate')
        publish_draft(existing.pk)
        edited_cases=[]
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(channel='msedge',headless=True)
            try:
                for viewport,size in [('desktop',{'width':1280,'height':720}),('mobile',{'width':390,'height':844})]:
                    for kind in ('account','thread','thread_post'):
                        with self.subTest(viewport=viewport,kind=kind):
                            context=browser.new_context(viewport=size,is_mobile=viewport=='mobile',has_touch=viewport=='mobile')
                            context.add_cookies([{'name':settings.SESSION_COOKIE_NAME,'value':self.client.cookies[settings.SESSION_COOKIE_NAME].value,'url':self.live_server_url}])
                            page=context.new_page();page.set_default_timeout(10000)
                            errors=[]
                            page.on('pageerror',lambda error:errors.append(str(error)))
                            page.on('console',lambda msg:errors.append(msg.text) if msg.type=='error' and not msg.location.get('url','').endswith('/favicon.ico') and not any(token in msg.text for token in ['400 (Bad Request)','net::ERR_FAILED']) else None)
                            try:
                                page.goto(f'{self.live_server_url}/mypage/?section=module&type=interface&subtype={kind}')
                                page.locator('[data-module-panel="interface:self"] .module-create-action button').click()
                                form=page.locator('#interface-draft-form');form.wait_for()
                                page.locator('#id_description').fill('Keep unsaved description')
                                for invalid_name in ['', 'Duplicate']:
                                    page.locator('#id_name').fill(invalid_name)
                                    page.locator('[form="interface-draft-form"][value="publish"]').click()
                                    expect(form.locator('[role="alert"]')).to_be_visible()
                                    expect(page.locator('#id_name')).to_have_value(invalid_name)
                                    expect(page.locator('#id_description')).to_have_value('Keep unsaved description')
                                    expect(page.locator('[value="publish"][form="interface-draft-form"]')).to_be_enabled()
                                name=f'Recovered-{viewport}-{kind}'
                                page.locator('#id_name').fill(name)
                                form.evaluate("el => { el.querySelector('[name=\"fields-TOTAL_FORMS\"]').value='1'; for (const [name,value] of [['definition_id','999999'],['field_id','']]) {const input=document.createElement('input');input.type='hidden';input.name='fields-0-'+name;input.value=value;el.append(input);} }")
                                page.locator('[form="interface-draft-form"][value="publish"]').click()
                                expect(form.locator('[role="alert"]')).to_be_visible()
                                expect(page.locator('#id_name')).to_have_value(name)
                                form.evaluate("el => {el.querySelector('[name=\"fields-TOTAL_FORMS\"]').value='0';el.querySelectorAll('[name^=\"fields-0-\"]').forEach(input=>input.remove());}")
                                page.route('**/interfaces/drafts/*/',lambda route:route.abort())
                                page.locator('[form="interface-draft-form"][value="publish"]').click()
                                expect(form.locator('[role="alert"]')).to_contain_text('通信')
                                expect(page.locator('#id_description')).to_have_value('Keep unsaved description')
                                expect(page.locator('[value="publish"][form="interface-draft-form"]')).to_be_enabled()
                                page.wait_for_timeout(350)
                                box=form.bounding_box()
                                self.assertGreaterEqual(box['x'], -1, page.evaluate('({scrollLeft:document.querySelector(".mypage-viewport").scrollLeft, scrollX, offset:workspace.style.getPropertyValue("--ui-workspace-offset")})'))
                                self.assertLessEqual(box['x']+box['width'],size['width']+1)
                                page.screenshot(path=output/f'{viewport}-{kind}-failure.png',full_page=True)
                                page.unroute('**/interfaces/drafts/*/')
                                page.locator('[form="interface-draft-form"][value="publish"]').click()
                                expect(page.locator('.interface-detail-pane')).to_have_count(0)
                                panel=page.locator('[data-module-panel="interface:self"]')
                                panel.locator('[data-detail-url]').filter(has_text=name).click()
                                page.locator('form[action$="/edit/"] button').click()
                                form=page.locator('#interface-draft-form');form.wait_for()
                                page.locator('#id_description').fill('Edited second version')
                                page.locator('[form="interface-draft-form"][value="save"]').click()
                                expect(page.locator('.interface-detail-pane')).to_have_count(0)
                                page.locator('[data-module-panel="interface:editing"] [data-detail-url]').filter(has_text=name).click()
                                expect(page.locator('#id_description')).to_have_value('Edited second version')
                                page.locator('[form="interface-draft-form"][value="publish"]').click()
                                expect(page.locator('.interface-detail-pane')).to_have_count(0)
                                edited_cases.append(name)
                                page.reload();expect(page.locator('[data-module-collection="self"]')).to_have_attribute('aria-selected','true')
                                page.locator('[data-module-panel="interface:self"] [data-detail-url]').filter(has_text=name).click()
                                page.locator('[data-close-interface-detail]').click()
                                expect(page.locator('.interface-detail-pane')).to_have_count(0)
                                self.assertEqual(errors,[])
                            finally:
                                page.screenshot(path=output/f'{viewport}-{kind}-edited.png',full_page=True)
                                context.close()
            finally:browser.close()

        for name in edited_cases:
            item=Interface.objects.get(name=name)
            self.assertEqual(item.current_version.version_number,2)
            self.assertEqual(item.current_version.description,'Edited second version')
            self.assertFalse(InterfaceDraft.objects.filter(interface=item).exists())

    def test_late_save_response_does_not_reopen_closed_editor(self):
        from playwright.sync_api import sync_playwright, expect
        drafts=[InterfaceDraft.objects.create(creator=self.owner,kind='thread',name=f'Late-{name}') for name in ('desktop','mobile')]
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(channel='msedge',headless=True)
            try:
                for name,size,draft in zip(('desktop','mobile'),({'width':1280,'height':720},{'width':390,'height':844}),drafts):
                    context=browser.new_context(viewport=size)
                    context.add_cookies([{'name':settings.SESSION_COOKIE_NAME,'value':self.client.cookies[settings.SESSION_COOKIE_NAME].value,'url':self.live_server_url}])
                    page=context.new_page()
                    errors=[]
                    page.on('pageerror',lambda error:errors.append(str(error)))
                    page.goto(f'{self.live_server_url}/mypage/?section=module&type=interface&subtype=thread&collection=editing&draft={draft.pk}')
                    page.locator('#interface-draft-form').wait_for()
                    page.locator('#id_description').fill('Late saved input')
                    def finish_after_close(route):
                        response=route.fetch()
                        page.locator('[data-close-interface-detail]').click()
                        route.fulfill(response=response)
                    page.route(f'**/interfaces/drafts/{draft.pk}/',finish_after_close)
                    page.locator('[form="interface-draft-form"][value="save"]').click()
                    expect(page.locator('.interface-detail-pane')).to_have_count(0)
                    page.wait_for_timeout(400)
                    self.assertEqual(page.locator('[data-interface-operation-message]').count(),0)
                    self.assertNotIn('draft=',page.url)
                    self.assertEqual(errors,[])
                    context.close()
            finally:browser.close()
        for draft in drafts:
            draft.refresh_from_db()
            self.assertEqual(draft.description,'Late saved input')
