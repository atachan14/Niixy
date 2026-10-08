"""Focused split feedback controls: disposable SQLite and local Edge."""
import json
from pathlib import Path
from uuid import uuid4
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from accounts.content_lists import route
from interfaces.models import InterfaceDraft, AccountLayout, AccountLayoutVersion
from interfaces.services import publish_draft, publish_field_definition
from rooms.models import Board
from rooms.services import create_room
from scripts.browser_test_server import SharedSQLiteStaticFilesHandler
from scripts.conversation_feedback_tests import seed


class FeedbackControlsBrowserTests(StaticLiveServerTestCase):
    static_handler = SharedSQLiteStaticFilesHandler

    def setUp(self):
        seed(self)
        room, _ = create_room(submission_id=uuid4(), owner=self.other, name='Feedback QA Room', description='', latitude='35', longitude='139')
        self.board = Board.objects.filter(placement__collection__room=room).first()
        draft = InterfaceDraft.objects.create(creator=self.other, kind='account', name='Feedback QA Module', description='Public module')
        self.module, _ = publish_draft(draft.pk)
        self.field, _ = publish_field_definition(creator=self.other, name='Feedback QA Field', field_type='short_text')
        self.layout = AccountLayout.objects.create(creator=self.other, name='Feedback QA Layout')
        self.layout.current_version = AccountLayoutVersion.objects.create(layout=self.layout, version_number=1, name=self.layout.name, html='<p>Public Layout</p>')
        self.layout.save()
        self.client.force_login(self.owner)
        self.session = self.client.cookies[settings.SESSION_COOKIE_NAME].value

    def test_split_controls(self):
        from playwright.sync_api import sync_playwright, expect
        from scripts.browser_smoke import wait_for_trail_count
        output = Path(settings.BASE_DIR) / '.artifacts' / 'feedback-controls'
        output.mkdir(parents=True, exist_ok=True)
        evidence = []
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='msedge', headless=True)
            try:
                for viewport, size in [('desktop', {'width':1280,'height':900}), ('mobile', {'width':390,'height':844})]:
                    for actor in ['account','guest']:
                        context = browser.new_context(viewport=size, is_mobile=viewport=='mobile', has_touch=viewport=='mobile')
                        if actor == 'account':
                            context.add_cookies([{'name':settings.SESSION_COOKIE_NAME,'value':self.session,'url':self.live_server_url}])
                        page = context.new_page()
                        errors = []
                        page.on('pageerror', lambda error: errors.append(str(error)))
                        page.on('console', lambda message: errors.append(message.text) if message.type=='error' and not message.location.get('url','').endswith('/favicon.ico') else None)
                        for kind, target in [('thread',self.thread),('response',self.response),('board',self.board),('interface',self.module),('field',self.field),('layout',self.layout)]:
                            page.goto(self.live_server_url + route(kind,'page',target.pk))
                            feedback = page.locator(f'[data-content-kind="{kind}"]').first
                            expect(feedback).to_be_visible()
                            base = page.locator('.ui-workspace-trail-pane').count()
                            fav = feedback.locator('[data-content-rate=fav]')
                            bad = feedback.locator('[data-content-rate=bad]')
                            count = feedback.locator('[data-content-count=fav]')
                            expect(count).to_have_text('(0)')
                            controls = feedback.locator('[data-content-rate], [data-content-count], [data-account-list-picker-url]')
                            boxes = controls.evaluate_all('els=>els.map(el=>{const r=el.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height}})')
                            self.assertEqual(len(boxes),5)
                            self.assertLess(max(b['y'] for b in boxes)-min(b['y'] for b in boxes),2,boxes)
                            if viewport=='mobile':self.assertTrue(all(b['width']>=44 and b['height']>=44 for b in boxes),boxes)
                            self.assertFalse(feedback.evaluate('el=>el.scrollWidth>el.clientWidth+1'))
                            # Zero count opens an empty Pane, never posts a rating; close returns to origin.
                            writes = []
                            def track(request):
                                if request.method=='POST' and request.url.endswith('/rating/'):writes.append(request.url)
                            page.on('request',track)
                            count.click();wait_for_trail_count(page,base+1)
                            self.assertEqual(writes,[])
                            page.locator('.ui-workspace-trail-header .icon-button').last.click();wait_for_trail_count(page,base)
                            expect(feedback).to_be_visible()
                            if actor=='account':
                                fav.click();expect(fav).to_have_attribute('aria-pressed','true');expect(count).to_have_text('(1)')
                                page.screenshot(path=output/f'{viewport}-{kind}-selected.png')
                                count.click();wait_for_trail_count(page,base+1)
                                expect(page.locator('.ui-workspace-trail-pane').last.locator('.account-summary')).to_have_count(1)
                                page.locator('.ui-workspace-trail-header .icon-button').last.click();wait_for_trail_count(page,base)
                                self.assertEqual(len(writes),1)
                                bad.click();expect(bad).to_have_attribute('aria-pressed','true');expect(fav).to_have_attribute('aria-pressed','false');expect(count).to_have_text('(0)')
                                bad.click();expect(bad).to_have_attribute('aria-pressed','false')
                                fav.focus();page.keyboard.press('Tab');expect(count).to_be_focused()
                                self.assertNotEqual(count.evaluate('el=>getComputedStyle(el).outlineStyle'),'none')
                                feedback.locator('[data-account-list-picker-url]').click();wait_for_trail_count(page,base+1)
                                expect(page.locator('[data-account-list-picker]')).to_be_visible()
                                page.locator('.ui-workspace-trail-header .icon-button').last.click();wait_for_trail_count(page,base)
                            else:
                                expect(fav).to_be_disabled();expect(bad).to_be_disabled();expect(feedback.locator('[data-account-list-picker-url]')).to_be_disabled()
                                expect(count).to_be_enabled()
                            # Large counts are a layout fixture only; server data stays truthful.
                            count.evaluate("el=>el.textContent='(123456789)'")
                            self.assertFalse(feedback.evaluate('el=>el.scrollWidth>el.clientWidth+1'))
                            pair_boxes=feedback.locator('.content-rating-control').evaluate_all('els=>els.map(el=>({width:el.getBoundingClientRect().width,children:[...el.children].map(c=>c.getBoundingClientRect().y)}))')
                            self.assertTrue(all(max(b['children'])-min(b['children'])<2 for b in pair_boxes))
                            if actor=='account' and kind=='thread':
                                page.screenshot(path=output/f'{viewport}-large-count.png')
                                count.evaluate("el=>el.textContent='(0)'")
                                page.screenshot(path=output/f'{viewport}-thread.png')
                                if viewport=='mobile':
                                    page.set_viewport_size({'width':320,'height':844})
                                    count.evaluate("el=>el.textContent='(123456789)'")
                                    self.assertFalse(feedback.evaluate('el=>el.scrollWidth>el.clientWidth+1'))
                                    page.screenshot(path=output/'narrow-large-count.png')
                                    page.set_viewport_size(size)
                            page.remove_listener('request',track)
                            evidence.append({'viewport':viewport,'actor':actor,'kind':kind,'controls':boxes,'passed':True})
                        self.assertFalse(errors,errors)
                        context.close()
            finally:
                browser.close()
        (output/'results.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
