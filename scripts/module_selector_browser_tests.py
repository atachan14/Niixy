"""Focused NiiMap creation selector regression; SQLite fixture only."""
from pathlib import Path
from uuid import uuid4
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from scripts.browser_test_server import SharedSQLiteStaticFilesHandler
from interfaces.models import InterfaceDraft, InterfaceDraftField
from interfaces.services import publish_draft, publish_field_definition
from rooms.models import Board
from rooms.services import create_room


class ModuleSelectorBrowserTests(StaticLiveServerTestCase):
    static_handler=SharedSQLiteStaticFilesHandler

    def setUp(self):
        self.assertEqual(settings.DATABASES['default']['ENGINE'],'django.db.backends.sqlite3')
        self.owner=get_user_model().objects.create_user('selector_owner')
        field,_=publish_field_definition(creator=self.owner,name='Selector Field',field_type='short_text')
        draft=InterfaceDraft.objects.create(creator=self.owner,kind='thread',name='Selector IF')
        InterfaceDraftField.objects.create(draft=draft,definition=field,position=0)
        publish_draft(draft.pk)
        self.room,_=create_room(submission_id=uuid4(),owner=self.owner,name='Selector Room',description='',latitude='35.681236',longitude='139.767125')
        self.board=Board.objects.get()
        self.client.force_login(self.owner)

    def assert_origin_and_current(self,page,form,current,size):
        self.assertEqual(form.evaluate('el=>getComputedStyle(el.closest(".thread-detail-pane, .niimap-room-thread-list-pane")).display')=='none',False)
        layout=page.evaluate("""() => {
            const track=document.querySelector('.thread-track');
            const origin=document.querySelector('#thread-create-form').closest('.thread-detail-pane');
            const list=track.querySelector('.thread-create-module-list-pane');
            return {originRight:origin.getBoundingClientRect().right,listLeft:list.getBoundingClientRect().left};
        }""") if form.get_attribute('id')=='thread-create-form' else None
        if layout:self.assertAlmostEqual(layout['originRight'],layout['listLeft'],delta=1)
        box=current.bounding_box();self.assertAlmostEqual(box['x']+box['width'],size['width'],delta=1)

    def test_create_selectors_preserve_origin_and_input(self):
        from playwright.sync_api import sync_playwright,expect
        output=Path(settings.BASE_DIR)/'.artifacts'/'module-selector';output.mkdir(parents=True,exist_ok=True)
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(channel='msedge',headless=True)
            try:
                for viewport,size in [('desktop',{'width':1280,'height':720}),('mobile',{'width':390,'height':844})]:
                    context=browser.new_context(viewport=size,is_mobile=viewport=='mobile',has_touch=viewport=='mobile')
                    context.add_cookies([{'name':settings.SESSION_COOKIE_NAME,'value':self.client.cookies[settings.SESSION_COOKIE_NAME].value,'url':self.live_server_url}])
                    page=context.new_page();page.set_default_timeout(7000);errors=[]
                    page.on('pageerror',lambda e:errors.append(str(e)))
                    page.on('console',lambda msg:errors.append(msg.text) if msg.type=='error' and not msg.location.get('url','').endswith('/favicon.ico') else None)
                    try:
                        page.goto(self.live_server_url+'/')
                        page.locator('#niimap-create-toggle').click()
                        page.evaluate('map.fire("click",{lngLat:{lng:139.767125,lat:35.681236}})')
                        page.locator('#open-thread-create').click()
                        form=page.locator('#thread-create-form');form.locator('[name="title"]').fill('Unsaved selector title')
                        for kind in ('interface','field'):
                            with self.subTest(viewport=viewport,kind=kind):
                                form.locator(f'[data-open-thread-{kind}-selector]').click()
                                listing=page.locator('.thread-create-module-list-pane');listing.wait_for();page.wait_for_timeout(300)
                                self.assert_origin_and_current(page,form,listing,size)
                                listing.locator('.ui-summary-item').first.click()
                                detail=page.locator('.thread-create-module-detail-pane')
                                detail.locator('.interface-implementation-editor input').first.fill(f'{kind} input')
                                page.wait_for_timeout(300);self.assert_origin_and_current(page,form,detail,size)
                                detail.locator('.interface-detail-actions button').click()
                                expect(page.locator('.thread-create-module-selector-pane')).to_have_count(0)
                                expect(form.locator('[name="title"]')).to_have_value('Unsaved selector title')
                                target='[data-selected-thread-interface]' if kind=='interface' else '[data-selected-direct-field]'
                                expect(form.locator(target+' input:not([type="hidden"])').first).to_have_value(f'{kind} input')
                                form.locator(f'[data-open-thread-{kind}-selector]').click()
                                page.locator('.thread-create-module-list-pane .ui-summary-item').first.click()
                                expect(page.locator('.interface-implementation-editor input').first).to_have_value(f'{kind} input')
                                page.locator('.thread-create-module-detail-pane .ui-pane-header button').click()
                                page.wait_for_timeout(300)
                                self.assert_origin_and_current(page,form,page.locator('.thread-create-module-list-pane'),size)
                                page.locator('.thread-create-module-list-pane .ui-pane-header button').click()
                                expect(page.locator('.thread-create-module-selector-pane')).to_have_count(0)
                        page.wait_for_timeout(300);page.screenshot(path=output/f'{viewport}-create.png',full_page=True)
                        page.locator('#close-thread-detail').click()
                        page.locator('#niimap-search-toggle').click()
                        page.locator('details.niimap-search-section').filter(has=page.locator('[data-search-select="interface"]')).locator(':scope > summary').click()
                        for kind in ('interface','field'):
                            page.locator(f'[data-search-select="{kind}"]').click()
                            page.locator(f'#thread-{kind}-selector').wait_for()
                            self.assertEqual(page.locator('.thread-create-module-selector-pane').count(),0)
                            if viewport=='desktop':self.assertEqual(page.locator('.thread-detail-pane').evaluate('el=>getComputedStyle(el).display'),'none')
                            page.locator(f'#close-thread-{kind}-selector').click()
                        if viewport=='desktop':
                            page.goto(f'{self.live_server_url}/?room={self.room.pk}&room_list=boards&board={self.board.pk}')
                            page.locator('[data-board-create-toggle]').click()
                            board_form=page.locator('[data-board-thread-create]')
                            board_form.locator('[name="title"]').fill('Unsaved Board title')
                            origin_width=page.locator('.thread-detail-pane').bounding_box()['width']
                            for kind in ('interface','field'):
                                board_form.locator(f'[data-open-thread-{kind}-selector]').click()
                                listing=page.locator('.thread-create-module-list-pane');listing.wait_for();page.wait_for_timeout(300)
                                self.assert_origin_and_current(page,board_form,listing,size)
                                self.assertAlmostEqual(page.locator('.thread-detail-pane').bounding_box()['width'],origin_width,delta=1)
                                listing.locator('.ui-summary-item').first.click()
                                detail=page.locator('.thread-create-module-detail-pane')
                                detail.locator('.interface-implementation-editor input').first.fill(f'board {kind}')
                                detail.locator('.interface-detail-actions button').click()
                                expect(board_form.locator('[name="title"]')).to_have_value('Unsaved Board title')
                                expect(page.locator('.thread-create-module-selector-pane')).to_have_count(0)
                            page.wait_for_timeout(300);page.screenshot(path=output/'desktop-board.png',full_page=True)
                        if viewport=='desktop':
                            page.goto(self.live_server_url+'/')
                            page.locator(f'a.room-summary[href="/rooms/{self.room.pk}/"]').click()
                            page.locator('.ui-workspace-trail-pane').nth(0).locator('[data-open-room-boards]').click()
                            page.locator('.ui-workspace-trail-pane').nth(1).locator(f'[data-open-board="{self.board.pk}"]').click()
                            board=page.locator('.ui-workspace-trail-pane').nth(2)
                            board.locator('[data-board-create-toggle]').click()
                            for kind in ('interface','field'):
                                board.locator(f'[data-open-thread-{kind}-selector]').click()
                                page.locator('.thread-create-module-list-pane .ui-summary-item').first.click()
                                page.locator('.thread-create-module-detail-pane .interface-implementation-editor input').first.fill(f'shared {kind}')
                                page.locator('.thread-create-module-detail-pane .interface-detail-actions button').click()
                                expect(page.locator('.thread-create-module-selector-pane')).to_have_count(0)
                                expect(page.locator('.ui-workspace-trail-pane')).to_have_count(3)
                        self.assertEqual(errors,[])
                    finally:
                        page.screenshot(path=output/f'{viewport}-final.png',full_page=True)
                        context.close()
            finally:browser.close()
