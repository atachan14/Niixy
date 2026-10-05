"""Map Board and compact chrome QA on a temporary SQLite LiveServer."""
import json
from pathlib import Path
from uuid import uuid4
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from events.models import NiiMapFilterPreference, Thread, ThreadAccessRule, ThreadPlacement, ThreadPost
from rooms.models import Board
from rooms.services import create_board, create_room
from scripts.browser_test_server import SharedSQLiteStaticFilesHandler


class MapBoardBrowserTests(StaticLiveServerTestCase):
    static_handler = SharedSQLiteStaticFilesHandler

    def setUp(self):
        self.assertEqual(settings.DATABASES['default']['ENGINE'], 'django.db.backends.sqlite3')
        self.owner = get_user_model().objects.create_user('map_board_qa')
        self.room, _ = create_room(submission_id=uuid4(), owner=self.owner, name='Map QA Room', description='',
            latitude='35.681236', longitude='139.767125')
        self.board, _ = create_board(submission_id=uuid4(), name='Map QA Board', latitude='35.681236', longitude='139.767125')
        self.thread = Thread.objects.create(title='Newest Map Thread', creator=self.owner)
        ThreadPost.objects.create(thread=self.thread, number=1, body='QA post')
        ThreadPlacement.objects.create(thread=self.thread, latitude='35.681236', longitude='139.767125')
        for cap in ['view', 'write']:
            for audience in ['guest', 'account']:
                ThreadAccessRule.objects.create(thread=self.thread, capability=cap, audience=audience)

    def test_guest_board_create_thread_response_and_ui_edges(self):
        from playwright.sync_api import sync_playwright, expect
        from scripts.browser_smoke import wait_for_trail_count, close_current_trail
        output = Path(settings.BASE_DIR) / '.artifacts' / 'map-board-ui'
        output.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='msedge', headless=True)
            try:
                for name, size in [('desktop', {'width': 1280, 'height': 720}), ('mobile', {'width': 390, 'height': 844})]:
                    context = browser.new_context(viewport=size, is_mobile=name == 'mobile', has_touch=name == 'mobile')
                    page = context.new_page(); page.set_default_timeout(10000)
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' and not msg.location.get('url', '').endswith('/favicon.ico') else None)
                    try:
                        page.goto(self.live_server_url + '/')
                        expect(page.locator('#thread-list')).to_be_visible()
                        self.assertGreater(page.locator('.board-map-marker').count(), 0)
                        page.locator('.board-map-marker:not([hidden])').first.click()
                        expect(page.locator(f'.board-item[data-board-id="{self.board.pk}"] .board-summary')).to_have_class('ui-summary-item spot-summary board-summary is-selected')
                        page.locator('#niimap-create-toggle').click()
                        page.locator('#map').click(position={'x': 90, 'y': 150})
                        expect(page.locator('#open-board-create')).to_be_enabled()
                        page.locator('#open-board-create').click()
                        form = page.locator('#board-create-form')
                        form.locator('[name="name"]').fill('Guest Board ' + name)
                        form.locator('[name="description"]').fill('Created directly on NiiMap')
                        self.assertEqual(form.locator('[data-account-condition-groups-input]').count(), 4)
                        form.locator('summary').click()
                        row = form.locator('.room-board-policy-editor-row').nth(3)
                        row.locator('[data-open-account-conditions]').click()
                        history = page.locator('.account-condition-pane')
                        history.locator('[data-browse-account-conditions]').click()
                        page.locator('.account-selector-pane .ui-summary-item').filter(has=page.locator('strong', has_text='NiixyAccount')).click()
                        history.locator('.ui-summary-item').filter(has=page.locator('strong', has_text='NiixyAccount')).click()
                        history.locator('[data-add-account-condition-group]').click()
                        history.locator('[data-close-account-conditions]').click()
                        expect(form.locator('[name="name"]')).to_have_value('Guest Board ' + name)
                        self.assertEqual(len(json.loads(row.locator('input').input_value())), 1)
                        page.screenshot(path=output / f'{name}-board-create.png')
                        form.locator('[type="submit"]').click()
                        page.wait_for_url('**/?board=*')
                        wait_for_trail_count(page, 1)
                        pane = page.locator('.ui-workspace-trail-pane').last
                        expect(pane.locator('[data-board-name]')).to_have_attribute('data-board-name', 'Guest Board ' + name)
                        expect(pane.locator('[data-board-edit-toggle]')).to_have_count(0)
                        pane.locator('[data-board-create-toggle]').click()
                        thread_form = pane.locator('[data-board-thread-create]')
                        thread_form.locator('[name="title"]').fill('Guest Board Thread ' + name)
                        thread_form.locator('[name="body"]').fill('Opening from map Board')
                        thread_form.locator('[type="submit"]').click()
                        wait_for_trail_count(page, 2)
                        detail = page.locator('.ui-workspace-trail-pane').last
                        expect(detail.locator('.thread-post')).to_have_count(1)
                        border = detail.locator('.thread-post').first.bounding_box()
                        box = detail.bounding_box()
                        self.assertAlmostEqual(border['x'], box['x'] + 1, delta=1)
                        self.assertAlmostEqual(border['width'], box['width'] - 1, delta=1)
                        header = detail.locator('.ui-pane-header').bounding_box()
                        self.assertAlmostEqual(header['height'], 44 if name == 'mobile' else 32, delta=1)
                        placement = detail.locator('.ui-placement-row').bounding_box()
                        self.assertAlmostEqual(placement['height'], 32 if name == 'mobile' else 24, delta=1)
                        self.assertAlmostEqual(placement['width'], box['width'] - 1, delta=1)
                        reply = detail.locator('.thread-reply-form')
                        reply.locator('textarea').fill('Guest Response')
                        reply.locator('[type="submit"]').click()
                        expect(detail.locator('.thread-post')).to_have_count(2)
                        page.screenshot(path=output / f'{name}-board-thread.png')
                        page.reload()
                        wait_for_trail_count(page, 2)
                        expect(page.locator('.ui-workspace-trail-pane').last.locator('.thread-post')).to_have_count(2)
                        close_current_trail(page, 1); close_current_trail(page, 0)
                        page.locator(f'a.room-summary[href="/rooms/{self.room.pk}/"]').click()
                        wait_for_trail_count(page, 1)
                        room = page.locator('.ui-workspace-trail-pane').last
                        expect(room.locator('.ui-identity-created')).to_be_visible()
                        room.locator('.identity-profile-placeholder').evaluate('el => el.style.minHeight = "800px"')
                        room.locator('.ui-workspace-trail-body').evaluate('el => el.scrollTop = 180')
                        self.assertGreater(room.locator('.ui-workspace-trail-body').evaluate('el => el.scrollTop'), 100)
                        coords = room.locator('.ui-placement-row').bounding_box()
                        body = room.locator('.ui-workspace-trail-body').bounding_box()
                        self.assertAlmostEqual(coords['y'], body['y'], delta=1)
                        self.assertAlmostEqual(coords['width'], room.bounding_box()['width'] - 1, delta=1)
                        page.screenshot(path=output / f'{name}-room-sticky.png')
                        page.goto(self.live_server_url + f'/accounts/{self.owner.username}/')
                        expect(page.locator('.account-page-header .ui-identity-created')).to_be_visible()
                        page.screenshot(path=output / f'{name}-account-date.png')
                        page.goto(self.live_server_url + f'/rooms/{self.room.pk}/')
                        expect(page.locator('.room-page-header .ui-identity-created')).to_be_visible()
                        overview = page.locator('.room-overview-pane')
                        overview.locator('.identity-profile-placeholder').evaluate('el => el.style.minHeight = "800px"')
                        overview.evaluate('el => el.scrollTop = 200')
                        self.assertGreater(overview.evaluate('el => el.scrollTop'), 100)
                        self.assertAlmostEqual(overview.locator('.ui-placement-row').bounding_box()['y'], overview.bounding_box()['y'], delta=1)
                        self.assertEqual(errors, [])
                    finally:
                        page.screenshot(path=output / f'{name}-last.png')
                        context.close()
            finally: browser.close()

    def test_initial_sorted_list_waits_for_response_and_retry(self):
        from playwright.sync_api import sync_playwright, expect
        NiiMapFilterPreference.objects.create(user=self.owner, search_state={'sort_kind': 'updated'})
        self.client.force_login(self.owner)
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='msedge', headless=True)
            context = browser.new_context()
            context.add_cookies([{'name': settings.SESSION_COOKIE_NAME, 'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url': self.live_server_url}])
            page = context.new_page()
            page.add_init_script("""const realFetch = window.fetch; window.fetch = async (...args) => {
                if (String(args[0]).includes('/api/threads/search/')) {
                    window.qaSearchWaiting = true;
                    await new Promise(resolve => setTimeout(resolve, 1200));
                }
                return realFetch(...args);
            };""")
            try:
                page.goto(self.live_server_url + '/', wait_until='domcontentloaded')
                page.wait_for_function('window.qaSearchWaiting === true')
                expect(page.locator('#thread-list')).to_be_hidden()
                expect(page.locator('#niimap-list-status')).to_be_visible()
                expect(page.locator('#thread-list')).to_be_visible()
                self.assertEqual(page.locator('#thread-list > article').first.get_attribute('data-thread-id'), str(self.thread.pk))
                page.route('**/api/threads/search/', lambda route: route.fulfill(status=503, content_type='application/json', body='{"error":"QA search unavailable"}'))
                page.reload()
                expect(page.locator('#niimap-list-retry')).to_be_visible()
                expect(page.locator('#thread-list')).to_be_hidden()
                page.unroute('**/api/threads/search/')
                page.locator('#niimap-list-retry').click()
                expect(page.locator('#thread-list')).to_be_visible()
                self.assertEqual(page.locator('#thread-list > article').first.get_attribute('data-thread-id'), str(self.thread.pk))
            finally:
                context.close(); browser.close()
