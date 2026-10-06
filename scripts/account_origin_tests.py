"""AccountPage actions use shared origin replacement, including native Pane coexistence."""
from pathlib import Path
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from accounts.tests_module_lists import seed
from scripts.browser_test_server import SharedSQLiteStaticFilesHandler
from events.models import Thread,ThreadPost,ThreadAccessRule


class AccountOriginBrowserTests(StaticLiveServerTestCase):
    static_handler=SharedSQLiteStaticFilesHandler
    def setUp(self):
        seed(self)
        self.thread=Thread.objects.create(creator=self.owner,title='Origin Thread')
        ThreadPost.objects.create(thread=self.thread,creator=self.owner,number=1,body='Origin Body')
        ThreadAccessRule.objects.bulk_create([ThreadAccessRule(thread=self.thread,capability=c,audience=a)
            for c in ['view','write'] for a in ['guest','account']])

    def context(self,browser,viewport,size):
        context=browser.new_context(viewport=size,is_mobile=viewport=='mobile',has_touch=viewport=='mobile')
        context.add_cookies([{'name':settings.SESSION_COOKIE_NAME,'value':self.client.cookies[settings.SESSION_COOKIE_NAME].value,'url':self.live_server_url}])
        return context

    def test_native_and_nested_actions_replace_after_account_origin_pc_mobile(self):
        from playwright.sync_api import sync_playwright,expect
        from scripts.browser_smoke import wait_for_trail_count
        output=Path(settings.BASE_DIR)/'.artifacts'/'account-origin';output.mkdir(parents=True,exist_ok=True)
        with sync_playwright() as pw:
            browser=pw.chromium.launch(channel='msedge',headless=True)
            try:
                for viewport,size in [('desktop',{'width':1280,'height':900}),('mobile',{'width':390,'height':844})]:
                    context=self.context(browser,viewport,size);page=context.new_page();page.set_default_timeout(10000);errors=[]
                    page.on('pageerror',lambda e:errors.append(str(e)))
                    page.on('console',lambda m:errors.append(m.text) if m.type=='error' and not m.location.get('url','').endswith('/favicon.ico') else None)
                    try:
                        for kind,stage in [('boards','board-list'),('people','people-list'),('modules','module-list'),('threads','list'),('responses','list'),('rooms','room-list'),('account-if','account-if-list')]:
                            with self.subTest(viewport=viewport,kind=kind):
                                page.goto(self.live_server_url+reverse('accounts:detail',args=[self.owner.username]))
                                origin=page.locator('.account-overview-pane');origin.evaluate('el=>{window.qaOrigin=el;el.dataset.qaOrigin="kept";}')
                                page.locator('.account-overview-pane [data-open-account-threads]').click()
                                page.locator('.account-thread-pane [data-thread-detail]').first.click()
                                reply=page.locator('.account-thread-detail-pane .thread-reply-form textarea');expect(reply).to_be_visible();reply.fill('Removed downstream input')
                                page.evaluate('url=>NiixyWorkspaceTrail.open(url,document.querySelector(".account-thread-detail-pane"))',reverse('accounts:detail',args=[self.other.username]))
                                wait_for_trail_count(page,1)
                                page.locator('.ui-workspace-trail-pane [data-open-account-modules]').click();wait_for_trail_count(page,2)
                                expect(page.locator('.ui-workspace-trail-pane [data-module-public]')).to_be_visible()
                                page.evaluate('() => {window.qaOldPanes=Array.from(document.querySelectorAll(".ui-workspace-trail-pane"));}')
                                selector='data-open-account-'+('account-if' if kind=='account-if' else kind)
                                page.locator('.account-overview-pane ['+selector+']').evaluate('el=>el.click()')
                                wait_for_trail_count(page,0)
                                expect(page.locator('.account-track')).to_have_attribute('data-ui-workspace-stage',stage)
                                self.assertTrue(page.evaluate('() => window.qaOldPanes.every(el=>!el.isConnected)'))
                                self.assertTrue(origin.evaluate('el=>el===window.qaOrigin && el.dataset.qaOrigin==="kept"'))
                                expect(page.locator('.account-thread-detail-pane .thread-reply-form textarea:visible')).to_have_count(0)
                                if kind in ['boards','people']:
                                    self.assertTrue(page.locator('[data-ui-feature-workspace=conversation]').evaluate('el=>el.hidden'))
                                    page.screenshot(path=str(output/(viewport+'-'+kind+'.png')),full_page=True)
                                    page.locator('.account-'+('board' if kind=='boards' else 'people')+'-list-pane .ui-pane-header .icon-button').click();wait_for_trail_count(page,0)
                                    expect(page.locator('.account-track')).to_have_attribute('data-ui-workspace-stage','overview')
                                    expect(page.locator('.account-thread-detail-pane .thread-reply-form textarea:visible')).to_have_count(0)
                                    self.assertTrue(origin.evaluate('el=>el===window.qaOrigin'))
                                    page.go_back();expect(page.locator('.account-track')).to_have_attribute('data-ui-workspace-stage',stage)
                                    wait_for_trail_count(page,0)
                                    expect(page.locator('.account-thread-detail-pane .thread-reply-form textarea:visible')).to_have_count(0)
                                    page.go_forward();expect(page.locator('.account-track')).to_have_attribute('data-ui-workspace-stage','overview')
                                    wait_for_trail_count(page,0)
                                elif kind=='modules':expect(page.locator('.profile-module-management [data-module-public]')).to_be_visible()
                        # Nested Account already uses a verified trail entry. Keep that origin too.
                        page.goto(self.live_server_url+reverse('accounts:detail',args=[self.owner.username]))
                        page.evaluate('url=>NiixyWorkspaceTrail.open(url,document.querySelector(".account-overview-pane"))',reverse('accounts:detail',args=[self.other.username]));wait_for_trail_count(page,1)
                        nested=page.locator('.ui-workspace-trail-pane [data-account-fragment]');nested.evaluate('el=>window.qaNestedOrigin=el')
                        for button in ['threads','people','boards','modules','responses','rooms','account-if']:
                            nested.locator('[data-open-account-'+button+']').evaluate('el=>el.click()');wait_for_trail_count(page,2)
                            self.assertTrue(nested.evaluate('el=>el===window.qaNestedOrigin'))
                            page.locator('.ui-workspace-trail-header .icon-button').last.click();wait_for_trail_count(page,1)
                        self.assertEqual(errors,[])
                    finally:context.close()
            finally:browser.close()

    def test_delayed_old_native_and_shared_responses_close_and_url_restore(self):
        from playwright.sync_api import sync_playwright,expect
        from scripts.browser_smoke import wait_for_trail_count
        with sync_playwright() as pw:
            browser=pw.chromium.launch(channel='msedge',headless=True)
            try:
                for viewport,size in [('desktop',{'width':1280,'height':900}),('mobile',{'width':390,'height':844})]:
                    with self.subTest(viewport=viewport):
                        context=self.context(browser,viewport,size);page=context.new_page();page.set_default_timeout(10000);errors=[]
                        page.on('pageerror',lambda e:errors.append(str(e)))
                        page.on('console',lambda m:errors.append(m.text) if m.type=='error' and not m.location.get('url','').endswith('/favicon.ico') else None)
                        try:
                            page.goto(self.live_server_url+reverse('accounts:detail',args=[self.owner.username]))
                            page.locator('[data-open-account-threads]').click()
                            # Fetch the real response, hold delivery to JS, then replace its origin.
                            page.evaluate('''id=>{window.qaFetch=fetch;window.fetch=(...args)=>window.qaFetch(...args).then(response=>{
                              if(String(args[0]).includes('/threads/'+id+'/')) return new Promise(resolve=>{window.qaHeld=true;window.qaRelease=()=>resolve(response);});
                              return response;
                            });}''',self.thread.pk)
                            page.locator('.account-thread-pane [data-thread-detail]').first.click();page.wait_for_function('window.qaHeld===true')
                            page.locator('.account-overview-pane [data-open-account-people]').evaluate('el=>el.click()');wait_for_trail_count(page,0)
                            page.evaluate('() => {window.qaRelease();window.fetch=window.qaFetch;}');page.wait_for_timeout(150)
                            expect(page.locator('[data-thread-detail-pane]')).to_have_count(0)
                            expect(page.locator('.account-track')).to_have_attribute('data-ui-workspace-stage','people-list')
                            page.locator('#close-account-people-list').click();wait_for_trail_count(page,0)
                            # Hold a shared Board response after receipt. Replacement aborts and disconnects it.
                            page.evaluate('''()=>{window.qaHeld=false;window.qaFetch=fetch;window.fetch=(...args)=>window.qaFetch(...args).then(response=>{
                              if(String(args[0]).endsWith('/boards/')) return new Promise(resolve=>{window.qaHeld=true;window.qaRelease=()=>resolve(response);});return response;
                            });}''')
                            page.locator('[data-open-account-boards]').click();page.wait_for_function('window.qaHeld===true')
                            page.evaluate('() => window.qaOldBoard=document.querySelector(".account-board-list-pane")')
                            page.locator('.account-overview-pane [data-open-account-people]').evaluate('el=>el.click()');wait_for_trail_count(page,0)
                            page.locator('#close-account-people-list').click();wait_for_trail_count(page,0)
                            page.evaluate('() => {window.qaRelease();window.fetch=window.qaFetch;}');page.wait_for_timeout(150)
                            self.assertTrue(page.evaluate('window.qaOldBoard.isConnected'));wait_for_trail_count(page,0)
                            expect(page.locator('.room-collection-browser')).to_have_count(0)
                            # Reopen the same legacy list while its old request is held.
                            # A new request generation must prevent the old response replacing it.
                            for action,container in [('threads','[data-thread-pane-container]'),('rooms','[data-account-room-list-container]')]:
                                page.goto(self.live_server_url+reverse('accounts:detail',args=[self.owner.username]))
                                path=page.locator('.account-thread-workspace' if action=='threads' else '.account-page').get_attribute('data-thread-pane-url' if action=='threads' else 'data-room-pane-url')
                                page.evaluate("""path=>{window.qaHeld=false;window.qaFetch=fetch;window.fetch=(...args)=>window.qaFetch(...args).then(response=>{
                                  if(!window.qaHeld && new URL(args[0],location.origin).pathname===path) return new Promise(resolve=>{window.qaHeld=true;window.qaRelease=()=>resolve(response);});return response;
                                });}""",path)
                                page.locator('[data-open-account-'+action+']').click();page.wait_for_function('window.qaHeld===true')
                                page.locator('.account-overview-pane [data-open-account-people]').evaluate('el=>el.click()');wait_for_trail_count(page,0)
                                page.locator('.account-overview-pane [data-open-account-'+action+']').evaluate('el=>el.click()');wait_for_trail_count(page,0)
                                expect(page.locator(container+' .ui-tabs')).to_be_visible()
                                page.locator(container).evaluate('el=>{const marker=document.createElement("span");marker.dataset.qaFreshResponse="kept";el.append(marker);}')
                                page.evaluate('() => {window.qaRelease();window.fetch=window.qaFetch;}');page.wait_for_timeout(150)
                                expect(page.locator(container+' [data-qa-fresh-response]')).to_have_count(1)
                            # Restoring both public origin URLs creates exactly one current Pane.
                            for pane in ['board','people']:
                                page.goto(self.live_server_url+reverse('accounts:detail',args=[self.owner.username])+'?pane='+pane)
                                wait_for_trail_count(page,0)
                                page.reload();wait_for_trail_count(page,0)
                                self.assertEqual(page.locator('.account-track').get_attribute('data-ui-workspace-stage'),pane+'-list')
                                self.assertTrue(page.locator('[data-ui-feature-workspace=conversation]').evaluate('el=>el.hidden'))
                                page.locator('#close-account-'+pane+'-list').click();wait_for_trail_count(page,0)
                                self.assertEqual(page.url,self.live_server_url+reverse('accounts:detail',args=[self.owner.username]))
                            self.assertEqual(errors,[])
                        finally:context.close()
            finally:browser.close()
