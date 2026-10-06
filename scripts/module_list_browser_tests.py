"""Integrated Board/Module tabs and public definitions: PC/mobile Edge, isolated DB."""
from pathlib import Path
from uuid import uuid4
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from accounts.tests_module_lists import seed
from accounts.content_lists import route
from interfaces.models import InterfaceListReference
from scripts.browser_test_server import SharedSQLiteStaticFilesHandler


class ModuleListBrowserTests(StaticLiveServerTestCase):
    static_handler=SharedSQLiteStaticFilesHandler
    def setUp(self):
        seed(self)
        self.main_id=self.owner.collections.get(name='Main').pk
        InterfaceListReference.objects.create(interface_list=self.content_list,target=self.interfaces[0])

    def test_tabs_ratings_lists_workspace_input_and_guest_pc_mobile(self):
        from playwright.sync_api import sync_playwright,expect
        from scripts.browser_smoke import wait_for_trail_count
        output=Path(settings.BASE_DIR)/'.artifacts'/'module-lists';output.mkdir(parents=True,exist_ok=True)
        with sync_playwright() as pw:
            browser=pw.chromium.launch(channel='msedge',headless=True)
            try:
                for viewport,size in [('desktop',{'width':1280,'height':900}),('mobile',{'width':390,'height':844})]:
                    with self.subTest(viewport=viewport):
                        context=browser.new_context(viewport=size,is_mobile=viewport=='mobile',has_touch=viewport=='mobile')
                        context.add_cookies([{'name':settings.SESSION_COOKIE_NAME,'value':self.client.cookies[settings.SESSION_COOKIE_NAME].value,'url':self.live_server_url}])
                        page=context.new_page();page.set_default_timeout(10000);errors=[]
                        page.on('pageerror',lambda e:errors.append(str(e)))
                        page.on('console',lambda m:errors.append(m.text) if m.type=='error' and not m.location.get('url','').endswith('/favicon.ico') else None)
                        try:
                            page.goto(self.live_server_url+reverse('accounts:detail',args=[self.owner.username]))
                            self.assertNotIn('BoardList',page.locator('.account-actions-grid').inner_text())
                            self.assertNotIn('InterfaceList',page.locator('.account-actions-grid').inner_text())
                            page.locator('[data-open-account-modules]').click()
                            root=page.locator('[data-module-public]');expect(root).to_be_visible()
                            expect(root.locator('[data-module-collection]')).to_have_text(['自作','fav','bad','Mixed List A','Mixed List B'])
                            expect(root.locator('[data-module-type]')).to_have_text(['Element','Interface','Layout'])
                            expect(root.locator('[data-module-public-panel=self]')).to_contain_text('Own Field')
                            list_key='list-'+str(self.content_list.pk)
                            root.locator(f'[data-module-collection="{list_key}"]').click()
                            panel=root.locator(f'[data-module-public-panel="{list_key}"]')
                            expect(panel.locator('.content-reference-summary:visible')).to_have_count(1)
                            expect(panel.locator('.content-reference-summary:visible')).to_contain_text('Public Field')
                            root.locator('[data-module-type=interface]').click()
                            expect(panel.locator('.content-reference-summary:visible')).to_have_count(1)
                            expect(panel.locator('.content-reference-summary:visible')).to_contain_text('Public thread IF')
                            root.locator('[data-module-subtypes=interface] [data-module-subtype=account]').click()
                            expect(panel.locator('.content-reference-summary:visible')).to_contain_text('Public account IF')
                            root.locator('[data-module-type=layout]').click()
                            expect(panel.locator('.content-reference-summary:visible')).to_have_count(0)
                            root.locator('[data-module-subtypes=layout] [data-module-subtype=account]').click()
                            expect(panel.locator('.content-reference-summary:visible')).to_contain_text('Public Layout')
                            page.screenshot(path=str(output/(viewport+'-three-tabs.png')),full_page=True)
                            # Public Layout and Field expose the same exclusive rating controls.
                            panel.locator('.content-reference-summary:visible').click();wait_for_trail_count(page,1)
                            feedback=page.locator('.ui-workspace-trail-pane [data-content-feedback]')
                            feedback.locator('[data-content-rate=bad]').click();expect(feedback.locator('[data-content-rate=bad]')).to_have_attribute('aria-pressed','true')
                            feedback.locator('[data-content-rate=bad]').click();expect(feedback.locator('[data-content-rate=bad]')).to_have_attribute('aria-pressed','false')
                            page.locator('.ui-workspace-trail-header .icon-button').last.click();wait_for_trail_count(page,0)
                            root.locator('[data-module-type=element]').click()
                            panel.locator('.content-reference-summary:visible').click();wait_for_trail_count(page,1)
                            feedback=page.locator('.ui-workspace-trail-pane [data-content-feedback]')
                            feedback.locator('[data-content-rate=fav]').click();expect(feedback.locator('[data-content-rate=fav]')).to_have_attribute('aria-pressed','false')
                            feedback.locator('[data-content-rate=bad]').click();expect(feedback.locator('[data-content-rate=bad]')).to_have_attribute('aria-pressed','true')
                            feedback.locator('[data-content-rate=fav]').click();expect(feedback.locator('[data-content-rate=fav]')).to_have_attribute('aria-pressed','true')
                            feedback.locator('[data-account-list-picker-url]').click();wait_for_trail_count(page,2)
                            picker=page.locator('[data-account-list-picker]');expect(picker).to_be_visible()
                            picker.locator('[data-list-operation=pick]').first.locator('button[type=submit]').click()
                            expect(picker.locator('[data-list-success]').first).to_contain_text('追加しました')
                            page.locator('.ui-workspace-trail-header .icon-button').last.click();wait_for_trail_count(page,1)
                            page.locator('.ui-workspace-trail-header .icon-button').last.click();wait_for_trail_count(page,0)
                            # List details are filtered to the selected first/second tabs.
                            panel=root.locator(f'[data-module-public-panel="{list_key}"]')
                            panel.locator('[data-module-list-detail]').click();wait_for_trail_count(page,1)
                            detail=page.locator('[data-account-list-detail]');expect(detail.locator('.content-reference-summary')).to_have_count(1)
                            expect(detail).not_to_contain_text('Public Layout')
                            add=detail.locator('[data-list-operation=add]');add.locator('[name=target_url]').fill('/fields/pending/')
                            detail.evaluate('el=>window.qaRetainedList=el')
                            detail.locator('.content-reference-summary').click();wait_for_trail_count(page,2)
                            page.locator('.ui-workspace-trail-header .icon-button').last.click();wait_for_trail_count(page,1)
                            self.assertTrue(detail.evaluate('el=>el===window.qaRetainedList'))
                            expect(add.locator('[name=target_url]')).to_have_value('/fields/pending/')
                            detail.locator('summary').filter(has_text='Listの管理').click()
                            rename=detail.locator('[data-list-operation=rename]');rename.locator('[name=name]').fill('Renamed '+viewport)
                            rename.locator('button[type=submit]').click()
                            expect(root.locator(f'[data-module-collection="{list_key}"]')).to_have_text('Renamed '+viewport)
                            expect(page.locator('[data-list-operation=add] [name=target_url]')).to_have_value('/fields/pending/')
                            page.screenshot(path=str(output/(viewport+'-saved-list.png')),full_page=True)
                            page.locator('.ui-workspace-trail-header .icon-button').last.click();wait_for_trail_count(page,0)
                            # Create through the integrated entry, then see its new third tab.
                            root.locator('[data-reference-title="Module List管理"]').click();wait_for_trail_count(page,1)
                            index=page.locator('[data-account-lists-index]');create=index.locator('[data-list-operation=create]')
                            create.locator('[name=name]').fill('New '+viewport);create.locator('button[type=submit]').click()
                            wait_for_trail_count(page,2)
                            expect(root.locator('[data-module-collection]').last).to_have_text('New '+viewport)
                            new_detail=page.locator('[data-account-list-detail]')
                            new_detail.locator('summary').filter(has_text='Listの管理').click()
                            page.once('dialog',lambda d:d.accept());new_detail.locator('[data-list-operation=delete] button').click();wait_for_trail_count(page,1)
                            expect(root.locator('[data-module-collection]').last).to_have_text('Mixed List B')
                            page.locator('.ui-workspace-trail-header .icon-button').last.click();wait_for_trail_count(page,0)
                            # Restore the shared fixture name for the other viewport.
                            response=context.request.post(self.live_server_url+route('interface','list-rename',self.content_list.pk),form={'name':'Mixed List A'},headers={'X-CSRFToken':page.locator('[name=csrfmiddlewaretoken]').first.input_value()})
                            self.assertEqual(response.status,200)
                            # Board's tabs retain original placement creation and input on refresh.
                            page.goto(self.live_server_url+reverse('accounts:detail',args=[self.owner.username]))
                            page.locator('[data-open-account-boards]').click();wait_for_trail_count(page,1)
                            boards=page.locator('[data-integrated-kind=board]')
                            expect(boards.locator('[data-ui-tab]:visible')).to_have_text(['自作','fav','bad','Main','未分類'])
                            main_id=self.main_id
                            boards.locator(f'[data-collection-id="{main_id}"]').click()
                            collection=boards.locator(f'[data-collection-panel-id="{main_id}"]')
                            collection.locator('[data-collection-create-toggle]').click()
                            input_=collection.locator('[data-board-action-kind=create] [name=name]');input_.fill('Kept Board input')
                            collection.evaluate('el=>window.qaBoardCollection=el')
                            boards.locator('[data-reference-title="Board List管理"]').click();wait_for_trail_count(page,2)
                            idx=page.locator('[data-account-lists-index]');idx.locator('[data-list-operation=create] [name=name]').fill('New Board '+viewport)
                            idx.locator('[data-list-operation=create] button').click();wait_for_trail_count(page,3)
                            expect(boards.locator('[data-ui-tab]:visible')).to_have_text(['自作','fav','bad','Main','New Board '+viewport,'未分類'])
                            new_board_id=page.locator('[data-account-list-detail]').get_attribute('data-list-id')
                            page.locator('.ui-workspace-trail-header .icon-button').last.click();wait_for_trail_count(page,2)
                            page.locator('.ui-workspace-trail-header .icon-button').last.click();wait_for_trail_count(page,1)
                            self.assertTrue(collection.evaluate('el=>el===window.qaBoardCollection'));expect(input_).to_have_value('Kept Board input')
                            page.screenshot(path=str(output/(viewport+'-board-tabs.png')),full_page=True)
                            # Remove the newly created list to reset the mobile fixture.
                            response=context.request.post(self.live_server_url+route('board','list-delete',new_board_id),headers={'X-CSRFToken':page.locator('[name=csrfmiddlewaretoken]').first.input_value()})
                            self.assertEqual(response.status,200)
                            # Native List URL can be reloaded by a Guest; writes remain disabled.
                            guest=browser.new_context(viewport=size,is_mobile=viewport=='mobile',has_touch=viewport=='mobile')
                            gp=guest.new_page();gp.on('pageerror',lambda e:errors.append(str(e)))
                            gp.goto(self.live_server_url+route('interface','list-page',self.content_list.pk));wait_for_trail_count(gp,1)
                            expect(gp.locator('[data-account-list-detail]')).to_contain_text('Public Field')
                            expect(gp.locator('[data-account-list-form]')).to_have_count(0)
                            gp.reload();wait_for_trail_count(gp,1)
                            gp.goto(self.live_server_url+route('field','page',self.field.pk))
                            expect(gp.locator('[data-content-rate=fav]')).to_be_disabled()
                            guest.close()
                            self.assertEqual(errors,[])
                        finally:context.close()
            finally:browser.close()
