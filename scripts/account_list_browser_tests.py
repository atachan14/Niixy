"""AccountList PC/mobile Workspace tests; isolated SQLite and local Edge."""
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from accounts.models import AccountList, AccountListReference, AccountReview
from scripts.browser_test_server import SharedSQLiteStaticFilesHandler


class AccountListBrowserTests(StaticLiveServerTestCase):
    static_handler = SharedSQLiteStaticFilesHandler

    def setUp(self):
        # Representative Account/Room/Board/NiiMap fixtures also exercise smoke.
        from scripts.review_browser_tests import ReviewBrowserTests
        ReviewBrowserTests.setUp(self)
        AccountReview.objects.create(author=self.author,target=self.target,sentiment='love',body='Listに追加する紹介文')
        self.existing=AccountList.objects.create(owner=self.author,name='既存List',submission_id=uuid4())
        for review in AccountReview.objects.filter(target=self.target).exclude(author=self.author):
            AccountListReference.objects.create(account_list=self.existing,target=review.author)

    def test_account_list_pc_mobile_and_smoke(self):
        from playwright.sync_api import expect, sync_playwright
        from scripts.browser_smoke import main as smoke_main, wait_for_trail_count
        output=Path(settings.BASE_DIR)/'.artifacts'/'account-lists';output.mkdir(parents=True,exist_ok=True)
        with sync_playwright() as pw:
            browser=pw.chromium.launch(channel='msedge',headless=True)
            try:
                for name,size in [('desktop',{'width':1280,'height':900}),('mobile',{'width':390,'height':844})]:
                    context=browser.new_context(viewport=size,is_mobile=name=='mobile',has_touch=name=='mobile')
                    context.add_cookies([{'name':settings.SESSION_COOKIE_NAME,'value':self.client.cookies[settings.SESSION_COOKIE_NAME].value,'url':self.live_server_url}])
                    page=context.new_page();page.set_default_timeout(10000);errors=[]
                    page.on('pageerror',lambda e: errors.append(str(e)))
                    page.on('console',lambda m: errors.append(m.text) if m.type=='error' and not m.location.get('url','').endswith('/favicon.ico') else None)
                    page.goto(self.live_server_url+'/accounts/review_browser_target/')
                    root=page.locator('.account-overview-pane [data-review-section]')
                    root.locator('[data-account-list-picker-url]').click();wait_for_trail_count(page,1)
                    picker=page.locator('[data-account-list-picker]')
                    expect(picker).to_be_visible()
                    picker.locator('summary').click()
                    expect(picker.locator('[data-list-share-url]')).to_have_value(self.live_server_url+'/accounts/review_browser_target/')
                    picker.locator('[data-copy-list-url]').click()
                    expect(picker.locator('[data-list-share-status]')).to_be_visible()
                    # The same reference can be safely added twice.
                    existing=picker.locator('[data-list-operation=pick]').filter(has_text='既存List')
                    existing.locator('[type=submit]').click();expect(existing.locator('[data-list-success]')).to_have_text('追加しました。')
                    existing.locator('[type=submit]').click()
                    create=picker.locator('[data-list-operation=create]');create.locator('[name=name]').fill('入力保持 '+name)
                    page.locator('.ui-workspace-trail-header .icon-button').last.click();wait_for_trail_count(page,0)
                    root.locator('[data-account-list-picker-url]').click();wait_for_trail_count(page,1)
                    expect(create.locator('[name=name]')).to_have_value('入力保持 '+name)
                    # Transport failure preserves editable input and retry token.
                    page.evaluate("""() => {window.listFetch=fetch;window.fetch=(...args)=>String(args[0]).endsWith('/lists/create/')?Promise.reject(new Error('通信テスト失敗')):window.listFetch(...args);} """)
                    create.locator('[type=submit]').click();expect(create.locator('.account-list-error')).to_have_text('通信テスト失敗')
                    expect(create.locator('[name=name]')).to_be_enabled()
                    page.evaluate('() => {window.fetch=window.listFetch;}')
                    create.locator('[name=name]').fill('QA List '+name)
                    # Mute Cancel and failure retain List input, including a closed draft.
                    page.once('dialog',lambda d:d.dismiss())
                    root.locator('[data-mute-form]').evaluate("el=>el.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}))")
                    expect(create.locator('[name=name]')).to_have_value('QA List '+name)
                    page.evaluate("""() => {window.listFetch=fetch;window.fetch=(...args)=>String(args[0]).endsWith('/mute/')?
                      new Promise(resolve=>setTimeout(resolve,250)).then(()=>new Response(JSON.stringify({error:'Muteテスト失敗'}),{status:400,headers:{'Content-Type':'application/json'}})):window.listFetch(...args);} """)
                    page.once('dialog',lambda d:d.accept())
                    root.locator('[data-mute-form]').evaluate("el=>el.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}))")
                    expect(create.locator('[name=name]')).to_be_disabled()
                    expect(root.locator('.review-error')).to_have_text('Muteテスト失敗')
                    expect(create.locator('[name=name]')).to_be_enabled()
                    expect(create.locator('[name=name]')).to_have_value('QA List '+name)
                    page.evaluate('() => {window.fetch=window.listFetch;}')
                    # A List GET can complete while Mute is pending. New controls
                    # must unlock too when Mute fails, retaining the closed draft.
                    page.locator('.ui-workspace-trail-header .icon-button').last.click();wait_for_trail_count(page,0)
                    page.evaluate("""() => {window.listFetch=fetch;window.fetch=(...args)=>{
                      if(String(args[0]).endsWith('/mute/'))return new Promise(resolve=>setTimeout(resolve,600)).then(()=>new Response(JSON.stringify({error:'遅いMute失敗'}),{status:400,headers:{'Content-Type':'application/json'}}));
                      if(String(args[0]).endsWith('/lists/picker/'))return window.listFetch(...args).then(response=>new Promise(resolve=>setTimeout(()=>resolve(response),100)));
                      return window.listFetch(...args);};}""")
                    root.locator('[data-account-list-picker-url]').evaluate('el=>el.click()')
                    page.once('dialog',lambda d:d.accept())
                    root.locator('[data-mute-form]').evaluate("el=>el.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}))")
                    expect(create.locator('[name=name]')).to_be_disabled()
                    expect(root.locator('.review-error')).to_have_text('遅いMute失敗')
                    expect(create.locator('[name=name]')).to_be_enabled()
                    expect(create.locator('[name=name]')).to_have_value('QA List '+name)
                    page.evaluate('() => {window.fetch=window.listFetch;}')
                    # Delayed repeated submit, followed by source retention.
                    page.evaluate("""() => {window.listFetch=fetch;window.listWrites=0;window.fetch=(...args)=>{
                      if(!String(args[0]).endsWith('/lists/create/'))return window.listFetch(...args);
                      window.listWrites++;return new Promise(resolve=>setTimeout(resolve,300)).then(()=>window.listFetch(...args));};}""")
                    create.evaluate("el=>{el.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));el.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));}")
                    wait_for_trail_count(page,2)
                    detail=page.locator('[data-account-list-detail]')
                    expect(detail.locator('.account-summary')).to_have_count(1)
                    self.assertEqual(page.evaluate('window.listWrites'),1)
                    page.evaluate('() => {window.fetch=window.listFetch;}')
                    list_url=page.url
                    self.assertIn('/accounts/lists/',list_url)
                    self.assertFalse(detail.evaluate('el=>el.scrollWidth>el.clientWidth+1'))
                    page.screenshot(path=output/f'{name}-list.png')
                    # AccountSummary opens a child; Close preserves the List form.
                    add=detail.locator('[data-list-operation=add]');add.locator('[name=target_url]').fill(self.live_server_url+'/accounts/review_fixture_0/')
                    detail.locator('.account-summary').click();wait_for_trail_count(page,3)
                    expect(page.locator('.ui-workspace-trail-pane [data-account-fragment]')).to_be_visible()
                    page.locator('.ui-workspace-trail-header .icon-button').last.click();wait_for_trail_count(page,2)
                    expect(add.locator('[name=target_url]')).to_have_value(self.live_server_url+'/accounts/review_fixture_0/')
                    add.locator('[type=submit]').click();expect(detail.locator('.account-summary')).to_have_count(2)
                    detail.locator('summary').filter(has_text='Listの管理').click()
                    rename=detail.locator('[data-list-operation=rename]');rename.locator('[name=name]').fill('改名 '+name);rename.locator('[type=submit]').click()
                    expect(page.locator('.ui-workspace-trail-header h2').last).to_have_text('改名 '+name)
                    page.reload();wait_for_trail_count(page,1)
                    expect(detail.locator('.account-summary')).to_have_count(2)
                    detail.locator('[data-list-operation=remove]').first.locator('[type=submit]').click()
                    expect(detail.locator('.account-summary')).to_have_count(1)
                    # Root replaces the whole later branch, then List opens from People.
                    page.locator('.account-overview-pane [data-open-account-people]').evaluate('el=>el.click()')
                    wait_for_trail_count(page,1)
                    index=page.locator('[data-account-lists-index]')
                    expect(index.locator('[data-account-list-form]')).to_have_count(1) # direct List reload uses owner Account
                    page.goto(self.live_server_url+'/accounts/review_browser_author/')
                    page.locator('[data-open-account-people]').click();wait_for_trail_count(page,1)
                    expect(index.locator('[data-list-operation=create]')).to_be_visible()
                    index.locator('[data-account-list-link]').filter(has_text='改名 '+name).click();wait_for_trail_count(page,2)
                    detail.locator('summary').filter(has_text='Listの管理').click()
                    page.once('dialog',lambda d:d.accept())
                    detail.locator('[data-list-operation=delete] [type=submit]').click();wait_for_trail_count(page,1)
                    expect(index.locator('[data-account-list-link]').filter(has_text='改名 '+name)).to_have_count(0)
                    # Late GET after Close must not resurrect its Pane.
                    page.evaluate("""() => {window.listFetch=fetch;window.fetch=(...args)=>{
                      if(!String(args[0]).includes('/lists/'))return window.listFetch(...args);
                      args[1]={...args[1],signal:undefined};return window.listFetch(...args).then(r=>new Promise(resolve=>setTimeout(()=>resolve(r),300)));};}""")
                    index.locator('[data-account-list-link]').filter(has_text='既存List').click()
                    page.locator('.ui-workspace-trail-header .icon-button').last.click();wait_for_trail_count(page,1)
                    page.wait_for_timeout(400);expect(detail).to_have_count(0)
                    page.evaluate('() => {window.fetch=window.listFetch;}')
                    index.locator('[data-account-list-link]').filter(has_text='既存List').click();wait_for_trail_count(page,2)
                    # Nested People uses the same right-side replacement, without
                    # dropping the parent's pending URL input.
                    detail.locator('.account-summary').first.click();wait_for_trail_count(page,3)
                    nested=page.locator('.ui-workspace-trail-pane [data-account-fragment]')
                    nested.locator('[data-open-account-people]').click();wait_for_trail_count(page,4)
                    expect(page.locator('[data-account-lists-index]').last).to_be_visible()
                    page.locator('.ui-workspace-trail-header .icon-button').last.click();wait_for_trail_count(page,3)
                    page.locator('.ui-workspace-trail-header .icon-button').last.click();wait_for_trail_count(page,2)
                    # Close during delayed add then reopen; stale callback neither
                    # closes nor replaces the newer Pane.
                    detail.locator('[data-list-operation=add] [name=target_url]').fill(self.live_server_url+'/accounts/review_browser_author/')
                    page.evaluate("""() => {window.listFetch=fetch;window.fetch=(...args)=>String(args[0]).endsWith('/add/')?
                      new Promise(resolve=>setTimeout(resolve,300)).then(()=>window.listFetch(...args)):window.listFetch(...args);} """)
                    detail.locator('[data-list-operation=add] [type=submit]').click()
                    page.locator('.ui-workspace-trail-header .icon-button').last.click();wait_for_trail_count(page,1)
                    index.locator('[data-account-list-link]').filter(has_text='既存List').click();wait_for_trail_count(page,2)
                    expect(detail.locator('.account-summary')).to_have_count(15)
                    page.evaluate('() => {window.fetch=window.listFetch;}')
                    expect(index.locator('[data-account-list-link]').filter(has_text='既存List').locator('[data-list-count]')).to_have_text('15')
                    page.screenshot(path=output/f'{name}-workspace.png')
                    # Guest URL direct read preserves targets and hides owner writes.
                    context.clear_cookies();page.goto(self.live_server_url+f'/accounts/lists/{self.existing.pk}/')
                    wait_for_trail_count(page,1)
                    expect(detail.locator('.account-summary')).to_have_count(15)
                    expect(detail.locator('[data-account-list-form]')).to_have_count(0)
                    page.screenshot(path=output/f'{name}-guest.png')
                    self.assertEqual(errors,[])
                    context.close()
            finally: browser.close()
        # AGENTS-required unchanged smoke entrypoint runs against isolated server.
        with patch('sys.argv',['scripts/browser_smoke.py','--base-url',self.live_server_url,'--output-dir',str(Path(settings.BASE_DIR)/'.artifacts'/'browser-smoke')]):
            self.assertEqual(smoke_main(),0)
