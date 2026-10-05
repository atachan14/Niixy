"""BoardList / InterfaceList and feedback, PC/mobile; isolated LiveServer + Edge."""
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from accounts.content_lists import route
from interfaces.models import InterfaceDraft, InterfaceList
from interfaces.services import publish_draft
from rooms.models import Board
from scripts.browser_test_server import SharedSQLiteStaticFilesHandler


class ContentListBrowserTests(StaticLiveServerTestCase):
    static_handler = SharedSQLiteStaticFilesHandler

    def setUp(self):
        from scripts.review_browser_tests import ReviewBrowserTests
        ReviewBrowserTests.setUp(self)
        self.board=Board.objects.get(placement__collection__account=self.target)
        self.own_board=Board.objects.get(placement__collection__account=self.author)
        self.board_list=self.author.collections.get(name='Main')
        draft=InterfaceDraft.objects.create(creator=self.target,kind='account',name='Browser公開IF',description='公開版だけを表示')
        self.interface,_=publish_draft(draft.pk)
        self.interface_list=InterfaceList.objects.create(owner=self.author,name='IF既存List',submission_id=uuid4())

    def test_lists_feedback_pc_mobile_and_smoke(self):
        from playwright.sync_api import sync_playwright,expect
        from scripts.browser_smoke import main as smoke_main,wait_for_trail_count
        output=Path(settings.BASE_DIR)/'.artifacts'/'content-lists';output.mkdir(parents=True,exist_ok=True)
        with sync_playwright() as pw:
            browser=pw.chromium.launch(channel='msedge',headless=True)
            try:
                for viewport,size in [('desktop',{'width':1280,'height':900}),('mobile',{'width':390,'height':844})]:
                    for kind,item,target in [('board',self.board_list,self.board),('interface',self.interface_list,self.interface)]:
                        context=browser.new_context(viewport=size,is_mobile=viewport=='mobile',has_touch=viewport=='mobile')
                        context.add_cookies([{'name':settings.SESSION_COOKIE_NAME,'value':self.client.cookies[settings.SESSION_COOKIE_NAME].value,'url':self.live_server_url}])
                        page=context.new_page();page.set_default_timeout(10000);errors=[]
                        page.on('pageerror',lambda e:errors.append(str(e)))
                        page.on('console',lambda m:errors.append(m.text) if m.type=='error' and not m.location.get('url','').endswith('/favicon.ico') else None)
                        try:
                            page.goto(self.live_server_url+route(kind,'page',target.pk))
                            base=1 if kind=='board' else 0
                            wait_for_trail_count(page,base)
                            feedback=page.locator('[data-content-feedback]').first
                            expect(feedback).to_be_visible()
                            # Click sets, switches, then clears without an introduction.
                            if feedback.get_attribute('data-content-sentiment'):
                                feedback.locator('[data-content-rate='+feedback.get_attribute('data-content-sentiment')+']').click()
                            feedback.locator('[data-content-rate=fav]').click();expect(feedback.locator('[data-content-rate=fav]')).to_have_attribute('aria-pressed','true')
                            feedback.locator('[data-content-rate=bad]').click();expect(feedback.locator('[data-content-rate=bad]')).to_have_attribute('aria-pressed','true')
                            expect(feedback.locator('[data-content-rate=fav]')).to_have_attribute('aria-pressed','false')
                            feedback.locator('[data-content-rate=bad]').click();expect(feedback.locator('[data-content-rate=bad]')).to_have_attribute('aria-pressed','false')
                            # Transport failure leaves the committed rating intact.
                            page.evaluate("() => {window.qaFetch=fetch;window.fetch=(...a)=>String(a[0]).endsWith('/rating/')?Promise.reject(new Error('評価通信失敗')):window.qaFetch(...a);}")
                            feedback.locator('[data-content-rate=fav]').click();expect(feedback.locator('.account-list-error')).to_have_text('評価通信失敗')
                            expect(feedback.locator('[data-content-rate=fav]')).to_have_attribute('aria-pressed','false')
                            page.evaluate('() => {window.fetch=window.qaFetch;}')
                            # Pending guard sends one desired-state POST for repeated submit.
                            page.evaluate("() => {window.qaFetch=fetch;window.ratingWrites=0;window.fetch=(...a)=>{if(!String(a[0]).endsWith('/rating/'))return window.qaFetch(...a);window.ratingWrites++;return new Promise(r=>setTimeout(r,200)).then(()=>window.qaFetch(...a));};}")
                            feedback.locator('[data-content-rating-form]').evaluate("f=>{const b=f.querySelector('[data-content-rate=fav]');f.requestSubmit(b);f.requestSubmit(b);}")
                            expect(feedback.locator('[data-content-rate=fav]')).to_have_attribute('aria-pressed','true');self.assertEqual(page.evaluate('window.ratingWrites'),1)
                            page.evaluate('() => {window.fetch=window.qaFetch;}')
                            feedback.locator('[data-content-count=fav]').click();wait_for_trail_count(page,base+1)
                            expect(page.locator('.account-list-content .account-summary')).to_have_count(1)
                            page.locator('.ui-workspace-trail-header .icon-button').last.click();wait_for_trail_count(page,base)
                            feedback.locator('[data-account-list-picker-url]').click();wait_for_trail_count(page,base+1)
                            picker=page.locator('[data-account-list-picker]');expect(picker).to_be_visible()
                            picker.locator('summary').click();expect(picker.locator('[data-list-share-url]')).to_have_value(self.live_server_url+route(kind,'page',target.pk))
                            picker.locator('[data-copy-list-url]').click();expect(picker.locator('[data-list-share-status]')).to_be_visible()
                            pick=picker.locator('[data-list-operation=pick]').filter(has_text='Main' if kind=='board' else 'IF既存List')
                            pick.locator('[type=submit]').click();expect(pick.locator('[data-list-success]')).to_have_text('追加しました。')
                            pick.locator('[type=submit]').click()
                            create=picker.locator('[data-list-operation=create]');create.locator('[name=name]').fill(kind+' 入力保持 '+viewport)
                            page.locator('.ui-workspace-trail-header .icon-button').last.click();wait_for_trail_count(page,base)
                            feedback.locator('[data-account-list-picker-url]').click();wait_for_trail_count(page,base+1)
                            expect(create.locator('[name=name]')).to_have_value(kind+' 入力保持 '+viewport)
                            page.evaluate("() => {window.qaFetch=fetch;window.fetch=(...a)=>String(a[0]).endsWith('-lists/create/')?Promise.reject(new Error('List通信失敗')):window.qaFetch(...a);}")
                            create.locator('[type=submit]').click();expect(create.locator('.account-list-error')).to_have_text('List通信失敗');expect(create.locator('[name=name]')).to_be_enabled()
                            page.evaluate('() => {window.fetch=window.qaFetch;}')
                            create.locator('[type=submit]').click();wait_for_trail_count(page,base+2)
                            detail=page.locator('[data-account-list-detail]');expect(detail.locator('[data-content-reference]')).to_have_count(1)
                            list_url=page.url
                            add=detail.locator('[data-list-operation=add]');add.locator('[name=target_url]').fill(self.live_server_url+route(kind,'page',target.pk))
                            # Nested content reuses original Policy and preserves the parent form.
                            detail.locator('[data-content-reference] .content-reference-summary').click();wait_for_trail_count(page,base+3)
                            child=page.locator('.ui-workspace-trail-pane').last
                            expect(child.locator('[data-content-feedback]')).to_be_visible()
                            child.locator('[data-content-rate=bad]').click()
                            expect(feedback.locator('[data-content-rate=bad]')).to_have_attribute('aria-pressed','true')
                            page.wait_for_timeout(300);page.screenshot(path=output/f'{viewport}-{kind}-workspace.png')
                            page.locator('.ui-workspace-trail-header .icon-button').last.click();wait_for_trail_count(page,base+2)
                            expect(add.locator('[name=target_url]')).to_have_value(self.live_server_url+route(kind,'page',target.pk))
                            add.locator('[type=submit]').click();expect(detail.locator('[data-content-reference]')).to_have_count(1)
                            expect(add.locator('[name=target_url]')).to_have_value('')
                            self.assertFalse(detail.evaluate('el=>el.scrollWidth>el.clientWidth+1'))
                            page.screenshot(path=output/f'{viewport}-{kind}-list.png')
                            # Rename then URL reload; owner forms and references remain accurate.
                            detail.locator('summary').filter(has_text='Listの管理').click()
                            detail.locator('[data-list-operation=rename] [name=name]').fill(kind+' 改名 '+viewport)
                            detail.locator('[data-list-operation=rename] [type=submit]').click()
                            expect(page.locator('.ui-workspace-trail-header h2').last).to_have_text(kind+' 改名 '+viewport)
                            page.reload();wait_for_trail_count(page,1);expect(detail.locator('[data-content-reference]')).to_have_count(1)
                            detail.locator('[data-list-operation=remove] [type=submit]').click();expect(detail.locator('[data-content-reference]')).to_have_count(0)
                            # Detached write finishes before a new form reopens.
                            add.locator('[name=target_url]').fill(self.live_server_url+route(kind,'page',target.pk))
                            page.evaluate("() => {window.qaFetch=fetch;window.fetch=(...a)=>String(a[0]).endsWith('/add/')?new Promise(r=>setTimeout(r,250)).then(()=>window.qaFetch(...a)):window.qaFetch(...a);}")
                            add.locator('[type=submit]').click();page.locator('.ui-workspace-trail-header .icon-button').last.click();wait_for_trail_count(page,0)
                            page.evaluate('(url)=>NiixyContentReferences.open(url,document.querySelector(".reference-origin"))',list_url)
                            wait_for_trail_count(page,1);expect(detail.locator('[data-content-reference]')).to_have_count(1)
                            page.evaluate('() => {window.fetch=window.qaFetch;}')
                            # Late content GET after Close cannot resurrect its Pane.
                            page.evaluate(r"() => {window.qaFetch=fetch;window.fetch=(...a)=>{if(!/\/(reference|pane)\/$/.test(String(a[0])))return window.qaFetch(...a);a[1]={...a[1],signal:undefined};return window.qaFetch(...a).then(r=>new Promise(done=>setTimeout(()=>done(r),250)));};}")
                            detail.locator('[data-content-reference] .content-reference-summary').click();page.locator('.ui-workspace-trail-header .icon-button').last.click();wait_for_trail_count(page,1)
                            page.wait_for_timeout(350);wait_for_trail_count(page,1);page.evaluate('() => {window.fetch=window.qaFetch;}')
                            context.clear_cookies();page.goto(list_url);wait_for_trail_count(page,1)
                            expect(detail.locator('[data-content-reference]')).to_have_count(1);expect(detail.locator('[data-account-list-form]')).to_have_count(0)
                            page.screenshot(path=output/f'{viewport}-{kind}-guest.png')
                            self.assertEqual(errors,[])
                        finally:context.close()
            finally:browser.close()
        with patch('sys.argv',['scripts/browser_smoke.py','--base-url',self.live_server_url,'--output-dir',str(Path(settings.BASE_DIR)/'.artifacts'/'browser-smoke')]):self.assertEqual(smoke_main(),0)

    def test_canonical_board_preserves_creation_and_thread_policy_pc_mobile(self):
        from playwright.sync_api import sync_playwright,expect
        from scripts.browser_smoke import wait_for_trail_count
        with sync_playwright() as pw:
            browser=pw.chromium.launch(channel='msedge',headless=True)
            try:
                for width in [1280,390]:
                    context=browser.new_context(viewport={'width':width,'height':900})
                    context.add_cookies([{'name':settings.SESSION_COOKIE_NAME,'value':self.client.cookies[settings.SESSION_COOKIE_NAME].value,'url':self.live_server_url}])
                    page=context.new_page();page.set_default_timeout(10000);errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                    try:
                        page.goto(self.live_server_url+route('board','page',self.own_board.pk));wait_for_trail_count(page,1)
                        page.locator('[data-board-create-toggle]').click()
                        form=page.locator('[data-board-thread-create]');form.locator('[name=title]').fill('Canonical Thread '+str(width));form.locator('[name=body]').fill('配置元の認可とThread Policy')
                        form.locator('[type=submit]').click();wait_for_trail_count(page,2)
                        expect(page.locator('.thread-detail')).to_contain_text('配置元の認可とThread Policy')
                        page.reload();wait_for_trail_count(page,2)
                        expect(page.locator('.thread-detail')).to_contain_text('配置元の認可とThread Policy')
                        page.locator('.ui-workspace-trail-header .icon-button').last.click();wait_for_trail_count(page,1)
                        expect(page.locator('[data-board-name]')).to_have_attribute('data-board-id',str(self.own_board.pk))
                        self.assertEqual(errors,[])
                    finally:context.close()
            finally:browser.close()
