"""Conversation feedback contracts; only disposable SQLite fixtures."""
import json
import subprocess
from pathlib import Path
from uuid import uuid4
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client, TestCase
from django.urls import reverse
from accounts.content_lists import KINDS, route
from accounts.models import AccountMute
from events.models import (Thread, ThreadPost, ThreadAccessRule, ThreadList, ResponseList,
    ThreadListReference, ResponseListReference, ThreadRating, ResponseRating, ThreadPlacement)
from scripts.browser_test_server import SharedSQLiteStaticFilesHandler


def seed(case):
    case.assertEqual(settings.DATABASES['default']['ENGINE'],'django.db.backends.sqlite3')
    case.owner=get_user_model().objects.create_user('conversation_owner')
    case.other=get_user_model().objects.create_user('conversation_other')
    case.thread=Thread.objects.create(creator=case.other,title='Foreign public Thread')
    case.first=ThreadPost.objects.create(thread=case.thread,creator=case.other,number=1,body='Public first body')
    case.response=ThreadPost.objects.create(thread=case.thread,creator=case.owner,number=2,body='Public reply body')
    case.private=Thread.objects.create(creator=case.other,title='Private Thread title')
    case.secret=ThreadPost.objects.create(thread=case.private,creator=case.owner,number=2,body='NEVER_EXPOSE_PRIVATE_BODY')
    case.secret2=ThreadPost.objects.create(thread=case.private,creator=case.owner,number=3,body='NEVER_EXPOSE_PRIVATE_REPLY')
    ThreadAccessRule.objects.bulk_create([ThreadAccessRule(thread=case.thread,capability=c,audience=a) for c in ['view','write'] for a in ['guest','account']])
    case.thread_list=ThreadList.objects.create(owner=case.owner,name='My Thread selections',submission_id=uuid4())
    case.response_list=ResponseList.objects.create(owner=case.owner,name='My Response selections',submission_id=uuid4())
    ThreadListReference.objects.create(thread_list=case.thread_list,target=case.thread)
    ResponseListReference.objects.create(response_list=case.response_list,target=case.response)


class ConversationFeedbackTests(TestCase):
    def setUp(self):
        seed(self);self.client.force_login(self.owner)

    def test_public_exclusive_rating_desired_state_and_counts(self):
        for kind,target in [('thread',self.thread),('response',self.response)]:
            url=route(kind,'rating',target.pk)
            for desired,expected in [('fav','fav'),('fav','fav'),('bad','bad'),('bad','bad'),('','')]:
                result=self.client.post(url,{'sentiment':desired})
                self.assertEqual(result.status_code,200);self.assertEqual(result.json()['sentiment'],expected)
                self.assertEqual(KINDS[kind].rating.objects.filter(author=self.owner,target=target).count(),bool(expected))
            self.assertEqual(self.client.post(url,{'sentiment':'love'}).status_code,400)
            self.client.post(url,{'sentiment':'fav'})
            self.client.logout();public=self.client.get(route(kind,'ratings',target.pk))
            self.assertContains(public,self.owner.username);self.assertEqual(self.client.post(url,{'sentiment':'bad'}).status_code,401)
            self.client.force_login(self.owner)

    def test_policy_csrf_owner_and_response_start_rejection(self):
        for kind,target in [('thread',self.private),('response',self.secret)]:
            for action in ['rating','picker','ratings']:
                result=self.client.post(route(kind,action,target.pk),{'sentiment':'fav'}) if action=='rating' else self.client.get(route(kind,action,target.pk))
                self.assertEqual(result.status_code,403)
            denied=self.client.get(route(kind,'pane',target.pk))
            self.assertEqual(denied.status_code,200);self.assertNotContains(denied,'NEVER_EXPOSE');self.assertNotContains(denied,'data-content-feedback')
            self.assertNotContains(denied,'data-thread-post-count');self.assertNotContains(denied,'data-target-post')
        for action in ['page','pane','rating','picker','ratings']:
            url=route('response',action,self.first.pk)
            result=self.client.post(url,{'sentiment':'fav'}) if action=='rating' else self.client.get(url)
            self.assertEqual(result.status_code,404)
        csrf=Client(enforce_csrf_checks=True);csrf.force_login(self.owner)
        self.assertEqual(csrf.post(route('thread','rating',self.thread.pk),{'sentiment':'fav'}).status_code,403)
        self.assertEqual(ThreadRating.objects.count(),0)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(route('thread','rating',self.private.pk),{'sentiment':'fav'}).status_code,200)

    def test_lists_reuse_crud_idempotency_canonical_urls_and_typed_references(self):
        for kind,target in [('thread',self.thread),('response',self.response)]:
            payload={'name':'New selections','submission_id':str(uuid4()),'target_url':route(kind,'page',target.pk)}
            result=self.client.post(route(kind,'list-create'),payload);self.assertEqual(result.status_code,201)
            duplicate=self.client.post(route(kind,'list-create'),payload);self.assertEqual(duplicate.status_code,200)
            item=KINDS[kind].model.objects.get(pk=result.json()['list_id']);self.assertEqual(item.references.count(),1)
            add=route(kind,'list-add',item.pk)
            for _ in range(2):self.assertEqual(self.client.post(add,{'target_url':payload['target_url']}).status_code,200)
            self.assertEqual(item.references.count(),1)
            for bad in ['https://outside.invalid'+payload['target_url'],payload['target_url']+'?pane=x',payload['target_url']+'#2','/threads/'+str(self.thread.pk)+'/pane/',route('response' if kind=='thread' else 'thread','page',self.response.pk if kind=='thread' else self.thread.pk)]:
                self.assertEqual(self.client.post(add,{'target_url':bad}).status_code,400)
            self.assertContains(self.client.get(route(kind,'list-detail',item.pk)),payload['target_url'])
            self.assertEqual(self.client.post(route(kind,'list-rename',item.pk),{'name':'Renamed'}).status_code,200)
            self.client.force_login(self.other)
            for action in ['list-rename','list-add','list-delete']:
                self.assertEqual(self.client.post(route(kind,action,item.pk),{'name':'hijack','target_url':payload['target_url']}).status_code,404)
            self.client.force_login(self.owner)
            self.assertEqual(self.client.post(route(kind,'list-remove',item.pk,item.references.get().pk)).status_code,200)
            self.assertEqual(item.references.count(),0)
            self.assertEqual(self.client.post(route(kind,'list-delete',item.pk)).status_code,200)
            self.assertTrue(type(target).objects.filter(pk=target.pk).exists())

    def test_foreign_rated_and_listed_account_detail_preserves_scope_and_policy(self):
        url=reverse('accounts:thread-detail',args=[self.owner.username,self.thread.pk])
        # Response creation already relates this Thread to the Account.
        self.assertEqual(self.client.get(url).status_code,200)
        other=Thread.objects.create(creator=self.other,title='Only a saved Thread')
        self.assertEqual(self.client.get(reverse('accounts:thread-detail',args=[self.owner.username,other.pk])).status_code,404)
        ThreadListReference.objects.create(thread_list=self.thread_list,target=other)
        self.client.logout()
        denied=self.client.get(reverse('accounts:thread-detail',args=[self.owner.username,other.pk]))
        self.assertEqual(denied.status_code,200);self.assertNotContains(denied,'data-content-feedback')

    def test_account_tabs_all_names_ten_items_and_no_fake_bookmark(self):
        for i in range(11):
            thread=Thread.objects.create(creator=self.other,title=f'Saved {i:02}')
            ThreadAccessRule.objects.create(thread=thread,capability='view',audience='guest')
            ThreadPost.objects.create(thread=thread,number=2,body='Listed response',creator=self.other)
            ThreadRating.objects.create(author=self.owner,target=thread,sentiment='fav')
            ResponseRating.objects.create(author=self.owner,target=thread.posts.get(),sentiment='bad')
        for kind in ['thread','response']:
            for i in range(24):KINDS[kind].model.objects.create(owner=self.owner,name=f'{kind} tab {i:02}',submission_id=uuid4())
            url=reverse('accounts:'+kind+'-pane',args=[self.owner.username]);tab='fav' if kind=='thread' else 'bad'
            pagekey='created_page' if kind=='thread' else 'response_page'
            result=self.client.get(url,{'tab':tab,pagekey:2});tabs=result.context['tabs']
            self.assertEqual(len(tabs),28);self.assertEqual(len(next(t['page'] for t in tabs if t['key']==tab)),1)
            self.assertNotContains(result,'bookmark');self.assertContains(result,f'{kind} tab 23')
            self.assertNotContains(result,'Listを作成')
            bad=self.client.get(url,{'tab':'invalid',pagekey:'bad'});self.assertEqual(bad.context['active_tab'],'created')

    def test_denied_response_deduplication_no_body_number_time_or_count(self):
        for post in [self.secret,self.secret2]:
            ResponseRating.objects.create(author=self.owner,target=post,sentiment='fav')
            ResponseListReference.objects.create(response_list=self.response_list,target=post)
        self.client.logout()
        for tab in ['created','fav','list-'+str(self.response_list.pk)]:
            result=self.client.get(reverse('accounts:response-pane',args=[self.owner.username]),{'tab':tab})
            items=next(t['page'] for t in result.context['tabs'] if t['key']==tab)
            self.assertEqual(sum(p.thread_id==self.private.pk for p in items),1)
            self.assertNotContains(result,'NEVER_EXPOSE');self.assertNotContains(result,'data-response-post="3"')
        listed=self.client.get(route('response','list-detail',self.response_list.pk))
        self.assertNotContains(listed,'NEVER_EXPOSE');self.assertNotContains(listed,'Response #3')

    def test_room_mute_keeps_original_response_semantics_and_does_not_change_policy(self):
        from rooms.services import create_room
        from rooms.models import Board, RoomMute
        room,_=create_room(submission_id=uuid4(),owner=self.other,name='Muted original Room',description='',latitude='35',longitude='139')
        board=Board.objects.filter(placement__collection__room=room).order_by('pk').first()
        self.assertIsNotNone(board)
        ThreadPlacement.objects.create(thread=self.thread,kind='board',board=board)
        RoomMute.objects.create(muter=self.owner,room=room)
        ThreadRating.objects.create(author=self.owner,target=self.thread,sentiment='fav')
        ResponseRating.objects.create(author=self.owner,target=self.response,sentiment='bad')
        thread=self.client.get(reverse('accounts:thread-pane',args=[self.owner.username]),{'tab':'fav'})
        self.assertEqual(len(next(t['page'] for t in thread.context['tabs'] if t['key']=='fav')),0)
        self.assertNotContains(self.client.get(route('thread','list-detail',self.thread_list.pk)),'content-reference-summary')
        response=self.client.get(reverse('accounts:response-pane',args=[self.owner.username]),{'tab':'bad'})
        self.assertEqual(len(next(t['page'] for t in response.context['tabs'] if t['key']=='bad')),1)
        self.assertEqual(self.client.get(route('thread','pane',self.thread.pk)).status_code,200)
        self.assertTrue(self.thread.allows(self.owner,'view'))

    def test_deleted_targets_leave_removable_placeholder_and_remove_ratings(self):
        ThreadRating.objects.create(author=self.owner,target=self.thread,sentiment='fav')
        ResponseRating.objects.create(author=self.owner,target=self.response,sentiment='bad')
        tid=self.thread.pk;rid=self.response.pk;self.thread.delete()
        self.assertEqual(ThreadRating.objects.count(),0);self.assertEqual(ResponseRating.objects.count(),0)
        for kind,item,targetid in [('thread',self.thread_list,tid),('response',self.response_list,rid)]:
            self.assertContains(self.client.get(route(kind,'list-detail',item.pk)),'削除済み・公開参照不可')
            self.assertContains(self.client.get(reverse('accounts:'+kind+'-pane',args=[self.owner.username]),{'tab':'list-'+str(item.pk)}),'削除済み・公開参照不可')
            self.assertEqual(self.client.post(route(kind,'rating',targetid),{'sentiment':'fav'}).status_code,404)
            ref=item.references.get();self.assertIsNone(ref.target)
            self.assertEqual(self.client.post(route(kind,'list-remove',item.pk,ref.pk)).status_code,200)

    def test_mute_filters_references_and_ratings_without_changing_acl_or_storage(self):
        ThreadRating.objects.create(author=self.owner,target=self.thread,sentiment='fav')
        ResponseRating.objects.create(author=self.owner,target=self.response,sentiment='fav')
        AccountMute.objects.create(muter=self.owner,muted_account=self.other)
        for kind,item,target in [('thread',self.thread_list,self.thread),('response',self.response_list,self.response)]:
            result=self.client.get(reverse('accounts:'+kind+'-pane',args=[self.owner.username]),{'tab':'fav'})
            self.assertEqual(len(next(t['page'] for t in result.context['tabs'] if t['key']=='fav')),0)
            self.assertNotContains(self.client.get(route(kind,'list-detail',item.pk)),'content-reference-summary')
            self.assertEqual(item.references.count(),1);self.assertEqual(KINDS[kind].rating.objects.count(),1)
            self.assertEqual(self.client.post(route(kind,'rating',target.pk),{'sentiment':'bad'}).status_code,200)
        self.assertContains(self.client.get(route('thread','pane',self.thread.pk)),'data-muted-response')
        self.assertNotContains(self.client.get(route('thread','pane',self.thread.pk)),'data-content-kind="thread"')


class ConversationFeedbackBrowserTests(StaticLiveServerTestCase):
    static_handler=SharedSQLiteStaticFilesHandler
    def setUp(self):
        seed(self);self.client.force_login(self.owner)
        self.session=self.client.cookies[settings.SESSION_COOKIE_NAME].value
        self.output=Path(settings.BASE_DIR)/'.artifacts/conversation-feedback';self.output.mkdir(parents=True,exist_ok=True)

    def test_desktop_mobile_rating_picker_lists_history_and_guest_policy(self):
        from playwright.sync_api import sync_playwright
        from scripts.browser_smoke import wait_for_trail_count
        evidence=[]
        with sync_playwright() as p:
            browser=p.chromium.launch(channel='msedge',headless=True)
            try:
                for name,size in [('desktop',{'width':1280,'height':800}),('mobile',{'width':390,'height':844})]:
                    context=browser.new_context(viewport=size,is_mobile=name=='mobile',has_touch=name=='mobile')
                    context.add_cookies([{'name':settings.SESSION_COOKIE_NAME,'value':self.session,'url':self.live_server_url}])
                    page=context.new_page();page.set_default_timeout(8000);errors=[]
                    page.on('pageerror',lambda e:errors.append(str(e)));page.on('console',lambda e:errors.append(e.text) if e.type=='error' and not e.location.get('url','').endswith('/favicon.ico') else None)
                    page.goto(self.live_server_url+route('thread','page',self.thread.pk))
                    body=page.locator('.ui-workspace-trail-pane').last
                    feedback=body.locator('[data-content-kind="thread"]');feedback.wait_for()
                    if name=='mobile':
                        self.assertTrue(page.evaluate("matchMedia('(pointer: coarse)').matches"))
                        dimensions=feedback.locator('[data-content-rate], [data-account-list-picker-url]').evaluate_all('els=>els.map(el=>({width:el.getBoundingClientRect().width,height:el.getBoundingClientRect().height}))')
                        self.assertTrue(all(row['width']>=43.99 and row['height']>=43.99 for row in dimensions),dimensions)
                    page.evaluate("navigator.clipboard.writeText=async value=>{window.qaSharedUrl=value;}")
                    self.assertEqual(feedback.locator('.account-list-share, [data-list-share-url], [data-copy-list-url]').count(),0)
                    count=[]
                    def track(request):
                        if request.method=='POST' and request.url.endswith(route('thread','rating',self.thread.pk)):count.append(request.url)
                    page.on('request',track)
                    feedback.locator('[data-content-rate="fav"]').dblclick()
                    page.wait_for_function("document.querySelector('.ui-workspace-trail-pane [data-content-kind=thread]').dataset.contentSentiment==='fav'")
                    self.assertEqual(len(count),1)
                    feedback.locator('[data-content-rate="bad"]').click()
                    page.wait_for_function("document.querySelector('.ui-workspace-trail-pane [data-content-kind=thread]').dataset.contentSentiment==='bad'")
                    feedback.locator('[data-content-rate="bad"]').click()
                    page.wait_for_function("document.querySelector('.ui-workspace-trail-pane [data-content-kind=thread]').dataset.contentSentiment===''")
                    feedback.locator('[data-content-rate="fav"]').click()
                    page.wait_for_function("document.querySelector('.ui-workspace-trail-pane [data-content-kind=thread]').dataset.contentSentiment==='fav'")
                    feedback.locator('[data-account-list-picker-url]').click()
                    picker=page.locator('.ui-workspace-trail-pane').last
                    picker.locator('.account-list-share summary').click()
                    picker.locator('[data-copy-list-url]').click()
                    self.assertEqual(page.evaluate('window.qaSharedUrl'),self.live_server_url+route('thread','page',self.thread.pk))
                    picker.locator('.account-list-share summary').click()
                    picker.locator('[data-list-operation="create"] input[name=name]').fill(f'{name} Saved Thread')
                    picker.locator('[data-list-operation="create"] [type=submit]').click()
                    listing=page.locator('.ui-workspace-trail-pane').last
                    listing.locator('[data-account-list-detail]').wait_for()
                    self.assertEqual(listing.locator('.content-reference-summary').count(),1)
                    page.goto(self.live_server_url+reverse('accounts:detail',args=[self.owner.username])+'?pane=thread&tab=fav')
                    tabs=page.locator('[data-thread-pane-container]');tabs.locator('[data-ui-tab-panel="fav"] [data-thread-detail]').wait_for()
                    self.assertEqual(tabs.locator('[data-ui-tab="fav"]').get_attribute('aria-selected'),'true')
                    tabs.locator('[data-ui-tab-panel="fav"] [data-thread-detail]').click()
                    detail=page.locator('.account-thread-detail-pane');detail.locator('[data-content-kind="thread"]').wait_for()
                    detail.locator('[data-content-kind="thread"] [data-content-rate="bad"]').click()
                    page.wait_for_function("document.querySelector('.account-thread-detail-pane [data-content-kind=thread]').dataset.contentSentiment==='bad'")
                    page.wait_for_function("document.querySelectorAll('[data-thread-pane-container] [data-ui-tab-panel=fav] [data-thread-detail]').length===0")
                    page.locator('#close-account-thread-detail').click()
                    self.assertEqual(tabs.locator('[data-ui-tab="fav"]').get_attribute('aria-selected'),'true')
                    self.assertEqual(tabs.locator('[data-ui-tab-panel="fav"] [data-thread-detail]').count(),0)
                    tabs.locator('[data-ui-tab="bad"]').click()
                    page.wait_for_url('**tab=bad*')
                    tabs.locator('[data-ui-tab-panel="bad"] [data-thread-detail]').click()
                    detail.locator('[data-content-kind="response"]').wait_for()
                    detail.locator('[data-content-kind="response"] [data-account-list-picker-url]').click()
                    page.locator('.ui-workspace-trail-pane').last.locator('[data-list-operation="create"] input[name=name]').fill(f'{name} Saved Response')
                    page.locator('.ui-workspace-trail-pane').last.locator('[data-list-operation="create"] [type=submit]').click()
                    page.locator('.ui-workspace-trail-pane').last.locator('[data-account-list-detail]').wait_for()
                    wait_for_trail_count(page, page.locator('.ui-workspace-trail-pane').count())
                    page.screenshot(path=str(self.output/f'{name}-list.png'),full_page=True)
                    page.goto(self.live_server_url+route('response','page',self.response.pk))
                    page.locator('.ui-workspace-trail-pane [data-target-post="2"]').wait_for()
                    wait_for_trail_count(page, page.locator('.ui-workspace-trail-pane').count())
                    page.screenshot(path=str(self.output/f'{name}-response.png'),full_page=True)
                    if name=='mobile':
                        canonical=page.locator('.ui-workspace-trail-pane').last
                        canonical.locator('.thread-reply-form textarea').fill('Canonical Response reply')
                        canonical.locator('.thread-reply-form [type=submit]').click()
                        canonical.locator('[data-thread-post-number="3"]').wait_for()
                        self.assertIn('Canonical Response reply',canonical.inner_text())
                        self.assertEqual(canonical.locator('[data-thread-detail-pane]').get_attribute('data-target-post'),'2')
                    self.assertFalse(errors,errors)
                    context.close()
                    guest=browser.new_context(viewport=size);gp=guest.new_page();guest_errors=[]
                    gp.on('pageerror',lambda e:guest_errors.append(str(e)))
                    gp.goto(self.live_server_url+route('thread','page',self.thread.pk))
                    gp.locator('.ui-workspace-trail-pane [data-content-kind="thread"]').wait_for()
                    self.assertTrue(gp.locator('.ui-workspace-trail-pane [data-content-kind="thread"] [data-content-rate="fav"]').is_disabled())
                    gp.goto(self.live_server_url+route('response','page',self.secret.pk))
                    gp.locator('.ui-workspace-trail-pane .thread-detail').wait_for()
                    self.assertNotIn('NEVER_EXPOSE',gp.locator('.reference-page').inner_text())
                    self.assertEqual(gp.locator('[data-content-feedback]').count(),0)
                    wait_for_trail_count(gp, gp.locator('.ui-workspace-trail-pane').count())
                    gp.screenshot(path=str(self.output/f'{name}-guest-denied.png'),full_page=True)
                    self.assertFalse(guest_errors);guest.close()
                    evidence.append({'viewport':name,'pageErrors':0,'consoleErrors':0,'doubleClickPosts':1,'guestPolicy':'passed'})
            finally:browser.close()
        (self.output/'browser.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')

    def test_owner_other_guest_native_nested_categories_and_history(self):
        from playwright.sync_api import sync_playwright, expect
        from scripts.browser_smoke import wait_for_trail_count
        other_client=Client();other_client.force_login(self.other)
        sessions={'owner':self.session,'other':other_client.cookies[settings.SESSION_COOKIE_NAME].value,'guest':None}
        # Seed outside browser I/O: shared SQLite cannot query in Playwright's sync loop.
        ThreadRating.objects.create(author=self.owner,target=self.thread,sentiment='fav')
        ResponseRating.objects.create(author=self.owner,target=self.response,sentiment='bad')
        rows=[]
        with sync_playwright() as p:
            browser=p.chromium.launch(channel='msedge',headless=True)
            try:
                for viewport,size in [('desktop',{'width':1280,'height':800}),('mobile',{'width':390,'height':844})]:
                    for actor,session in sessions.items():
                        for origin in ['native','nested']:
                            context=browser.new_context(viewport=size,is_mobile=viewport=='mobile',has_touch=viewport=='mobile')
                            if session:context.add_cookies([{'name':settings.SESSION_COOKIE_NAME,'value':session,'url':self.live_server_url}])
                            page=context.new_page();page.set_default_timeout(8000);errors=[]
                            page.on('pageerror',lambda e:errors.append(str(e)))
                            page.on('console',lambda e:errors.append(e.text) if e.type=='error' and not e.location.get('url','').endswith('/favicon.ico') else None)
                            if origin=='native':
                                page.goto(self.live_server_url+reverse('accounts:detail',args=[self.owner.username]))
                                account=page.locator('.account-page')
                            else:
                                page.goto(self.live_server_url+route('thread','page',self.thread.pk))
                                page.locator('.ui-workspace-trail-pane [data-thread-post-number="2"] a').first.click()
                                account=page.locator('.ui-workspace-trail-pane [data-account-fragment]').last
                                account.wait_for()
                            account.locator('[data-open-account-threads]').click()
                            listing=page.locator('[data-integrated-kind="thread"]').last
                            listing.locator('[data-ui-tab="fav"]').click()
                            expect(listing.locator('[data-ui-tab="fav"]')).to_have_attribute('aria-selected','true')
                            listing.locator('[data-ui-tab-panel="fav"] [data-thread-detail]').click()
                            detail=page.locator('.account-thread-detail-pane') if origin=='native' else page.locator('.ui-workspace-trail-pane').last
                            detail.locator('[data-content-kind="thread"]').wait_for()
                            if actor=='guest':expect(detail.locator('[data-content-kind="thread"] [data-content-rate="fav"]')).to_be_disabled()
                            if actor=='owner':
                                feedback=detail.locator('[data-content-kind="thread"]')
                                feedback.locator('[data-content-rate="bad"]').click()
                                expect(listing.locator('[data-ui-tab-panel="fav"] [data-thread-detail]')).to_have_count(0)
                                feedback.locator('[data-content-rate="fav"]').click()
                                expect(listing.locator('[data-ui-tab-panel="fav"] [data-thread-detail]')).to_have_count(1)
                            close=page.locator('#close-account-thread-detail') if origin=='native' else detail.locator('.ui-workspace-trail-header .icon-button')
                            close.click()
                            expect(listing.locator('[data-ui-tab="fav"]')).to_have_attribute('aria-selected','true')
                            listing.locator('[data-ui-tab="list-'+str(self.thread_list.pk)+'"]').click()
                            expect(listing.locator('[data-ui-tab-panel="list-'+str(self.thread_list.pk)+'"] [data-thread-detail]')).to_have_count(1)
                            if origin=='native':
                                page.go_back();expect(listing.locator('[data-ui-tab="fav"]')).to_have_attribute('aria-selected','true')
                                page.go_forward();expect(listing.locator('[data-ui-tab="list-'+str(self.thread_list.pk)+'"]')).to_have_attribute('aria-selected','true')
                            if origin=='native':page.locator('#close-account-list').click()
                            else:page.locator('.ui-workspace-trail-pane').last.locator('.ui-workspace-trail-header .icon-button').click()
                            account.locator('[data-open-account-responses]').click()
                            response=page.locator('[data-integrated-kind="response"]').last
                            response.locator('[data-ui-tab="bad"]').click()
                            response.locator('[data-ui-tab-panel="bad"] [data-response-thread]').click()
                            detail=page.locator('.account-thread-detail-pane') if origin=='native' else page.locator('.ui-workspace-trail-pane').last
                            detail.locator('[data-thread-post-number="2"]').wait_for()
                            if actor=='owner':
                                feedback=detail.locator('[data-content-kind="response"]')
                                feedback.locator('[data-content-rate="fav"]').click()
                                expect(response.locator('[data-ui-tab-panel="bad"] [data-response-thread]')).to_have_count(0)
                                feedback.locator('[data-content-rate="bad"]').click()
                                expect(response.locator('[data-ui-tab-panel="bad"] [data-response-thread]')).to_have_count(1)
                            self.assertIn('Public reply body',detail.inner_text())
                            self.assertNotIn('NEVER_EXPOSE',detail.inner_text())
                            wait_for_trail_count(page, page.locator('.ui-workspace-trail-pane').count())
                            page.screenshot(path=str(self.output/f'{viewport}-{actor}-{origin}.png'),full_page=True)
                            self.assertFalse(errors,errors)
                            rows.append({'viewport':viewport,'actor':actor,'origin':origin,'pageErrors':0,'consoleErrors':0})
                            context.close()
            finally:browser.close()
        (self.output/'matrix.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')

    def test_required_browser_smoke_against_isolated_live_server(self):
        import sys
        from rooms.services import create_room
        from rooms.models import Board
        # Full smoke needs representative visible map, Account and Room sources.
        room,_=create_room(submission_id=uuid4(),owner=self.owner,name='Conversation Smoke Room',description='',latitude='35.681236',longitude='139.767125')
        ThreadPlacement.objects.create(thread=self.thread,kind='niimap',latitude='35.681236',longitude='139.767125')
        for board in Board.objects.filter(placement__collection__room=room).order_by('pk'):
            placed=Thread.objects.create(creator=self.owner,title='Conversation Smoke Thread '+str(board.pk))
            ThreadPost.objects.create(thread=placed,creator=self.owner,number=1,body='Smoke first body')
            ThreadPost.objects.create(thread=placed,creator=self.other,number=2,body='Smoke reply body')
            ThreadAccessRule.objects.bulk_create([ThreadAccessRule(thread=placed,capability=c,audience=a) for c in ['view','write'] for a in ['guest','account']])
            ThreadPlacement.objects.create(thread=placed,kind='board',board=board)
        result=subprocess.run([sys.executable,str(Path(settings.BASE_DIR)/'scripts/browser_smoke.py'),'--base-url',self.live_server_url],cwd=settings.BASE_DIR,capture_output=True,text=True,encoding='utf-8')
        (self.output/'smoke.log').write_text(result.stdout+'\n'+result.stderr,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        results,_=json.JSONDecoder().raw_decode(result.stdout.lstrip())
        self.assertEqual(len(results),2)
        for viewport in results:
            self.assertEqual(len(viewport['checks']),17,viewport)
            self.assertEqual(viewport['warnings'],[],viewport)
            self.assertEqual(viewport['browser_errors'],[],viewport)
