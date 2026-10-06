"""AccountPage pagination and category retention; disposable SQLite only."""
import json
import subprocess
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client, TestCase
from django.urls import reverse

from accounts.content_lists import KINDS
from accounts.models import AccountList, AccountListReference, AccountReview, AccountMute
from events.models import Thread, ThreadPost, ThreadAccessRule, ThreadPlacement
from interfaces.account_applications import change_application
from interfaces.models import InterfaceDraft, InterfaceList
from interfaces.services import publish_draft, publish_field_definition
from rooms.models import Board, BoardPlacement, BoardListReference
from scripts.browser_test_server import SharedSQLiteStaticFilesHandler


def seed(case):
    case.assertEqual(settings.DATABASES['default']['ENGINE'], 'django.db.backends.sqlite3')
    user = get_user_model()
    case.owner = user.objects.create_user('page_owner')
    case.other = user.objects.create_user('page_other')
    case.people = AccountList.objects.create(owner=case.owner, name='Paged People', submission_id=uuid4())
    case.modules = InterfaceList.objects.create(owner=case.owner, name='Paged Module', submission_id=uuid4())
    for index in range(24):
        AccountList.objects.create(owner=case.owner, name=f'People Tab {index:02}', submission_id=uuid4())
        InterfaceList.objects.create(owner=case.owner, name=f'Module Tab {index:02}', submission_id=uuid4())
    case.collection = case.owner.collections.get(name='Main')
    case.board = Board.objects.get(placement__collection=case.collection)
    case.targets = []
    for index in range(21):
        target = user.objects.create_user(f'page_person_{index:02}')
        case.targets.append(target)
        AccountListReference.objects.create(account_list=case.people, target=target)
        AccountReview.objects.create(author=case.owner, target=target, sentiment='love', body='Public review')
        source = Board.objects.get(placement__collection__account=target)
        BoardListReference.objects.create(board_list=case.collection, target=source)
        placed = Board.objects.create(creator=case.owner, name=f'Placed {index:02}')
        BoardPlacement.objects.create(board=placed, kind=BoardPlacement.COLLECTION, collection=case.collection)
        room_if, _ = publish_draft(InterfaceDraft.objects.create(creator=case.owner, kind='room', name=f'Room IF {index:02}').pk)
        KINDS['interface'].reference.objects.create(interface_list=case.modules, target=room_if)
        field, _ = publish_field_definition(creator=case.owner, name=f'Field {index:02}', field_type='short_text')
        change_application(case.owner, {'operation':'add_field', 'id':field.pk, 'values':{str(field.key):['QA value']}})
    from rooms.services import create_room
    from rooms.models import RoomReview
    case.room, _ = create_room(submission_id=uuid4(), owner=case.owner, name='Category Room', description='', latitude='35', longitude='139')
    RoomReview.objects.create(author=case.owner, target=case.room, sentiment='love', body='Public Room Review')
    case.threads = []
    for index in range(21):
        thread = Thread.objects.create(creator=case.owner, title=f'Paged Thread {index:02}')
        ThreadPost.objects.create(thread=thread, creator=case.owner, number=1, body='First')
        ThreadPost.objects.create(thread=thread, creator=case.owner, number=2, body='Response')
        ThreadPlacement.objects.create(thread=thread, kind=ThreadPlacement.BOARD, board=case.board)
        ThreadAccessRule.objects.bulk_create([ThreadAccessRule(thread=thread, capability=c, audience=a) for c in ['view','write'] for a in ['guest','account']])
        case.threads.append(thread)


class AccountListConsistencyTests(TestCase):
    def setUp(self): seed(self)

    def test_people_all_tabs_but_twenty_visible_references_and_reviews(self):
        url=reverse('accounts:list-index',args=[self.owner.username])
        first=self.client.get(url)
        self.assertEqual(len(first.context['people_lists']),25)
        self.assertEqual(len(first.context['loved_accounts']),20)
        second=self.client.get(url,{'people_tab':'love','page':2})
        self.assertEqual(len(second.context['loved_accounts']),1)
        page=self.client.get(url,{'people_tab':'list-'+str(self.people.pk),'page':2})
        self.assertEqual(len(page.context['people_lists'][0].visible_references),1)
        self.assertContains(page,'People Tab 23')
        AccountMute.objects.create(muter=self.other,muted_account=self.targets[0])
        self.client.force_login(self.other)
        filtered=self.client.get(url)
        self.assertEqual(filtered.context['loved_accounts'].paginator.count,20)
        self.assertEqual(self.people.references.count(),21)

    def test_room_if_paginates_within_subtype_and_preserves_future_tabs(self):
        url=reverse('accounts:module-pane',args=[self.owner.username])
        page=self.client.get(url,{'type':'interface','subtype':'room','collection':'list-'+str(self.modules.pk),'page':2})
        group=next(g for g in page.context['module_collections'] if g.get('list_id')==self.modules.pk)
        room=next(c for c in group['pages'] if (c['type'],c['subtype'])==('interface','room'))
        self.assertEqual(room['page'].paginator.count,21);self.assertEqual(len(room['page']),1)
        self.assertEqual(len(page.context['module_collections']),28)
        for label in ['RoomIF','ComputedField','Action','ThreadPost','Room','Module Tab 23']:self.assertContains(page,label)
        field=self.client.get(url).context['module_collections'][0]['pages'][0]['page']
        self.assertEqual(len(field),20)

    def test_board_reference_and_placement_pages_are_independent(self):
        url=reverse('accounts:boards',args=[self.owner.username])
        page=self.client.get(url,{'collection':self.collection.pk,'page':2,'boards_page':2})
        group=next(c for c in page.context['collections'] if c.pk==self.collection.pk)
        self.assertEqual(group.board_count,22)
        self.assertEqual(len(group.reference_summaries),1);self.assertEqual(len(group.visible_boards),2)
        self.assertContains(page,'boards_page=2');self.assertContains(page,'page=2')
        detail=self.client.get(reverse('accounts:board-threads',args=[self.owner.username,self.board.pk]),{'thread_page':2})
        self.assertEqual(len(detail.context['threads']),1)

    def test_public_applied_is_paged_owner_editor_is_complete(self):
        url=reverse('accounts:applied',args=[self.owner.username])
        first=self.client.get(url);self.assertEqual(len(first.context['applied']['fields']),20)
        second=self.client.get(url,{'tab':'applied-field','page':2});self.assertEqual(len(second.context['applied']['fields']),1)
        self.client.force_login(self.owner)
        editor=self.client.get(url,{'edit':1,'page':2});self.assertEqual(len(editor.context['applied']['fields']),21)
        self.assertContains(editor,'data-add-applied="field"')

    def test_gets_do_not_change_models_and_invalid_page_uses_existing_paginator(self):
        from django.apps import apps
        models=[m for m in apps.get_models() if m._meta.app_label in {'accounts','interfaces','rooms','events'}]
        before={m:list(m.objects.order_by('pk').values()) for m in models}
        for name in ['list-index','module-pane','boards','applied','thread-pane','response-pane']:
            response=self.client.get(reverse('accounts:'+name,args=[self.owner.username]),{'page':'bad','created_page':'bad','response_page':'bad'})
            self.assertEqual(response.status_code,200)
        for model,rows in before.items():self.assertEqual(list(model.objects.order_by('pk').values()),rows,model.__name__)


class AccountListConsistencyBrowserTests(StaticLiveServerTestCase):
    static_handler=SharedSQLiteStaticFilesHandler
    def setUp(self):seed(self)

    def test_categories_pages_children_and_reload_roles_pc_mobile(self):
        from playwright.sync_api import sync_playwright,expect
        from scripts.browser_smoke import wait_for_trail_count
        out=Path(settings.BASE_DIR)/'.artifacts/account-list-consistency';out.mkdir(parents=True,exist_ok=True)
        sessions={}
        for role,user in [('owner',self.owner),('other',self.other)]:
            client=Client();client.force_login(user);sessions[role]=client.cookies[settings.SESSION_COOKIE_NAME].value
        rows=[]
        with sync_playwright() as pw:
            browser=pw.chromium.launch(channel='msedge',headless=True)
            try:
                for viewport,size in [('desktop',{'width':1280,'height':900}),('mobile',{'width':390,'height':844})]:
                    for role in ['owner','other','guest']:
                        context=browser.new_context(viewport=size,is_mobile=viewport=='mobile',has_touch=viewport=='mobile')
                        if role in sessions:context.add_cookies([{'name':settings.SESSION_COOKIE_NAME,'value':sessions[role],'url':self.live_server_url}])
                        page=context.new_page();page.set_default_timeout(10000);errors=[]
                        page.on('pageerror',lambda e:errors.append(str(e)))
                        page.on('console',lambda m:errors.append(m.text) if m.type=='error' and not m.location.get('url','').endswith('/favicon.ico') else None)
                        try:
                            for nested in [False,True]:
                                def open_feature(action):
                                    url=reverse('accounts:detail',args=[self.owner.username])
                                    page.goto(self.live_server_url+('/' if nested else url))
                                    if nested:
                                        page.evaluate('url=>NiixyWorkspaceTrail.open(url)',url);wait_for_trail_count(page,1)
                                        origin=page.locator('[data-account-fragment]')
                                    else:origin=page.locator('.account-overview-pane')
                                    origin.locator('[data-open-account-'+action+']').evaluate('el=>el.click()')
                                    wait_for_trail_count(page,2 if nested else 0)
                                base=2 if nested else 0
                                open_feature('people')
                                people=page.locator('[data-account-lists-index]');expect(people.locator('[data-list-tab-id]')).to_have_count(25)
                                people.locator(f'[data-ui-tab="list-{self.people.pk}"]').click()
                                panel=people.locator(f'[data-ui-tab-panel="list-{self.people.pk}"]')
                                expect(panel.locator('.ui-summary-item')).to_have_count(20)
                                panel.locator('[data-summary-page]').filter(has_text='次へ').click()
                                expect(panel.locator('.ui-summary-item')).to_have_count(1)
                                panel.locator('.ui-summary-item').click();wait_for_trail_count(page,base+1)
                                people.locator('[data-ui-tab=hate]').evaluate('el=>el.click()');wait_for_trail_count(page,base)
                                expect(page).to_have_url(__import__('re').compile('people_tab=hate'))
                                page.reload();expect(page.locator('[data-ui-tab=hate]')).to_have_attribute('aria-selected','true')
                                open_feature('modules')
                                modules=page.locator('[data-module-public]');expect(modules.locator('[data-module-list-id]')).to_have_count(25)
                                modules.locator('[data-module-type=interface]').click();modules.locator('[data-module-subtypes=interface] [data-module-subtype=room]').click()
                                modules.locator(f'[data-module-collection="list-{self.modules.pk}"]').click()
                                panel=modules.locator(f'[data-module-public-panel="list-{self.modules.pk}"]')
                                expect(panel.locator('.content-reference-summary:visible')).to_have_count(20)
                                panel.locator('[data-summary-page]:visible').filter(has_text='次へ').click()
                                expect(panel.locator('.content-reference-summary:visible')).to_have_count(1)
                                panel.locator('.content-reference-summary:visible').click();wait_for_trail_count(page,base+1)
                                modules.locator('[data-module-type=element]').evaluate('el=>el.click()');wait_for_trail_count(page,base)
                                modules.locator('[data-module-subtype=action]').click();expect(panel).to_contain_text('表示できるModuleはありません')
                                modules.locator('[data-module-type=interface]').click();modules.locator('[data-module-subtypes=interface] [data-module-subtype=room]').click()
                                expect(page).to_have_url(__import__('re').compile('subtype=room'))
                                page.screenshot(path=out/f'{viewport}-{role}-{nested}-room-if.png')
                                page.reload();expect(page.locator('[data-module-subtypes=interface] [data-module-subtype=room]')).to_have_attribute('aria-selected','true')
                                open_feature('boards')
                                boards=page.locator('[data-integrated-kind=board]');boards.locator(f'[data-collection-id="{self.collection.pk}"]').click()
                                panel=boards.locator(f'[data-collection-panel-id="{self.collection.pk}"]')
                                if role=='owner':
                                    panel.locator('[data-collection-create-toggle]').click();name=panel.locator('[data-board-action-kind=create] [name=name]')
                                    name.fill('UNSENT BOARD');name.evaluate('el=>window.retainedBoardInput=el')
                                panel.locator('[data-collection-references] [data-summary-page]').filter(has_text='次へ').click()
                                expect(panel.locator('[data-collection-references] .content-reference-summary')).to_have_count(1)
                                panel.locator('[data-collection-boards] [data-summary-page]').filter(has_text='次へ').click()
                                expect(panel.locator('[data-open-board]')).to_have_count(2)
                                expect(panel.locator('[data-collection-references] .content-reference-summary')).to_have_count(1)
                                if role=='owner':
                                    expect(name).to_have_value('UNSENT BOARD');self.assertTrue(name.evaluate('el=>el===window.retainedBoardInput'))
                                panel.locator(f'[data-open-board="{self.board.pk}"]').click();wait_for_trail_count(page,base+1)
                                results=page.locator('[data-board-thread-results]');expect(results.locator('[data-room-thread]')).to_have_count(20)
                                results.locator('[data-summary-page]').filter(has_text='次へ').click();expect(results.locator('[data-room-thread]')).to_have_count(1)
                                boards.locator('[data-ui-tab=fav]').evaluate('el=>el.click()');wait_for_trail_count(page,base)
                                expect(page).to_have_url(__import__('re').compile('tab=fav'))
                                for action,param in [('threads','created_page'),('responses','response_page')]:
                                    open_feature(action)
                                    content=page.locator('.account-feature-content').last;expect(content.locator('[data-thread-detail], [data-response-thread]')).to_have_count(10)
                                    content.locator('[data-pane-pagination]').filter(has_text='次へ').click();expect(content.locator('[data-thread-detail], [data-response-thread]')).to_have_count(10)
                                    expect(page).to_have_url(__import__('re').compile(param+'=2'))
                                    content.locator('[data-thread-detail], [data-response-thread]').first.click()
                                    if nested:wait_for_trail_count(page,base+1)
                                    else:page.wait_for_function("document.querySelector('.account-track').dataset.uiWorkspaceStage==='detail'")
                                    content.locator('[data-ui-tab=fav]').evaluate('el=>el.click()');wait_for_trail_count(page,base)
                                    expect(page).to_have_url(__import__('re').compile('tab=fav'))
                                    page.reload();expect(page.locator('[data-ui-tab=fav]')).to_have_attribute('aria-selected','true')
                                    if not nested:
                                        page.locator('#account-page-identity').click()
                                        page.go_back();expect(page.locator('[data-ui-tab=fav]')).to_have_attribute('aria-selected','true')
                                        page.go_forward();page.wait_for_function("document.querySelector('.account-track').dataset.uiWorkspaceStage==='overview'")
                                open_feature('rooms')
                                content=page.locator('.account-feature-content').last
                                content.locator('[data-ui-tab=love]').click()
                                content.locator('[data-account-room-detail]:visible').filter(has_text='Category Room').click();wait_for_trail_count(page,base+1)
                                content.locator('[data-ui-tab=hate]').evaluate('el=>el.click()');wait_for_trail_count(page,base)
                                expect(page).to_have_url(__import__('re').compile('room_tab=hate'))
                                page.reload();expect(page.locator('[data-ui-tab=hate]')).to_have_attribute('aria-selected','true')
                                open_feature('account-if')
                                content=page.locator('.applied-list-content');expect(content.locator('[data-ui-tab-panel=applied-field] .ui-summary-item')).to_have_count(20)
                                content.locator('[data-summary-page]:visible').filter(has_text='次へ').click();expect(content.locator('[data-ui-tab-panel=applied-field] .ui-summary-item')).to_have_count(1)
                                content.locator('[data-ui-tab=applied-interface]').click();expect(page).to_have_url(__import__('re').compile('tab=applied-interface'))
                                page.reload();expect(page.locator('[data-ui-tab=applied-interface]')).to_have_attribute('aria-selected','true')
                                rows.append({'viewport':viewport,'role':role,'nested':nested,'checks':'People/Module/Board/Thread/Applied paging, category child cleanup, reload, owner input'})
                            self.assertEqual(errors,[])
                        finally:context.close()
            finally:browser.close()
        (out/'matrix.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')

    def test_nested_query_only_pagination_before_and_after(self):
        from playwright.sync_api import sync_playwright,expect
        from scripts.browser_smoke import wait_for_trail_count
        old=subprocess.check_output(['git','show','d5b53a8:static/shared/workspace_trail.js'],cwd=settings.BASE_DIR,text=True,encoding='utf-8')
        out=Path(settings.BASE_DIR)/'.artifacts/account-list-consistency';out.mkdir(parents=True,exist_ok=True);rows=[]
        with sync_playwright() as pw:
            browser=pw.chromium.launch(channel='msedge',headless=True)
            try:
                for viewport,size in [('desktop',{'width':1280,'height':900}),('mobile',{'width':390,'height':844})]:
                    for before in [True,False]:
                        context=browser.new_context(viewport=size)
                        if before:context.route('**/static/shared/workspace_trail.js*',lambda route:route.fulfill(status=200,content_type='application/javascript',body=old))
                        page=context.new_page();page.goto(self.live_server_url+'/')
                        page.evaluate('url=>NiixyWorkspaceTrail.open(url)',reverse('accounts:detail',args=[self.owner.username]));wait_for_trail_count(page,1)
                        page.locator('[data-account-fragment] [data-open-account-threads]').click();wait_for_trail_count(page,2)
                        entry=page.locator('.ui-workspace-trail-pane').last
                        next=entry.locator('[data-pane-pagination]').filter(has_text='次へ')
                        next.evaluate("el=>el.setAttribute('href','?created_page=2')");next.click()
                        if before:
                            wait_for_trail_count(page,3)
                            expect(entry.locator('[data-account-fragment]')).to_have_count(1)
                        else:
                            expect(entry.locator('.account-page')).to_have_count(0)
                            page.wait_for_url('**created_page=2')
                            expect(entry.locator('[data-thread-detail]')).to_have_count(10)
                        rows.append({'viewport':viewport,'old_query_only_handler':before,'wrong_account_pane_appended':before})
                        context.close()
            finally:browser.close()
        (out/'nested-pagination-before-after.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')


    def test_deep_board_url_preserves_both_list_pages_thread_page_and_close(self):
        from playwright.sync_api import sync_playwright,expect
        from scripts.browser_smoke import wait_for_trail_count
        with sync_playwright() as pw:
            browser=pw.chromium.launch(channel='msedge',headless=True)
            try:
                for size in [{'width':1280,'height':900},{'width':390,'height':844}]:
                    context=browser.new_context(viewport=size);page=context.new_page()
                    params=f'?pane=board&collection={self.collection.pk}&page=2&boards_page=2&board={self.board.pk}&thread_page=2'
                    page.goto(self.live_server_url+reverse('accounts:detail',args=[self.owner.username])+params)
                    wait_for_trail_count(page,1)
                    expect(page.locator('[data-board-thread-results] [data-room-thread]')).to_have_count(1)
                    page.locator('[data-room-thread]').click();wait_for_trail_count(page,2)
                    page.locator('.ui-workspace-trail-header .icon-button').last.click();wait_for_trail_count(page,1)
                    expect(page).to_have_url(__import__('re').compile('thread_page=2'))
                    page.locator('.ui-workspace-trail-header .icon-button').last.click();wait_for_trail_count(page,0)
                    panel=page.locator(f'[data-collection-panel-id="{self.collection.pk}"]')
                    expect(panel.locator('[data-collection-references] .content-reference-summary')).to_have_count(1)
                    expect(panel.locator('[data-open-board]')).to_have_count(2)
                    self.assertNotIn('thread_page',page.url)
                    context.close()
            finally:browser.close()

    def test_category_change_invalidates_delayed_people_module_board_pages(self):
        from playwright.sync_api import sync_playwright,expect
        from scripts.browser_smoke import wait_for_trail_count
        rows=[]
        with sync_playwright() as pw:
            browser=pw.chromium.launch(channel='msedge',headless=True)
            try:
                for viewport,size in [('desktop',{'width':1280,'height':900}),('mobile',{'width':390,'height':844})]:
                    for nested in [False,True]:
                        for action in ['people','modules','boards']:
                            context=browser.new_context(viewport=size);page=context.new_page();errors=[]
                            page.on("pageerror",lambda error:errors.append(str(error)))
                            page.on("console",lambda message:errors.append(message.text) if message.type=="error" and not message.location.get("url", "").endswith("/favicon.ico") else None)
                            page.add_init_script("""(() => {
                              const original=window.fetch;
                              window.fetch=async (...args) => {
                                const response=await original(...args);
                                if (window.holdPage && String(args[0]).includes('page=2')) {
                                  const text=response.text.bind(response);
                                  response.text=async () => {const value=await text();window.pageBodyHeld=true;await new Promise(resolve=>window.releasePageBody=resolve);return value;};
                                }
                                return response;
                              };
                            })();""")
                            url=reverse('accounts:detail',args=[self.owner.username])
                            page.goto(self.live_server_url+('/' if nested else url))
                            if nested:
                                page.evaluate('url=>NiixyWorkspaceTrail.open(url)',url);wait_for_trail_count(page,1)
                                origin=page.locator('[data-account-fragment]')
                            else:origin=page.locator('.account-overview-pane')
                            origin.locator('[data-open-account-'+action+']').evaluate('el=>el.click()')
                            wait_for_trail_count(page,2 if nested else 0)
                            if action=='people':
                                root=page.locator('[data-account-lists-index]');next=root.locator('[data-ui-tab-panel=love] [data-summary-page]').filter(has_text='次へ')
                                target=root.locator('[data-ui-tab=hate]')
                            elif action=='modules':
                                root=page.locator('[data-module-public]');next=root.locator('[data-module-public-panel=self] [data-summary-page]:visible').filter(has_text='次へ')
                                target=root.locator('[data-module-collection=bad]')
                            else:
                                root=page.locator('[data-integrated-kind=board]');root.locator(f'[data-collection-id="{self.collection.pk}"]').click()
                                next=root.locator(f'[data-collection-panel-id="{self.collection.pk}"] [data-collection-references] [data-summary-page]').filter(has_text='次へ')
                                target=root.locator('[data-ui-tab=fav]')
                            page.evaluate('window.holdPage=true');next.click();page.wait_for_function('window.pageBodyHeld===true')
                            target.evaluate('el=>el.click()');selected_url=page.url;retained_dom=root.inner_html()
                            page.evaluate('window.holdPage=false;window.releasePageBody()');page.wait_for_timeout(150)
                            expect(target).to_have_attribute('aria-selected','true');self.assertEqual(page.url,selected_url)
                            self.assertEqual(root.inner_html(),retained_dom);self.assertEqual(errors,[])
                            rows.append({'viewport':viewport,'nested':nested,'feature':action,'delayed_page_discarded':True})
                            context.close()
            finally:browser.close()
        out=Path(settings.BASE_DIR)/'.artifacts/account-list-consistency'
        out.mkdir(parents=True,exist_ok=True);(out/'delayed-pages.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
