"""AccountIF endpoint and Summary color regression, isolated fixtures only."""
import json
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db.backends.postgresql.base import DatabaseWrapper
from django.db.models.query import QuerySet
from django.test import Client, TestCase
from django.urls import reverse
from interfaces.models import (AccountInterfaceImplementation, AccountFieldValue, InterfaceDraft,
    InterfaceDraftField, FieldDefinition, InterfaceList, InterfaceListReference,
    FieldListReference, AccountLayoutDraft)
from interfaces.services import publish_field_definition, publish_draft
from interfaces import account_layouts
from scripts.browser_test_server import SharedSQLiteStaticFilesHandler


def seed(case):
    assert settings.DATABASES['default']['ENGINE'] == 'django.db.backends.sqlite3'
    case.owner = get_user_model().objects.create_user('if_fix_owner')
    case.other = get_user_model().objects.create_user('if_fix_other')
    case.field, _ = publish_field_definition(creator=case.owner, name='Fix Field', field_type='short_text')
    draft = InterfaceDraft.objects.create(creator=case.owner, kind='account', name='Fix AccountIF')
    InterfaceDraftField.objects.create(draft=draft, definition=case.field, required=True, position=0)
    case.interface, _ = publish_draft(draft.pk)
    case.url = reverse('accounts:applied-change', args=[case.owner.username])
    case.payload = {'operation':'add_interface','id':case.interface.pk,'values':{str(case.field.key):['preserved input']}}


def csrf_client(user=None):
    client = Client(enforce_csrf_checks=True)
    if user: client.force_login(user)
    client.get(reverse('accounts:detail', args=['if_fix_owner']))
    return client


class AccountIfRegressionTests(TestCase):
    def setUp(self): seed(self)

    def post(self, client, payload=None, path=None):
        return client.post(path or self.url, json.dumps(payload or self.payload), content_type='application/json',
                           HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value)

    def test_postgres_nullable_join_lock_contract_through_real_api(self):
        # Compile only: this PG connection never connects or executes SQL.
        pg = DatabaseWrapper({'ENGINE':'django.db.backends.postgresql','NAME':'compile_only',
                              'TIME_ZONE':None,'OPTIONS':{},'AUTOCOMMIT':True}, alias='compile_only')
        pg.get_autocommit = lambda: False
        original = QuerySet._fetch_all
        statements = []
        def inspect(queryset):
            if queryset.model is FieldDefinition and queryset.query.select_for_update:
                sql, _ = queryset.query.get_compiler(connection=pg).as_sql()
                statements.append(sql)
            return original(queryset)
        with patch.object(QuerySet, '_fetch_all', inspect):
            response = self.post(csrf_client(self.owner))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(statements)
        self.assertIn('LEFT OUTER JOIN', statements[0])
        self.assertTrue(statements[0].endswith('FOR UPDATE OF "interfaces_fielddefinition"'), statements[0])
        self.assertEqual(AccountInterfaceImplementation.objects.count(), 1)

    def test_csrf_origin_and_missing_tokens_return_json_without_writes(self):
        client = csrf_client(self.owner)
        for extra in [{}, {'HTTP_X_CSRFTOKEN':'x'*32},
                      {'HTTP_X_CSRFTOKEN':client.cookies['csrftoken'].value, 'HTTP_ORIGIN':'https://outside.invalid'}]:
            response = client.post(self.url,json.dumps(self.payload),content_type='application/json',**extra)
            self.assertEqual(response.status_code,403)
            self.assertEqual(response['Content-Type'],'application/json')
            self.assertEqual(response.json()['code'],'csrf_failed')
        self.assertEqual(AccountInterfaceImplementation.objects.count(),0)
        self.assertEqual(AccountFieldValue.objects.count(),0)
        # Ordinary form CSRF failures retain Django's original response.
        response=client.post(reverse('mypage'),{'display_name':'blocked'})
        self.assertEqual(response.status_code,403)
        self.assertTrue(response['Content-Type'].startswith('text/html'))

    def test_auth_stale_target_and_duplicate_are_json_and_atomic(self):
        for user,code in [(None,401),(self.other,403)]:
            response=self.post(csrf_client(user))
            self.assertEqual(response.status_code,code)
            self.assertEqual(response['Content-Type'],'application/json')
            self.assertIsNone(response.get('Location'))
        owner=csrf_client(self.owner)
        response=self.post(owner,path=reverse('accounts:applied-change',args=['missing_account']))
        self.assertEqual(response.status_code,404)
        self.assertEqual(response['Content-Type'],'application/json')
        response=self.post(owner,{'operation':'add_interface','id':self.interface.pk,'values':{}})
        self.assertEqual(response.status_code,400)
        self.assertEqual(AccountInterfaceImplementation.objects.count(),0)
        self.assertEqual(self.post(owner).status_code,200)
        self.assertEqual(self.post(owner).status_code,400)
        self.assertEqual(AccountInterfaceImplementation.objects.count(),1)
        self.assertEqual(AccountFieldValue.objects.count(),1)


class AccountIfFixBrowserTests(StaticLiveServerTestCase):
    static_handler=SharedSQLiteStaticFilesHandler
    def setUp(self):
        seed(self)
        self.client.force_login(self.owner)
        self.owner_session=self.client.cookies[settings.SESSION_COOKIE_NAME].value
        other=Client();other.force_login(self.other)
        self.other_session=other.cookies[settings.SESSION_COOKIE_NAME].value
        self.output=Path(settings.BASE_DIR)/'.artifacts/account-if-fix'
        self.output.mkdir(parents=True,exist_ok=True)

    def context(self,browser,viewport,size):
        context=browser.new_context(viewport=size,is_mobile=viewport=='mobile',has_touch=viewport=='mobile')
        context.add_cookies([{'name':settings.SESSION_COOKIE_NAME,'value':self.owner_session,'url':self.live_server_url}])
        page=context.new_page();page.set_default_timeout(8000)
        return context,page

    def remove_application(self,context,page):
        context.add_cookies([{'name':settings.SESSION_COOKIE_NAME,'value':self.owner_session,'url':self.live_server_url}])
        page.goto(self.live_server_url+'/mypage/')
        token=page.locator('[name=csrfmiddlewaretoken]').first.input_value()
        applied=page.request.get(self.live_server_url+reverse('accounts:applied-data',args=[self.owner.username])).json()
        response=page.request.post(self.live_server_url+self.url,
            data={'operation':'remove_interface','id':applied['interfaces'][0]['id']},headers={'X-CSRFToken':token})
        self.assertTrue(response.ok)

    def picker(self,page):
        page.goto(self.live_server_url+'/mypage/?section=applied')
        pane=page.locator('[data-applied-pane]')
        pane.locator('[data-ui-tab="applied-interface"]').click()
        pane.locator('[data-add-applied="interface"]').click()
        listing=page.locator('.thread-create-module-list-pane')
        listing.locator('.ui-tab-panel.is-active .ui-summary-item').filter(has_text='Fix AccountIF@').click()
        editor=page.locator('.thread-create-module-detail-pane')
        editor.locator('.interface-implementation-editor input').fill('preserved input')
        return pane,editor

    def color(self,locator,kind):
        self.assertEqual(locator.get_attribute('data-summary-kind'),kind)
        result=locator.evaluate('''el=>({kind:getComputedStyle(el).getPropertyValue('--summary-kind-color').trim(),
            expected:getComputedStyle(document.documentElement).getPropertyValue('--summary-'+el.dataset.summaryKind+'-color').trim(),
            background:getComputedStyle(el).backgroundColor,border:getComputedStyle(el).borderBottomColor})''')
        self.assertTrue(result['expected'])
        self.assertEqual(result['kind'],result['expected'])
        self.assertNotIn(result['background'],['transparent','rgba(0, 0, 0, 0)'])
        return result

    def test_colors_picker_applied_public_module_list_and_require(self):
        from playwright.sync_api import sync_playwright,expect
        from interfaces.account_applications import change_application
        item=InterfaceList.objects.create(owner=self.owner,name='Fix ModuleList',submission_id=uuid4())
        InterfaceListReference.objects.create(interface_list=item,target=self.interface)
        FieldListReference.objects.create(interface_list=item,target=self.field)
        extra,_=publish_field_definition(creator=self.owner,name='Require Field',field_type='short_text')
        payload={'name':'Color Layout','description':'','html':'<p>Color QA</p>','css':'',
                 'requirements':{'fields':[extra.pk],'interfaces':[self.interface.pk]},'items':[]}
        draft=AccountLayoutDraft.objects.create(creator=self.owner)
        layout=account_layouts.save_draft(self.owner,draft.pk,payload,publish=True,
                    token=account_layouts.preview(self.owner,payload)['token'])
        records=[]
        with sync_playwright() as pw:
            browser=pw.chromium.launch(channel='msedge',headless=True)
            try:
                for viewport,size in [('desktop',{'width':1280,'height':800}),('mobile',{'width':390,'height':844})]:
                    context,page=self.context(browser,viewport,size);errors=[]
                    page.on('pageerror',lambda e:errors.append(str(e)))
                    page.on('console',lambda m:errors.append(m.text) if m.type=='error' and not m.location.get('url','').endswith('/favicon.ico') else None)
                    try:
                        page.goto(self.live_server_url+'/mypage/?section=applied')
                        pane=page.locator('[data-applied-pane]');pane.locator('[data-add-applied="field"]').click()
                        listing=page.locator('.thread-field-list-pane')
                        row=listing.locator('.ui-tab-panel.is-active .ui-summary-item').filter(has_text='Fix Field@')
                        records.append({'viewport':viewport,'route':'field-picker',**self.color(row,'field')})
                        listing.locator('.icon-button').click()
                        pane,editor=self.picker(page)
                        row=page.locator('.thread-create-module-list-pane .ui-tab-panel.is-active .ui-summary-item').filter(has_text='Fix AccountIF@')
                        records.append({'viewport':viewport,'route':'interface-picker',**self.color(row,'interface')})
                        with page.expect_response(lambda r:r.url.endswith('/applied/change/')) as saved:
                            editor.locator('.interface-detail-actions button').click()
                        self.assertEqual(saved.value.status,200)
                        expect(page.locator('.thread-create-module-selector-pane')).to_have_count(0)
                        pane=page.locator('[data-applied-pane]');pane.locator('[data-ui-tab="applied-field"]').click()
                        self.color(pane.locator('[data-edit-applied-field]'),'field')
                        pane.locator('[data-ui-tab="applied-interface"]').click()
                        self.color(pane.locator('[data-edit-applied-interface]'),'interface')
                        page.screenshot(path=self.output/f'{viewport}-applied-owner.png',full_page=True)
                        for role,session in [('owner',self.owner_session),('other',self.other_session),('guest',None)]:
                            context.clear_cookies()
                            if session:context.add_cookies([{'name':settings.SESSION_COOKIE_NAME,'value':session,'url':self.live_server_url}])
                            page.goto(self.live_server_url+f'/accounts/{self.owner.username}/?pane=account-if&tab=applied-interface')
                            public=page.locator('[data-account-applied-container]')
                            expect(public.locator('[data-ui-tab-panel="applied-interface"] .ui-summary-item')).to_be_visible()
                            for kind,tab in [('interface','applied-interface'),('field','applied-field')]:
                                public.locator(f'[data-ui-tab="{tab}"]').click()
                                row=public.locator(f'[data-ui-tab-panel="{tab}"] .ui-summary-item')
                                records.append({'viewport':viewport,'role':role,'route':'applied',**self.color(row,kind)})
                            expect(public.locator('[data-add-applied]')).to_have_count(0)
                            page.goto(self.live_server_url+f'/accounts/{self.owner.username}/?pane=module&type=interface&subtype=account')
                            row=page.locator('[data-module-public] [data-module-public-page]:visible .ui-summary-item')
                            records.append({'viewport':viewport,'role':role,'route':'public-module',**self.color(row,'interface')})
                        page.goto(self.live_server_url+reverse('references:interface-list-page',args=[item.pk]))
                        for kind in ['field','interface']:
                            self.color(page.locator(f'[data-account-list-detail] .ui-summary-item[data-summary-kind="{kind}"]'),kind)
                        page.goto(self.live_server_url+reverse('references:layout-page',args=[layout.layout_id]))
                        require=page.locator('.layout-require-status')
                        for kind in ['field','interface']:
                            records.append({'viewport':viewport,'route':'layout-require',**self.color(require.locator(f'[data-summary-kind="{kind}"]'),kind)})
                        page.screenshot(path=self.output/f'{viewport}-layout-require.png',full_page=True)
                        self.assertEqual(errors,[])
                        self.remove_application(context,page)
                    finally:context.close()
            finally:browser.close()
        (self.output/'colors.json').write_text(json.dumps(records,indent=2),encoding='utf-8')

    def test_real_csrf_expired_session_other_and_html_keep_input_then_retry(self):
        from playwright.sync_api import sync_playwright,expect
        from interfaces.account_applications import change_application
        records=[]
        with sync_playwright() as pw:
            browser=pw.chromium.launch(channel='msedge',headless=True)
            try:
                for viewport,size in [('desktop',{'width':1280,'height':800}),('mobile',{'width':390,'height':844})]:
                    context,page=self.context(browser,viewport,size);page_errors=[];console_errors=[]
                    page.on('pageerror',lambda e:page_errors.append(str(e)))
                    page.on('console',lambda m:console_errors.append({'text':m.text,'url':m.location.get('url','')}) if m.type=='error' else None)
                    try:
                        page.goto(self.live_server_url+'/mypage/?section=applied')
                        pane=page.locator('[data-applied-pane]')
                        expect(pane.locator('h2')).to_have_text('Applied一覧')
                        pane.locator('[data-ui-tab="applied-interface"]').click()
                        for role,session in [('other',self.other_session),('guest',None)]:
                            context.clear_cookies()
                            if session:context.add_cookies([{'name':settings.SESSION_COOKIE_NAME,'value':session,'url':self.live_server_url}])
                            with page.expect_response(lambda r:r.url.endswith('/applied/data/')) as result:
                                pane.locator('[data-add-applied="interface"]').click()
                            self.assertEqual(result.value.status,200)
                            self.assertNotIn('catalog',result.value.json())
                            expect(pane.locator('[data-applied-error]')).to_contain_text('ログイン状態')
                            expect(page.locator('.thread-create-module-selector-pane')).to_have_count(0)
                            records.append({'viewport':viewport,'case':role+'-catalog','status':200,'content_type':'application/json','private_catalog':False})
                        context.add_cookies([{'name':settings.SESSION_COOKIE_NAME,'value':self.owner_session,'url':self.live_server_url}])
                        pane,editor=self.picker(page)
                        input_=editor.locator('.interface-implementation-editor input');button=editor.locator('.interface-detail-actions button')
                        original=pane.locator('[name=csrfmiddlewaretoken]').first.input_value()
                        csrf=[c for c in context.cookies() if c['name']=='csrftoken'][0]
                        def attempt(label,status,text):
                            with page.expect_response(lambda r:r.url.endswith('/applied/change/')) as result:button.click()
                            response=result.value
                            self.assertEqual(response.status,status)
                            expect(editor.locator('[data-applied-error]')).to_contain_text(text)
                            expect(input_).to_have_value('preserved input');expect(button).to_be_enabled()
                            self.assertEqual(page.request.get(self.live_server_url+reverse('accounts:applied-data',args=[self.owner.username])).json()['interfaces'],[])
                            records.append({'viewport':viewport,'case':label,'status':response.status,'content_type':response.headers.get('content-type'),'redirect':response.headers.get('location')})
                        pane.locator('[name=csrfmiddlewaretoken]').first.evaluate("el=>el.value='x'.repeat(32)")
                        attempt('csrf-mismatch',403,'確認情報')
                        pane.locator('[name=csrfmiddlewaretoken]').first.evaluate('(el,value)=>el.value=value',original)
                        context.clear_cookies();context.add_cookies([csrf])
                        attempt('expired-session',401,'ログイン')
                        context.add_cookies([{'name':settings.SESSION_COOKIE_NAME,'value':self.other_session,'url':self.live_server_url}])
                        attempt('other-session',403,'本人')
                        context.add_cookies([{'name':settings.SESSION_COOKIE_NAME,'value':self.owner_session,'url':self.live_server_url}])
                        route=self.live_server_url+self.url
                        page.route(route,lambda r:r.fulfill(status=500,content_type='text/html',body='<!doctype html><title>Server Error</title>'))
                        attempt('html-server-error',500,'入力内容を保持')
                        page.unroute(route)
                        page.route(route,lambda r:r.fulfill(status=302,headers={'Location':'/mypage/'},body=''))
                        with page.expect_response(lambda r:r.url.endswith('/mypage/') and r.request.method=='GET'):
                            button.click()
                        expect(editor.locator('[data-applied-error]')).to_contain_text('ログイン状態')
                        expect(input_).to_have_value('preserved input');expect(button).to_be_enabled()
                        page.unroute(route)
                        calls=[]
                        page.on('response',lambda r:calls.append(r.status) if r.url.endswith('/applied/change/') else None)
                        button.evaluate('el=>{el.click();el.click();}')
                        expect(page.locator('.thread-create-module-selector-pane')).to_have_count(0)
                        self.assertEqual(calls,[200])
                        self.assertEqual(len(page.request.get(self.live_server_url+reverse('accounts:applied-data',args=[self.owner.username])).json()['interfaces']),1)
                        self.assertEqual(page_errors,[])
                        unexpected=[e for e in console_errors if not (e['url'].endswith('/applied/change/') and 'Failed to load resource' in e['text']) and not e['url'].endswith('/favicon.ico')]
                        self.assertEqual(unexpected,[])
                        records.append({'viewport':viewport,'case':'retry-double-click','status':200,'expected_negative_http_console':console_errors,'unexpected_errors':0})
                        if viewport=='desktop':self.remove_application(context,page)
                    finally:context.close()
            finally:browser.close()
        self.assertEqual(AccountInterfaceImplementation.objects.filter(account=self.owner).count(),1)
        self.assertEqual(AccountFieldValue.objects.filter(account=self.owner).count(),1)
        (self.output/'errors-and-retry.json').write_text(json.dumps(records,indent=2),encoding='utf-8')