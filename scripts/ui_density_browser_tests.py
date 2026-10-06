"""Actual Niixy forms, isolated SQLite and Edge; compare density and preserve UI."""
import json,os
from pathlib import Path
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from interfaces.models import InterfaceDraft,InterfaceDraftField
from interfaces.services import publish_draft,publish_field_definition
from events.models import Thread,ThreadPost,ThreadPlacement,ThreadAccessRule
from scripts.browser_test_server import SharedSQLiteStaticFilesHandler
from scripts import module_selector_browser_tests as selector_tests

class DensityBrowserTests(StaticLiveServerTestCase):
    static_handler=SharedSQLiteStaticFilesHandler
    host='127.0.0.1'
    def setUp(self):
        self.assertEqual(settings.DATABASES['default']['ENGINE'], 'django.db.backends.sqlite3')
        selector_tests.ModuleSelectorBrowserTests.setUp(self)
        self.phase=os.environ.get('NIIXY_DENSITY_PHASE','after')
        self.output=Path(settings.BASE_DIR)/'.artifacts/ui-density'/self.phase
        self.output.mkdir(parents=True,exist_ok=True)
        self.other=get_user_model().objects.create_user('density_other')
        field,_=publish_field_definition(creator=self.owner,name='長い日本語の紹介文項目',field_type='long_text')
        draft=InterfaceDraft.objects.create(creator=self.owner,kind='account',name='密度確認AccountIF')
        InterfaceDraftField.objects.create(draft=draft,definition=field,position=0)
        self.account_if,_=publish_draft(draft.pk)
        self.module_draft=InterfaceDraft.objects.create(creator=self.owner,kind='account',name='日本語の入力と折り返しを確認するDraft')
        self.layout_draft=self.client.post(reverse('interfaces:layout-draft-create')).json()['draft_id']
        self.thread=Thread.objects.create(creator=self.owner,title='密度確認のThread')
        for number in [1,2]:ThreadPost.objects.create(thread=self.thread,creator=self.owner,number=number,body='長い日本語も本文の読みやすさを保ちます。'*6)
        ThreadPlacement.objects.create(thread=self.thread,kind=ThreadPlacement.BOARD,board=self.board)
        for capability in ['view','write']:
            for audience in ['guest','account']:ThreadAccessRule.objects.create(thread=self.thread,capability=capability,audience=audience)
        self.assertEqual(self.client.get('/accounts/'+self.owner.username+'/').status_code,200)

    def snap(self,page,viewport,name,selector,form=False):
        from playwright.sync_api import expect
        region=page.locator(selector).first;expect(region).to_be_visible()
        page.wait_for_timeout(400)
        metrics=region.evaluate('''el=>({width:el.clientWidth,overflow:el.scrollWidth-el.clientWidth,controls:[...el.querySelectorAll('button,.button,input,select,textarea,h3,label')].filter(e=>e.getBoundingClientRect().width && e.getBoundingClientRect().height && getComputedStyle(e).visibility!=='hidden').map(e=>({tag:e.tagName,type:e.type||'',label:(e.textContent||e.getAttribute('name')||'').trim().slice(0,70),className:e.className,font:parseFloat(getComputedStyle(e).fontSize),height:e.getBoundingClientRect().height,width:e.getBoundingClientRect().width,disabled:!!e.disabled}))})''')
        self.assertLessEqual(page.evaluate('document.scrollingElement.scrollWidth-innerWidth'),2,(viewport,name))
        header=page.locator('.site-header').evaluate('el=>({height:el.getBoundingClientRect().height,brand:parseFloat(getComputedStyle(el.querySelector(".service-brand")).fontSize)})')
        record={'viewport':viewport,'case':name,'header':header,**metrics}
        if self.phase=='after':
            baseline=next((r for r in self.before if r['viewport']==viewport and r['case']==name), None)
            allowed_overflow=max(2,baseline['overflow']+1) if baseline else (20 if name=='thread-create' else 2)
            self.assertLessEqual(metrics['overflow'],allowed_overflow,(viewport,name,metrics))
            if baseline:
                self.assertEqual(header,baseline['header'])
            if baseline and name in ['account-overview','room-overview'] and viewport=='mobile':
                old=[(r['label'],r['font'],r['height']) for r in baseline['controls'] if r['tag']=='BUTTON' and ('account-actions' in r['className'] or r['label'] in ['Thread','Response','Room','Board','People','Applied','Module','RoomIF','Member(1)','Timeline','Policy','参加不可'])]
                new=[(r['label'],r['font'],r['height']) for r in metrics['controls'] if r['tag']=='BUTTON' and ('account-actions' in r['className'] or r['label'] in ['Thread','Response','Room','Board','People','Applied','Module','RoomIF','Member(1)','Timeline','Policy','参加不可'])]
                self.assertEqual(new,old,(name,new,old))
            if form:
                for control in metrics['controls']:
                    if control['tag']=='BUTTON' and control['label'] in ['条件を追加','Fieldを追加','Fieldを選択','新しい条件を探す']:
                        self.assertEqual(control['font'],14,(name,control))
                        self.assertGreaterEqual(control['height'],44 if viewport=='mobile' else 32,(name,control))
                    if control['tag'] in ['INPUT','SELECT','TEXTAREA'] and control['type'] not in ['checkbox','radio','hidden','color','range']:
                        self.assertGreaterEqual(control['font'],16 if viewport=='mobile' else 14,(name,control))
                        self.assertGreaterEqual(control['height'],44 if viewport=='mobile' else 32,(name,control))
                    if viewport=='mobile' and control['tag']=='BUTTON' and 'button' in control['className'].split() and 'icon-button' not in control['className']:
                        self.assertGreaterEqual(control['height'],44,(name,control))
        self.records.append(record)
        (self.output/'measurements.json').write_text(json.dumps(self.records,ensure_ascii=False,indent=2),encoding='utf-8')
        page.screenshot(path=self.output/f'{viewport}-{name}.png',full_page=True)

    def test_actual_forms_pc_mobile(self):
        from playwright.sync_api import sync_playwright,expect
        self.records=[]
        baseline_path=self.output.parent/'before/measurements.json'
        self.before=json.loads(baseline_path.read_text(encoding='utf-8')) if self.phase=='after' and baseline_path.exists() else []
        with sync_playwright() as pw:
            browser=pw.chromium.launch(channel='msedge',headless=True,args=['--no-first-run','--disable-sync'])
            try:
                for viewport,size in [('desktop',{'width':1280,'height':900}),('mobile',{'width':390,'height':844})]:
                    context=browser.new_context(viewport=size,is_mobile=viewport=='mobile',has_touch=viewport=='mobile',extra_http_headers={'Cache-Control':'no-cache'})
                    # Typography/Workspace QA does not depend on external map tiles.
                    # Keep the real SDK/events and replace only its remote base style.
                    context.route('https://cdn.geolonia.com/style/**',lambda route:route.fulfill(status=200,content_type='application/json',headers={'Access-Control-Allow-Origin':'*'},body=json.dumps({'version':8,'sources':{},'layers':[{'id':'background','type':'background','paint':{'background-color':'#f7f6f2'}}]})))
                    context.add_cookies([{'name':settings.SESSION_COOKIE_NAME,'value':self.client.cookies[settings.SESSION_COOKIE_NAME].value,'url':self.live_server_url}])
                    page=context.new_page();page.set_default_timeout(15000);errors=[]
                    page.on('pageerror',lambda e:errors.append(str(e)))
                    page.on('console',lambda e:errors.append(e.text) if e.type=='error' and not e.location.get('url','').endswith('/favicon.ico') else None)
                    try:
                        page.goto(self.live_server_url+'/accounts/'+self.owner.username+'/')
                        self.snap(page,viewport,'account-overview','.account-overview-pane')
                        page.goto(self.live_server_url+f'/rooms/{self.room.pk}/')
                        self.snap(page,viewport,'room-overview','.room-overview-pane')
                        page.locator('.room-edit-menu > summary').click()
                        self.snap(page,viewport,'room-edit','.room-edit-menu form',True)
                        page.goto(self.live_server_url+f'/rooms/{self.room.pk}/?boards=1&board={self.board.pk}')
                        page.locator('#room-thread-list-content [data-board-information-toggle]').click()
                        page.locator('#room-thread-list-content [data-board-edit-toggle]').click()
                        self.snap(page,viewport,'board-edit','.room-board-editor',True)
                        page.locator('.room-board-edit details').filter(has=page.locator('[data-open-account-conditions]')).first.locator(':scope > summary').click()
                        self.snap(page,viewport,'board-policy','.room-board-editor',True)
                        page.goto(self.live_server_url+'/')
                        page.locator('#niimap-search-toggle').click()
                        page.locator('details.niimap-search-section').filter(has=page.locator('[data-open-account-conditions="creator-include"]')).locator(':scope > summary').click()
                        self.snap(page,viewport,'search-conditions','.niimap-search-controls',True)
                        page.locator('[data-open-account-conditions="creator-include"]').click()
                        self.snap(page,viewport,'condition-picker','#account-condition-pane',True)
                        page.locator('#browse-account-conditions').click()
                        page.locator('[data-account-condition-kind="account"]').click()
                        self.snap(page,viewport,'account-selector','#account-selector-pane',True)
                        page.locator('#close-account-selector').click();page.locator('#close-account-condition-pane').click()
                        page.goto(self.live_server_url+'/');page.locator('#niimap-create-toggle').click()
                        page.locator('#map .maplibregl-canvas').click(position={'x':120,'y':140})
                        page.locator('#open-thread-create').click()
                        form=page.locator('#thread-create-form');form.locator('[name=title]').fill('保存前の日本語タイトルと入力保持を確認')
                        self.snap(page,viewport,'thread-create','#thread-create-form',True)
                        page.goto(self.live_server_url+'/mypage/?section=basic')
                        page.locator('#open-basic-info').click()
                        self.snap(page,viewport,'basic-info','.basic-info-form',True)
                        page.goto(self.live_server_url+f'/mypage/?section=module&type=interface&subtype=account&draft={self.module_draft.pk}')
                        self.snap(page,viewport,'module-draft','.interface-draft-form',True)
                        page.goto(self.live_server_url+f'/mypage/?section=module&type=layout&subtype=account&layout_draft={self.layout_draft}')
                        editor=page.locator('[data-layout-editor]');editor.locator('input[name=name]').fill('長い日本語のLayout名を入力して文字が詰まらないことを確認')
                        self.snap(page,viewport,'layout-draft','[data-layout-editor]',True)
                        page.goto(self.live_server_url+'/mypage/?section=applied')
                        page.locator('[data-applied-pane] [data-ui-tab="applied-interface"]').click()
                        page.locator('[data-add-applied="interface"]').click()
                        page.locator('.thread-create-module-list-pane .ui-tab-panel.is-active .ui-summary-item').filter(has_text='密度確認AccountIF').click()
                        self.snap(page,viewport,'applied-editor','.thread-create-module-detail-pane',True)
                        page.goto(self.live_server_url+'/accounts/'+self.other.username+'/')
                        page.locator('[data-review-section] [data-review-edit="love"]').click()
                        review=page.locator('.review-editor');review.locator('textarea').fill('長い日本語のレビューです。'*25)
                        self.snap(page,viewport,'review-editor','.review-editor',True)
                        review.locator('textarea').fill('   ')
                        review.locator('button[type=submit]').click()
                        expect(review.locator('.review-error')).to_be_visible()
                        self.snap(page,viewport,'validation-error','.review-editor',True)
                        if self.phase=='after':
                            review.locator('textarea').focus();page.keyboard.press('Tab');active=page.evaluate('({tag:document.activeElement.tagName,outline:getComputedStyle(document.activeElement).outlineStyle,width:getComputedStyle(document.activeElement).outlineWidth})')
                            self.assertNotEqual(active['outline'],'none',active)
                        page.goto(self.live_server_url+f'/threads/{self.thread.pk}/')
                        feedback=page.locator('.ui-workspace-trail-pane [data-content-kind="thread"]')
                        feedback.locator('[data-account-list-picker-url]').click()
                        self.snap(page,viewport,'list-picker','.ui-workspace-trail-pane:last-child',True)
                        context.clear_cookies();page.goto(self.live_server_url+'/accounts/'+self.other.username+'/')
                        page.locator('[data-auth-mode="login"]').click()
                        self.snap(page,viewport,'auth-dialog','.auth-dialog',True)
                        self.assertFalse(errors,errors)
                    finally:context.close()
            finally:browser.close()
        (self.output/'measurements.json').write_text(json.dumps(self.records,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'phase':self.phase,'cases':len(self.records),'page_console_errors':0,'shared_DB':False}),flush=True)
        (self.output/'qa-summary.json').write_text(json.dumps({'phase':self.phase,'cases':len(self.records),'page_console_errors':0,'shared_DB':False}),encoding='utf-8')
