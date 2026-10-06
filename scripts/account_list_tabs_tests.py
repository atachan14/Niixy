"""Current People navigation and scoped feature padding; isolated SQLite only."""
import json
from pathlib import Path
from uuid import uuid4
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import TestCase,Client
from django.urls import reverse
from accounts.content_lists import route
from accounts.models import AccountList,AccountListReference,AccountMute,AccountReview
from interfaces.models import InterfaceDraft
from interfaces.services import publish_draft
from scripts.browser_test_server import SharedSQLiteStaticFilesHandler
from scripts.nightly_qa_tests import seed
from events.models import Thread,ThreadPost,ThreadAccessRule


def setup(case):
    seed(case)
    case.second_list=AccountList.objects.create(owner=case.owner,name='Second People',submission_id=uuid4())
    case.own_interface,_=publish_draft(InterfaceDraft.objects.create(creator=case.owner,kind='thread',name='Own Published IF').pk)
    InterfaceDraft.objects.create(creator=case.owner,interface=case.own_interface,kind='thread',name='PRIVATE OWN DRAFT',description='PRIVATE OWN BODY')


class AccountListTabTests(TestCase):
    def setUp(self):setup(self)

    def test_people_inline_order_all_lists_and_existing_public_reviews(self):
        for index in range(23):AccountList.objects.create(owner=self.owner,name=f'People {index}',submission_id=uuid4())
        self.client.logout();response=self.client.get(reverse('accounts:list-index',args=[self.owner.username]));html=response.content.decode()
        self.assertLess(html.index('data-ui-tab="love"'),html.index('data-ui-tab="hate"'))
        self.assertLess(html.index('data-ui-tab="hate"'),html.index('data-ui-tab="list-'))
        self.assertEqual(len(response.context['people_lists']),25)
        self.assertContains(response,'People 22');self.assertContains(response,self.target.username)
        self.assertContains(response,'Review更新');self.assertContains(response,'追加 ')
        self.assertContains(response,reverse('accounts:list-page',args=[self.account_list.pk]))
        for absent in ['data-ui-tab="lists"','data-account-list-form','data-list-tab-url','PRIVATE OWN']:
            self.assertNotContains(response,absent)
        self.assertNotContains(response,route('interface','list-page',self.interface_list.pk))
        AccountMute.objects.create(muter=self.owner,muted_account=self.target)
        self.client.force_login(self.owner)
        self.assertNotContains(self.client.get(reverse('accounts:list-index',args=[self.owner.username])),self.target.username)
        self.assertTrue(self.account_list.references.filter(target=self.target).exists())
        self.assertTrue(AccountReview.objects.filter(author=self.owner,target=self.target).exists())

    def test_published_module_reads_do_not_write(self):
        from django.apps import apps
        models=[m for m in apps.get_models() if m._meta.app_label in {'accounts','interfaces','rooms'}]
        before={m:list(m.objects.order_by('pk').values()) for m in models};self.client.logout()
        for url in [route('interface','list-index',self.owner.username),reverse('accounts:module-pane',args=[self.owner.username]),reverse('accounts:list-index',args=[self.owner.username])]:
            response=self.client.get(url);self.assertEqual(response.status_code,200)
            self.assertNotContains(response,'PRIVATE OWN');self.assertNotContains(response,'data-account-list-form')
        for m,rows in before.items():self.assertEqual(list(m.objects.order_by('pk').values()),rows,m.__name__)

    def test_creation_remains_in_picker_and_owner_api_only(self):
        for user in [self.owner,self.target]:
            self.client.force_login(user)
            self.assertNotContains(self.client.get(reverse('accounts:list-index',args=[user.username])),'data-list-operation="create"')
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(reverse('accounts:list-picker',args=[self.target.username])),'data-list-operation="create"')
        response=self.client.post(reverse('accounts:list-create'),{'name':'Picker List','submission_id':uuid4(),'target_url':reverse('accounts:detail',args=[self.target.username])})
        self.assertEqual(response.status_code,201)
        self.assertTrue(AccountList.objects.get(pk=response.json()['list_id']).references.filter(target=self.target).exists())
        self.client.force_login(self.target)
        self.assertEqual(self.client.post(reverse('accounts:list-rename',args=[self.account_list.pk]),{'name':'Stolen'}).status_code,404)


class AccountListTabBrowserTests(StaticLiveServerTestCase):
    static_handler=SharedSQLiteStaticFilesHandler
    def setUp(self):setup(self)

    def test_pc_mobile_inline_lists_retained_input_and_stale_children(self):
        from playwright.sync_api import sync_playwright,expect
        from scripts.browser_smoke import wait_for_trail_count
        output=Path(settings.BASE_DIR)/'.artifacts'/'account-list-tabs';output.mkdir(parents=True,exist_ok=True)
        with sync_playwright() as pw:
            browser=pw.chromium.launch(channel='msedge',headless=True)
            try:
                for viewport,size in [('desktop',{'width':1280,'height':900}),('mobile',{'width':390,'height':844})]:
                    context=browser.new_context(viewport=size,is_mobile=viewport=='mobile',has_touch=viewport=='mobile')
                    context.add_cookies([{'name':settings.SESSION_COOKIE_NAME,'value':self.client.cookies[settings.SESSION_COOKIE_NAME].value,'url':self.live_server_url}])
                    page=context.new_page();errors=[]
                    page.on('pageerror',lambda e:errors.append(str(e)))
                    page.on('console',lambda m:errors.append(m.text) if m.type=='error' and not m.location.get('url','').endswith('/favicon.ico') else None)
                    try:
                        url=self.live_server_url+reverse('accounts:detail',args=[self.owner.username]);page.goto(url)
                        page.locator('[data-open-account-people]').click();wait_for_trail_count(page,0)
                        index=page.locator('[data-account-lists-index]');expect(index.locator('[role=tab]')).to_have_text(['Love','Hate','QA People','Second People'])
                        expect(index.locator('[data-ui-tab-panel=love]')).to_contain_text(self.target.username)
                        expect(index.locator('[data-list-operation=create]')).to_have_count(0)
                        tab=index.locator(f'[data-list-tab-id="{self.account_list.pk}"]');tab.click();wait_for_trail_count(page,0)
                        panel=index.locator(f'[data-ui-tab-panel="list-{self.account_list.pk}"]');expect(panel.locator('.account-summary')).to_have_count(1)
                        panel.locator('[data-people-list-detail]').click();wait_for_trail_count(page,1)
                        detail=page.locator('[data-account-list-detail]');add=detail.locator('[data-list-operation=add] [name=target_url]')
                        add.fill(url);detail.evaluate('el=>window.qaList=el')
                        detail.locator('.account-summary').first.click();wait_for_trail_count(page,2)
                        nested=page.locator('[data-account-fragment]');nested.locator('[data-open-account-people]').click();wait_for_trail_count(page,3)
                        nested.locator('[data-open-account-modules]').evaluate('el=>el.click()');wait_for_trail_count(page,3)
                        expect(page.locator('[data-module-public]')).to_have_count(1);expect(page.locator('[data-account-lists-index]')).to_have_count(1)
                        for count in (2,1):page.locator('.ui-workspace-trail-header .icon-button').last.click();wait_for_trail_count(page,count)
                        self.assertTrue(detail.evaluate('el=>el===window.qaList'));expect(add).to_have_value(url)
                        detail.locator('[data-list-operation=add] [type=submit]').click()
                        expect(detail.locator('.account-summary')).to_have_count(2);expect(panel.locator('.account-summary')).to_have_count(2)
                        detail.locator('summary').filter(has_text='Listの管理').click()
                        rename=detail.locator('[data-list-operation=rename]');rename.locator('[name=name]').fill('Renamed People')
                        rename.locator('[type=submit]').click();expect(tab).to_have_text('Renamed People')
                        page.locator('.ui-workspace-trail-header .icon-button').last.click();wait_for_trail_count(page,0)
                        # An inline fixed tab cancels a pending child without replacing this index.
                        index.evaluate('el=>window.qaIndex=el')
                        page.evaluate("""()=>{window.qaFetch=fetch;window.fetch=(...a)=>{if(!String(a[0]).includes('/pane/')||!String(a[0]).includes('lists/'))return window.qaFetch(...a);a[1]={...a[1],signal:undefined};return window.qaFetch(...a).then(r=>new Promise(resolve=>{window.qaRelease=()=>resolve(r);}));};}""")
                        panel.locator('[data-people-list-detail]').click();wait_for_trail_count(page,1);page.wait_for_function('typeof window.qaRelease==="function"')
                        index.locator('[data-ui-tab=hate]').evaluate('el=>el.click()');wait_for_trail_count(page,0)
                        page.evaluate('()=>{window.qaRelease();window.fetch=window.qaFetch;}');page.wait_for_timeout(150)
                        wait_for_trail_count(page,0);self.assertTrue(index.evaluate('el=>el===window.qaIndex'))
                        tab.click();page.screenshot(path=output/f'{viewport}-inline-list.png',full_page=True)
                        page.reload();expect(tab).to_have_attribute('aria-selected','true');wait_for_trail_count(page,0)
                        # Restore name for the next viewport, and retain direct shared List URLs.
                        csrf=page.locator('[name=csrfmiddlewaretoken]').first.input_value()
                        response=context.request.post(self.live_server_url+reverse('accounts:list-rename',args=[self.account_list.pk]),form={'name':'QA People'},headers={'X-CSRFToken':csrf});self.assertEqual(response.status,200)
                        response=context.request.post(self.live_server_url+reverse('accounts:list-add',args=[self.account_list.pk]),form={'target_url':url},headers={'X-CSRFToken':csrf});self.assertEqual(response.status,200)
                        ref_id=response.json()['reference_id']
                        response=context.request.post(self.live_server_url+reverse('accounts:list-remove',args=[self.account_list.pk,ref_id]),headers={'X-CSRFToken':csrf});self.assertEqual(response.status,200)
                        page.goto(self.live_server_url+reverse('accounts:list-page',args=[self.account_list.pk]));wait_for_trail_count(page,1)
                        expect(detail.locator('[data-list-operation=add]')).to_be_visible()
                        context.clear_cookies();page.reload();wait_for_trail_count(page,1)
                        expect(detail.locator('[data-account-list-form]')).to_have_count(0);self.assertEqual(errors,[])
                    finally:context.close()
            finally:browser.close()


class AccountFeatureLayoutTests(StaticLiveServerTestCase):
    static_handler=SharedSQLiteStaticFilesHandler
    def setUp(self):
        setup(self)
        thread=Thread.objects.create(creator=self.owner,title='Gutter Thread')
        ThreadPost.objects.create(thread=thread,creator=self.owner,number=1,body='Gutter body')
        ThreadAccessRule.objects.bulk_create([ThreadAccessRule(thread=thread,capability=c,audience=a) for c in ['view','write'] for a in ['guest','account']])

    def test_owner_other_guest_native_and_nested_layout_pc_mobile(self):
        from playwright.sync_api import sync_playwright,expect
        from scripts.browser_smoke import wait_for_trail_count
        output=Path(settings.BASE_DIR)/'.artifacts'/'account-feature-layout';output.mkdir(parents=True,exist_ok=True);rows=[]
        sessions={}
        for role,user in [('owner',self.owner),('other',self.target)]:
            client=Client();client.force_login(user);sessions[role]=client.cookies[settings.SESSION_COOKIE_NAME].value
        with sync_playwright() as pw:
            browser=pw.chromium.launch(channel='msedge',headless=True)
            try:
                for viewport,size in [('desktop',{'width':1280,'height':900}),('mobile',{'width':390,'height':844})]:
                    for role,user in [('owner',self.owner),('other',self.target),('guest',None)]:
                        context=browser.new_context(viewport=size,is_mobile=viewport=='mobile',has_touch=viewport=='mobile')
                        if user:
                            context.add_cookies([{'name':settings.SESSION_COOKIE_NAME,'value':sessions[role],'url':self.live_server_url}])
                        page=context.new_page();errors=[]
                        page.on('pageerror',lambda e:errors.append(str(e)))
                        page.on('console',lambda m:errors.append(m.text) if m.type=='error' and not m.location.get('url','').endswith('/favicon.ico') else None)
                        try:
                            for nested in [False,True]:
                                url=reverse('accounts:detail',args=[self.owner.username])
                                page.goto(self.live_server_url+('/' if nested else url))
                                if nested:
                                    page.evaluate('url=>NiixyWorkspaceTrail.open(url)',url);wait_for_trail_count(page,1)
                                    origin=page.locator('[data-account-fragment]')
                                else:origin=page.locator('.account-overview-pane')
                                for action in ['threads','account-if','people','modules']:
                                    origin.locator('[data-open-account-'+action+']').evaluate('el=>el.click()')
                                    if nested:wait_for_trail_count(page,2)
                                    expect(page.locator('.site-header')).to_contain_text(user.username) if user else expect(page.locator('.site-header')).to_contain_text('ログイン')
                                    content=page.locator('.account-feature-content:visible').last;expect(content).to_be_visible()
                                    expect(content.locator('[role=tab]')).not_to_have_count(0)
                                    if action=='modules':
                                        column=content.locator('[data-module-public-panel].is-active');expect(column).to_be_visible()
                                        expect(content.locator('[data-module-public-panel]:visible')).to_have_count(1)
                                        expect(content.locator('[role=tablist]:visible')).to_have_count(3)
                                        expect(content.locator('[data-module-subtypes]:visible')).to_have_count(1)
                                        self.assertEqual(content.evaluate('el=>el.closest(".ui-pane,.ui-workspace-trail-pane").querySelectorAll(".ui-pane-header").length'),1)
                                    else:column=content.locator('.ui-tab-panel.is-active')
                                    expected=16 if viewport=='mobile' else 20
                                    page.wait_for_timeout(350)
                                    metrics=column.evaluate('el=>{const title=el.querySelector(".ui-summary-item-title");return {padding:parseFloat(getComputedStyle(el).paddingLeft),titleGutter:title?title.getBoundingClientRect().left-el.getBoundingClientRect().left:null};}')
                                    self.assertEqual(metrics['padding'],expected,(viewport,role,nested,action,metrics))
                                    if action in ['threads','people']:self.assertAlmostEqual(metrics['titleGutter'],expected,delta=1)
                                    expect(content.locator('[data-list-operation=create]')).to_have_count(0)
                                    expect(content.locator('[data-reference-title="Board List管理"], [data-reference-title="Module List管理"]')).to_have_count(0)
                                    rows.append({'viewport':viewport,'viewer':role,'nested':nested,'feature':action,**metrics})
                                    self.assertAlmostEqual(content.evaluate('el=>el.closest(".ui-list-pane,.ui-workspace-trail-pane").getBoundingClientRect().right'),size['width'],delta=1)
                                    page.screenshot(path=output/f'{viewport}-{role}-{"nested" if nested else "native"}-{action}.png',full_page=True)
                                self.assertEqual(errors,[])
                        finally:context.close()
            finally:browser.close()
        (output/'metrics.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
