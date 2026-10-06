"""Account feature buttons share stage, Current, motion, Close and history contracts."""
import json
import os
from pathlib import Path
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from accounts.tests_module_lists import seed
from scripts.browser_test_server import SharedSQLiteStaticFilesHandler


class AccountFeatureSwitchTests(StaticLiveServerTestCase):
    static_handler=SharedSQLiteStaticFilesHandler

    def setUp(self):
        seed(self)
        assert settings.DATABASES['default']['ENGINE']=='django.db.backends.sqlite3'
        assert settings.DATABASES['default']['NAME']==':memory:' or 'mode=memory' in settings.DATABASES['default']['NAME']

    def context(self,browser,viewport,size):
        context=browser.new_context(viewport=size,is_mobile=viewport=='mobile',has_touch=viewport=='mobile')
        context.add_cookies([{'name':settings.SESSION_COOKIE_NAME,'value':self.client.cookies[settings.SESSION_COOKIE_NAME].value,'url':self.live_server_url}])
        return context

    def test_buttons_share_stage_current_history_and_no_overview_bounce(self):
        from playwright.sync_api import sync_playwright,expect
        phase=os.environ.get('NIIXY_FEATURE_QA_PHASE','after')
        output=Path(settings.BASE_DIR)/'.artifacts'/'account-feature-switch'/phase
        output.mkdir(parents=True,exist_ok=True)
        rows=[];failures=[]
        with sync_playwright() as pw:
            browser=pw.chromium.launch(channel='msedge',headless=True)
            try:
                for viewport,size in [('desktop',{'width':1280,'height':900}),('mobile',{'width':390,'height':844})]:
                    context=self.context(browser,viewport,size);page=context.new_page();errors=[]
                    page.on('pageerror',lambda e:errors.append(str(e)))
                    page.on('console',lambda m:errors.append(m.text) if m.type=='error' and not m.location.get('url','').endswith('/favicon.ico') else None)
                    try:
                        for action,stage in [('responses','list'),('modules','module-list'),('boards','board-list'),('people','people-list')]:
                            page.goto(self.live_server_url+reverse('accounts:detail',args=[self.owner.username]))
                            page.locator('[data-open-account-threads]').click()
                            expect(page.locator('[data-thread-pane-container] .ui-tabs')).to_be_visible()
                            page.wait_for_timeout(300)
                            page.evaluate('''()=>{const track=document.querySelector('.account-track');
                              window.qaBeforeOffset=track.style.getPropertyValue('--ui-workspace-offset');window.qaHistory=[];
                              for(const action of ['pushState','replaceState']){const original=history[action].bind(history);history[action]=(...args)=>{window.qaHistory.push(action);return original(...args);};}
                            }''')
                            row=page.locator('.account-overview-pane [data-open-account-'+action+']').evaluate('''(el,expected)=>{
                              el.click();const track=document.querySelector('.account-track');return {expected,
                                stage:track.niixyWorkspace.stage,identityDisabled:document.querySelector('#account-page-identity').disabled,
                                beforeOffset:window.qaBeforeOffset,immediateOffset:track.style.getPropertyValue('--ui-workspace-offset'),
                                history:window.qaHistory.slice()};}''',stage)
                            row.update(viewport=viewport,action=action);rows.append(row)
                            if row['stage']!=stage or row['identityDisabled'] or row['beforeOffset']!=row['immediateOffset'] or row['history'].count('pushState')!=1:
                                failures.append(row)
                            page.wait_for_timeout(350)
                            page.screenshot(path=str(output/(viewport+'-'+action+'.png')),full_page=True)
                        self.assertEqual(errors,[])
                    finally:context.close()
            finally:browser.close()
        (output/'comparison.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
        self.assertEqual(failures,[],json.dumps(failures,ensure_ascii=False))

    def test_interrupted_close_reopen_mutual_switch_and_history(self):
        from playwright.sync_api import sync_playwright,expect
        from scripts.browser_smoke import wait_for_trail_count
        with sync_playwright() as pw:
            browser=pw.chromium.launch(channel='msedge',headless=True)
            try:
                for viewport,size in [('desktop',{'width':1280,'height':900}),('mobile',{'width':390,'height':844})]:
                    context=self.context(browser,viewport,size);page=context.new_page();errors=[]
                    page.on('pageerror',lambda e:errors.append(str(e)))
                    page.on('console',lambda m:errors.append(m.text) if m.type=='error' and not m.location.get('url','').endswith('/favicon.ico') else None)
                    try:
                        url=self.live_server_url+reverse('accounts:detail',args=[self.owner.username])
                        for action,stage,selector in [('boards','board-list','.account-board-list-pane'),('people','people-list','.account-people-list-pane')]:
                            page.goto(url);origin=page.locator('.account-overview-pane');origin.evaluate('el=>window.qaFeatureOrigin=el')
                            # Reopen while closing transition runs. Use the real click handler without coordinate waiting.
                            origin.locator('[data-open-account-'+action+']').click()
                            expect(page.locator(selector+' .ui-tabs')).to_be_visible()
                            page.locator('#account-page-identity').click()
                            origin.locator('[data-open-account-'+action+']').evaluate('el=>el.click()')
                            expect(page.locator('.account-track')).to_have_attribute('data-ui-workspace-stage',stage)
                            expect(page.locator('#account-page-identity')).to_be_enabled()
                            # Reclick same root action while opening, then switch through every existing feature.
                            origin.locator('[data-open-account-'+action+']').evaluate('el=>el.click()')
                            for other,other_stage in [('threads','list'),('responses','list'),('rooms','room-list'),('account-if','account-if-list'),('modules','module-list')]:
                                origin.locator('[data-open-account-'+other+']').evaluate('el=>el.click()')
                                origin.locator('[data-open-account-'+action+']').evaluate('el=>el.click()')
                                expect(page.locator('.account-track')).to_have_attribute('data-ui-workspace-stage',stage)
                                wait_for_trail_count(page,0)
                            expect(page.locator(selector+' .ui-tabs')).to_be_visible()
                            page.wait_for_timeout(350)
                            geometry=page.locator(selector).evaluate('el=>({right:el.getBoundingClientRect().right,width:el.getBoundingClientRect().width,scroll:document.querySelector(".account-workspace").scrollLeft})')
                            self.assertAlmostEqual(geometry['right'],size['width'],delta=1)
                            self.assertEqual(geometry['scroll'],0)
                            self.assertTrue(origin.evaluate('el=>el===window.qaFeatureOrigin'))
                            page.locator(selector+' .ui-pane-header .icon-button').click()
                            expect(page.locator('.account-track')).to_have_attribute('data-ui-workspace-stage','overview')
                            page.go_back();expect(page.locator('.account-track')).to_have_attribute('data-ui-workspace-stage',stage)
                            page.go_forward();expect(page.locator('.account-track')).to_have_attribute('data-ui-workspace-stage','overview')
                            page.goto(url+'?pane='+('board' if action=='boards' else 'people'))
                            expect(page.locator('.account-track')).to_have_attribute('data-ui-workspace-stage',stage)
                            page.reload();expect(page.locator('.account-track')).to_have_attribute('data-ui-workspace-stage',stage)
                            wait_for_trail_count(page,0)
                            page.locator('#account-page-identity').click();self.assertEqual(page.url,url)
                        self.assertEqual(errors,[])
                    finally:context.close()
            finally:browser.close()

    def test_native_open_close_animation_matches_thread_pc_mobile(self):
        from playwright.sync_api import sync_playwright,expect
        samples=[]
        with sync_playwright() as pw:
            browser=pw.chromium.launch(channel='msedge',headless=True)
            try:
                for viewport,size in [('desktop',{'width':1280,'height':900}),('mobile',{'width':390,'height':844})]:
                    context=self.context(browser,viewport,size);page=context.new_page()
                    try:
                        for action in ['threads','boards','people']:
                            page.goto(self.live_server_url+reverse('accounts:detail',args=[self.owner.username]))
                            for control,opening in [(page.locator('[data-open-account-'+action+']'),True),(page.locator('#account-page-identity'),False)]:
                                motion=control.evaluate("""async el=>{
                                  const track=document.querySelector('.account-track'),events=[],values=[];
                                  const listener=e=>{if(e.target===track&&e.propertyName==='transform')events.push(e.type);};
                                  track.addEventListener('transitionrun',listener);track.addEventListener('transitionend',listener);
                                  const x=()=>new DOMMatrixReadOnly(getComputedStyle(track).transform).m41;
                                  const before=x();el.click();const start=performance.now();
                                  await new Promise(resolve=>{const frame=now=>{values.push(x());if(now-start<420)requestAnimationFrame(frame);else resolve();};requestAnimationFrame(frame);});
                                  track.removeEventListener('transitionrun',listener);track.removeEventListener('transitionend',listener);
                                  return {before,after:x(),values,events,scroll:document.querySelector('.account-workspace').scrollLeft,suppressed:track.classList.contains('is-workspace-trail-aligning')};
                                }""")
                                expected=360 if viewport=='desktop' else 390
                                self.assertAlmostEqual(motion['after'],-expected if opening else 0,delta=1)
                                self.assertGreater(abs(motion['after']-motion['before']),100)
                                self.assertTrue(any(min(motion['before'],motion['after'])+1<v<max(motion['before'],motion['after'])-1 for v in motion['values']))
                                self.assertIn('transitionrun',motion['events']);self.assertIn('transitionend',motion['events'])
                                self.assertEqual(motion['scroll'],0);self.assertFalse(motion['suppressed'])
                                expect(page.locator('#account-page-identity')).to_be_enabled() if opening else expect(page.locator('#account-page-identity')).to_be_disabled()
                                samples.append({'viewport':viewport,'feature':action,'opening':opening,**motion})
                    finally:context.close()
            finally:browser.close()
        output=Path(settings.BASE_DIR)/'.artifacts'/'account-feature-switch'/'after'
        output.mkdir(parents=True,exist_ok=True)
        (output/'motion.json').write_text(json.dumps(samples,indent=2),encoding='utf-8')


    def test_back_aborts_native_fetch_for_owner_other_guest_pc_mobile(self):
        from django.test import Client
        from playwright.sync_api import sync_playwright, expect
        sessions = {}
        for role, user in [('owner', self.owner), ('other', self.other)]:
            client = Client()
            client.force_login(user)
            sessions[role] = client.cookies[settings.SESSION_COOKIE_NAME].value
        rows = []
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='msedge', headless=True)
            try:
                for viewport, size in [('desktop', {'width':1280, 'height':900}), ('mobile', {'width':390, 'height':844})]:
                    for role in ['owner', 'other', 'guest']:
                        context = browser.new_context(viewport=size, is_mobile=viewport=='mobile', has_touch=viewport=='mobile')
                        if role in sessions:
                            context.add_cookies([{'name':settings.SESSION_COOKIE_NAME, 'value':sessions[role], 'url':self.live_server_url}])
                        page = context.new_page()
                        errors = []
                        page.on('pageerror', lambda e: errors.append(str(e)))
                        page.on('console', lambda m: errors.append(m.text) if m.type=='error' and not m.location.get('url','').endswith('/favicon.ico') else None)
                        try:
                            for action, feature, attribute in [('boards','board','data-boards-url'), ('people','people','data-account-lists-url')]:
                                with self.subTest(viewport=viewport, viewer=role, feature=feature):
                                    url = self.live_server_url + reverse('accounts:detail', args=[self.owner.username])
                                    page.goto(url)
                                    page.locator('[data-open-account-threads]').click()
                                    expect(page.locator('[data-thread-pane-container] .ui-tabs')).to_be_visible()
                                    path = page.locator('.account-page').get_attribute(attribute)
                                    page.evaluate("""path => {
                                      const original = window.fetch;
                                      window.qaHeld = false;
                                      window.fetch = (...args) => original(...args).then(response => {
                                        if (!window.qaHeld && new URL(args[0],location.origin).pathname === path) {
                                          window.qaHeld = true;
                                          return new Promise(resolve => { window.qaRelease = () => resolve(response); });
                                        }
                                        return response;
                                      });
                                    }""", path)
                                    page.locator('[data-open-account-'+action+']').evaluate('el=>el.click()')
                                    page.wait_for_function('window.qaHeld === true')
                                    body = page.locator('.account-'+feature+'-list-pane [data-account-feature-body]')
                                    body.evaluate('el=>el.innerHTML="<span data-qa-retained-marker>retained</span>"')
                                    page.go_back()
                                    expect(page.locator('.account-track')).to_have_attribute('data-ui-workspace-stage','list')
                                    page.evaluate('window.qaRelease()')
                                    page.wait_for_timeout(150)
                                    preserved = body.locator('[data-qa-retained-marker]').count() == 1
                                    rows.append({'viewport':viewport, 'viewer':role, 'feature':feature, 'late_response_discarded':preserved})
                                    # Forward creates a fresh request and restores the standard stage/Current/Close contract.
                                    page.go_forward()
                                    expect(page.locator('.account-track')).to_have_attribute('data-ui-workspace-stage',feature+'-list')
                                    expect(body.locator('.ui-tabs')).to_be_visible()
                                    expect(page.locator('#account-page-identity')).to_be_enabled()
                                    page.locator('#close-account-'+feature+'-list').click()
                                    expect(page.locator('.account-track')).to_have_attribute('data-ui-workspace-stage','overview')
                                    self.assertEqual(page.url, url)
                                    self.assertTrue(preserved, 'Back must invalidate the original native feature request')
                            self.assertEqual(errors, [])
                        finally:
                            context.close()
            finally:
                browser.close()
        output = Path(settings.BASE_DIR) / '.artifacts' / 'account-feature-switch' / 'after'
        output.mkdir(parents=True, exist_ok=True)
        (output/'history-roles.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
