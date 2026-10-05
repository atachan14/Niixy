"""AccountPage tab correction: isolated SQLite and local Edge only."""
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import TestCase
from django.urls import reverse

from accounts.content_lists import route
from accounts.models import AccountList
from interfaces.models import InterfaceDraft
from interfaces.services import publish_draft
from scripts.browser_test_server import SharedSQLiteStaticFilesHandler
from scripts.nightly_qa_tests import seed


def setup(case):
    seed(case)
    case.second_list = AccountList.objects.create(owner=case.owner, name='Second People', submission_id=uuid4())
    case.own_interface, _ = publish_draft(InterfaceDraft.objects.create(
        creator=case.owner, kind='thread', name='Own Published IF').pk)
    InterfaceDraft.objects.create(creator=case.owner, interface=case.own_interface,
        kind='thread', name='PRIVATE OWN DRAFT', description='PRIVATE OWN BODY')


class AccountListTabTests(TestCase):
    def setUp(self):
        setup(self)

    def test_people_preserves_fixed_tabs_and_real_list_links_for_guest(self):
        self.client.logout()
        response = self.client.get(reverse('accounts:list-index', args=[self.owner.username]))
        html = response.content.decode()
        self.assertLess(html.index('data-ui-tab="lists"'), html.index('data-ui-tab="list-'))
        self.assertLess(html.index('data-ui-tab="list-'), html.index('data-ui-tab="love"'))
        self.assertLess(html.index('data-ui-tab="love"'), html.index('data-ui-tab="hate"'))
        self.assertContains(response, 'QA People')
        self.assertContains(response, route('interface', 'list-page', self.interface_list.pk), count=0)
        self.assertNotContains(response, 'AccountListA')
        self.assertNotContains(response, 'data-account-list-form')
        self.assertContains(response, 'data-ui-tab-panel="love"><p class="empty">未実装')
        self.assertContains(response, 'data-ui-tab-panel="hate"><p class="empty">未実装')

    def test_interface_self_uses_published_versions_only_and_gets_do_not_write(self):
        from django.apps import apps
        models = [m for m in apps.get_models() if m._meta.app_label in {'accounts', 'interfaces', 'rooms'}]
        before = {m: list(m.objects.order_by('pk').values()) for m in models}
        self.client.logout()
        response = self.client.get(route('interface', 'list-index', self.owner.username))
        html = response.content.decode()
        self.assertLess(html.index('data-ui-tab="search"'), html.index('data-ui-tab="self"'))
        self.assertLess(html.index('data-ui-tab="self"'), html.index('data-ui-tab="lists"'))
        self.assertContains(response, 'Own Published IF')
        self.assertNotContains(response, 'PRIVATE OWN')
        self.assertNotContains(response, 'QA Public IF')
        self.assertNotContains(response, 'data-account-list-form')
        self.assertNotContains(response, 'data-ui-tab="editing"')
        self.assertContains(response, '選択したInterfaceの検索は今後実装予定です。')
        module = self.client.get(reverse('accounts:module-pane', args=[self.owner.username]))
        for kind in ['element', 'interface', 'layout']:
            self.assertContains(module, 'data-module-type="'+kind+'"')
        self.assertNotContains(module, 'PRIVATE OWN')
        self.client.get(reverse('accounts:list-index', args=[self.owner.username]))
        for model, rows in before.items():
            self.assertEqual(list(model.objects.order_by('pk').values()), rows, model.__name__)

    def test_empty_owner_can_create_and_nonowner_gets_no_create_form(self):
        for url in [reverse('accounts:list-index', args=[self.target.username]),
                    route('interface', 'list-index', self.target.username)]:
            self.assertNotContains(self.client.get(url), 'data-account-list-form')
        self.client.force_login(self.target)
        for url in [reverse('accounts:list-index', args=[self.target.username]),
                    route('interface', 'list-index', self.target.username)]:
            self.assertContains(self.client.get(url), 'data-list-operation="create"')


class AccountListTabBrowserTests(StaticLiveServerTestCase):
    static_handler = SharedSQLiteStaticFilesHandler

    def setUp(self):
        setup(self)

    def test_pc_mobile_tabs_lists_origin_retention_and_late_responses(self):
        from playwright.sync_api import sync_playwright, expect
        from scripts.browser_smoke import wait_for_trail_count
        output = Path(settings.BASE_DIR) / '.artifacts' / 'account-list-tabs'
        output.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='msedge', headless=True)
            try:
                for viewport, size in [('desktop', {'width':1280,'height':720}), ('mobile', {'width':390,'height':844})]:
                    for kind in ['account', 'interface']:
                        with self.subTest(viewport=viewport, kind=kind):
                            context = browser.new_context(viewport=size, is_mobile=viewport=='mobile', has_touch=viewport=='mobile')
                            context.add_cookies([{'name':settings.SESSION_COOKIE_NAME,
                                'value':self.client.cookies[settings.SESSION_COOKIE_NAME].value,'url':self.live_server_url}])
                            page = context.new_page()
                            page.set_default_timeout(10000)
                            errors = []
                            page.on('pageerror', lambda e:errors.append(str(e)))
                            page.on('console', lambda m:errors.append(m.text) if m.type=='error' and not m.location.get('url','').endswith('/favicon.ico') else None)
                            try:
                                page.goto(self.live_server_url+reverse('accounts:detail', args=[self.owner.username]))
                                if kind == 'account':
                                    page.locator('[data-open-account-people]').click()
                                    item = self.account_list
                                    tabs = ['AccountList','QA People','Second People','Love','Hate']
                                    detail_url = reverse('accounts:list-page',args=[item.pk])
                                    new_target = reverse('accounts:detail',args=[self.owner.username])
                                else:
                                    page.locator('[data-reference-title="InterfaceList一覧"]').click()
                                    item = self.interface_list
                                    tabs = ['検索','自作','保存済み','QA IFs']
                                    detail_url = route(kind,'list-page',item.pk)
                                    new_target = route(kind,'page',self.own_interface.pk)
                                wait_for_trail_count(page,1)
                                index = page.locator('[data-account-lists-index]')
                                expect(index.locator('[role=tab]')).to_have_text(tabs)
                                if kind == 'interface':
                                    expect(index.locator('[data-ui-tab-panel=self]')).to_contain_text('Own Published IF')
                                    expect(index).not_to_contain_text('PRIVATE OWN')
                                    index.locator('[data-ui-tab=search]').click()
                                    expect(index.locator('[data-ui-tab-panel=search]')).to_be_visible()
                                index.locator('[data-ui-tab=lists]').click()
                                create = index.locator('[data-list-operation=create]')
                                draft = kind+' pending '+viewport
                                create.locator('[name=name]').fill(draft)
                                index.evaluate('el=>{window.qaIndex=el;}')
                                # Name tab opens the existing List to the right. Fixed
                                # tab switches remove only children and retain draft DOM.
                                index.locator(f'[data-list-tab-id="{item.pk}"]').click()
                                wait_for_trail_count(page,2)
                                detail = page.locator('[data-account-list-detail]')
                                expect(detail).to_be_visible()
                                add = detail.locator('[data-list-operation=add]')
                                add.locator('[name=target_url]').fill(self.live_server_url+new_target)
                                add.locator('[type=submit]').click()
                                if kind == 'account':
                                    expect(detail.locator('[data-account-reference]')).to_have_count(2)
                                    expect(index.locator('[data-ui-tab-panel=lists] [data-list-count]').first).to_have_text('2')
                                else:
                                    expect(detail.locator('[data-content-reference]')).to_have_count(2)
                                    expect(index.locator('[data-ui-tab-panel=lists] [data-list-count]')).to_have_text('2')
                                page.locator('.ui-workspace-trail-header .icon-button').last.click()
                                wait_for_trail_count(page,1)
                                index.locator('[data-ui-tab=lists]').click()
                                expect(create.locator('[name=name]')).to_have_value(draft)
                                self.assertTrue(page.evaluate('window.qaIndex===document.querySelector("[data-account-lists-index]")'))
                                for tab in (['love','hate'] if kind=='account' else ['search','self']):
                                    index.locator(f'[data-ui-tab={tab}]').click()
                                    expect(index.locator(f'[data-ui-tab-panel={tab}]')).to_be_visible()
                                page.screenshot(path=output/f'{viewport}-{kind}-fixed.png')
                                # Hold a fetched response after ignoring its abort signal.
                                page.evaluate("""() => {window.qaFetch=fetch;window.fetch=(...a)=>{
                                  if(!String(a[0]).includes('/pane/') || !String(a[0]).includes('lists/'))return window.qaFetch(...a);
                                  a[1]={...a[1],signal:undefined};return window.qaFetch(...a).then(response=>new Promise(resolve=>{window.qaRelease=()=>resolve(response);}));};} """)
                                index.locator(f'[data-list-tab-id="{item.pk}"]').click()
                                wait_for_trail_count(page,2)
                                page.wait_for_function('typeof window.qaRelease==="function"')
                                index.locator('[data-ui-tab=lists]').evaluate('el=>el.click()')
                                wait_for_trail_count(page,1)
                                page.evaluate('() => {window.qaRelease();window.fetch=window.qaFetch;}')
                                page.wait_for_timeout(100)
                                wait_for_trail_count(page,1)
                                expect(detail).to_have_count(0)
                                expect(create.locator('[name=name]')).to_have_value(draft)
                                # Create remains connected; selected tab and draft guard
                                # survive the index refresh and new detail opening.
                                create.locator('[type=submit]').click()
                                wait_for_trail_count(page,2)
                                expect(index.locator('[data-list-tab-url]').last).to_have_text(draft)
                                page.locator('.ui-workspace-trail-header .icon-button').last.click()
                                wait_for_trail_count(page,1)
                                index.locator('[data-list-tab-url]').last.click()
                                wait_for_trail_count(page,2)
                                detail.locator('summary').filter(has_text='Listの管理').click()
                                detail.locator('[data-list-operation=rename] [name=name]').fill(draft+' renamed')
                                detail.locator('[data-list-operation=rename] [type=submit]').click()
                                expect(index.locator('[data-list-tab-url]').last).to_have_text(draft+' renamed')
                                expect(page.locator('.ui-workspace-trail-header h2').last).to_have_text(draft+' renamed')
                                # A saved detail refresh collapses its management details.
                                detail.locator('summary').filter(has_text='Listの管理').click()
                                page.once('dialog',lambda dialog:dialog.accept())
                                detail.locator('[data-list-operation=delete] [type=submit]').click()
                                wait_for_trail_count(page,1)
                                expect(index.locator('[data-list-tab-url]')).to_have_count(2 if kind=='account' else 1)
                                self.assertTrue(index.evaluate('''el => {
                                    const active=el.querySelector('[data-ui-tab][aria-selected=true]').getBoundingClientRect();
                                    const row=el.querySelector('[role=tablist]').getBoundingClientRect();
                                    return active.left >= row.left-1 && active.right <= row.right+1;
                                }'''))
                                # Existing List selected through the original summary link.
                                index.locator('[data-ui-tab-panel=lists] .account-list-summary').first.click()
                                wait_for_trail_count(page,2)
                                add = detail.locator('[data-list-operation=add]')
                                add.locator('[name=target_url]').fill(self.live_server_url+new_target)
                                if kind == 'account':
                                    detail.locator('.account-summary').first.click()
                                    wait_for_trail_count(page,3)
                                    nested = page.locator('[data-account-fragment]')
                                    nested.locator('[data-open-account-people]').click()
                                    wait_for_trail_count(page,4)
                                    child = page.locator('[data-account-lists-index]').last
                                    expect(child.locator('[data-ui-tab=love]')).to_be_visible()
                                    nested.locator('[data-reference-title="InterfaceList一覧"]').evaluate('el=>el.click()')
                                    wait_for_trail_count(page,4)
                                    expect(page.locator('[data-content-list-kind=interface][data-account-lists-index]')).to_have_count(1)
                                    expect(page.locator('[data-account-lists-index]')).to_have_count(2)
                                    page.locator('.ui-workspace-trail-header .icon-button').last.click()
                                    wait_for_trail_count(page,3)
                                    page.locator('.ui-workspace-trail-header .icon-button').last.click()
                                    wait_for_trail_count(page,2)
                                else:
                                    detail.locator('.content-reference-summary').first.click()
                                    wait_for_trail_count(page,3)
                                    expect(page.locator('[data-public-interface]')).to_be_visible()
                                    page.locator('.ui-workspace-trail-header .icon-button').last.click()
                                    wait_for_trail_count(page,2)
                                expect(add.locator('[name=target_url]')).to_have_value(self.live_server_url+new_target)
                                page.screenshot(path=output/f'{viewport}-{kind}-list.png')
                                # Reload canonical URL and read it as Guest. Authorization
                                # stays in existing API suites as well as this UI check.
                                page.goto(self.live_server_url+detail_url)
                                wait_for_trail_count(page,1)
                                expect(detail.locator('[data-list-operation=add]')).to_be_visible()
                                context.clear_cookies()
                                page.reload()
                                wait_for_trail_count(page,1)
                                expect(detail.locator('[data-account-list-form]')).to_have_count(0)
                                self.assertEqual(errors,[])
                            except Exception:
                                page.screenshot(path=output/f'{viewport}-{kind}-failure.png')
                                raise
                            finally:
                                context.close()
            finally:
                browser.close()
