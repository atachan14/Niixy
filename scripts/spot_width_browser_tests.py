"""Spot-list width regression on isolated SQLite/LiveServer, with visual evidence."""
import json
import os
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase

from events.models import Thread, ThreadAccessRule, ThreadPlacement, ThreadPost
from rooms.services import create_room
from scripts.browser_test_server import SharedSQLiteStaticFilesHandler


class SpotWidthBrowserTests(StaticLiveServerTestCase):
    static_handler = SharedSQLiteStaticFilesHandler

    def setUp(self):
        self.assertEqual(settings.DATABASES['default']['ENGINE'], 'django.db.backends.sqlite3')
        self.owner = get_user_model().objects.create_user('width_qa')
        self.room, _ = create_room(submission_id=uuid4(), owner=self.owner,
                                  name='Spot Width Room', description='Width regression fixture',
                                  latitude='35.681236', longitude='139.767125')
        self.threads = []
        for index in range(8):
            thread = Thread.objects.create(creator=self.owner, title=f'Spot Width Thread {index}')
            ThreadPost.objects.create(thread=thread, number=1, creator=self.owner, body='Spot list regression')
            ThreadPlacement.objects.create(thread=thread, latitude='35.681236', longitude='139.767125')
            for capability in ['view', 'write']:
                for audience in ['guest', 'account']:
                    ThreadAccessRule.objects.create(thread=thread, capability=capability, audience=audience)
            self.threads.append(thread)
        phase = os.environ.get('SPOT_WIDTH_QA_PHASE', 'after')
        self.output = Path(os.environ.get('SPOT_WIDTH_QA_OUTPUT', str(settings.BASE_DIR / '.artifacts' / 'spot-width'))) / phase
        self.output.mkdir(parents=True, exist_ok=True)
        self.measurements = []

    def inspect_root(self, page, name, stage):
        page.wait_for_selector('#thread-list:not([hidden]) .spot-summary')
        page.wait_for_timeout(350)
        row = page.evaluate('''() => {
            const box = s => {const el = document.querySelector(s), r = el.getBoundingClientRect();
                return {x:r.x, right:r.right, width:r.width, client:el.clientWidth,
                        scroll:el.scrollWidth, scrollLeft:el.scrollLeft};};
            return {viewport:innerWidth, documentWidth:document.documentElement.scrollWidth,
                    workspace:box('.thread-workspace'), root:box('.thread-map-list-pane'),
                    map:box('.map-frame'), list:box('.thread-list-pane'),
                    header:box('.thread-pane-header'), summary:box('#thread-list .spot-summary')};
        }''')
        row.update(viewport_name=name, stage=stage)
        self.measurements.append(row)
        (self.output / 'measurements.json').write_text(json.dumps(self.measurements, indent=2), encoding='utf-8')
        page.screenshot(path=self.output / f'{name}-{stage}.png')
        viewport_width = page.viewport_size['width']
        self.assertEqual(row['viewport'], viewport_width, row)
        expected = viewport_width if viewport_width <= 780 else 360
        self.assertAlmostEqual(row['list']['width'], expected, delta=1, msg=row)
        self.assertAlmostEqual(row['map']['width'], row['viewport'] if row['viewport'] <= 780 else row['viewport'] - 360, delta=1, msg=row)
        self.assertLessEqual(row['list']['scroll'], row['list']['client'], row)
        self.assertEqual(row['root']['scrollLeft'], 0, row)
        self.assertLessEqual(row['documentWidth'], row['viewport'], row)
        self.assertAlmostEqual(row['summary']['right'], row['list']['right'], delta=1, msg=row)
        self.assertAlmostEqual(row['summary']['x'], row['list']['x'] + 1, delta=1, msg=row)
        return row

    def test_initial_and_restored_spot_width(self):
        from playwright.sync_api import sync_playwright
        from scripts.browser_smoke import wait_for_trail_count, close_current_trail

        self.client.force_login(self.owner)
        self.assertEqual(self.client.get('/').status_code, 200)
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='msedge', headless=True)
            try:
                for width in [int(value) for value in os.environ.get('SPOT_WIDTH_QA_WIDTHS', '320,360,375,390,430,768,780,781,1280').split(',')]:
                    name = f'mobile-{width}' if width <= 780 else f'desktop-{width}'
                    with self.subTest(viewport=name):
                        context = browser.new_context(viewport={'width': width, 'height': 844 if width <= 780 else 720},
                                                      is_mobile=width <= 780, has_touch=width <= 780)
                        context.add_cookies([{'name': settings.SESSION_COOKIE_NAME,
                                             'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value,
                                             'url': self.live_server_url}])
                        page = context.new_page()
                        page.set_default_timeout(10000)
                        errors = []
                        page.on('pageerror', lambda error: errors.append(str(error)))
                        page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error'
                                and not msg.location.get('url', '').endswith('/favicon.ico') else None)
                        try:
                            page.goto(self.live_server_url + '/', wait_until='domcontentloaded')
                            page.wait_for_selector('#thread-list:not([hidden]) .spot-summary')
                            root = page.locator('.thread-map-list-pane')
                            if width <= 780:
                                root.evaluate('el => el.scrollTop = document.querySelector(".map-frame").offsetHeight - 140')
                            self.inspect_root(page, name, 'initial')
                            # Preserve the actual list DOM and mobile scroll through Room and list Pane Close.
                            page.locator(f'a.room-summary[href="/rooms/{self.room.pk}/"]').scroll_into_view_if_needed()
                            scroll_top = root.evaluate('el => el.scrollTop')
                            root.evaluate('el => window.spotRootBefore = el')
                            page.locator(f'a.room-summary[href="/rooms/{self.room.pk}/"]').click()
                            wait_for_trail_count(page, 1)
                            page.locator('.ui-workspace-trail-pane [data-open-room-boards]').click()
                            wait_for_trail_count(page, 2)
                            close_current_trail(page, 1)
                            close_current_trail(page, 0)
                            self.assertTrue(root.evaluate('el => window.spotRootBefore === el'))
                            self.assertAlmostEqual(root.evaluate('el => el.scrollTop'), scroll_top, delta=1)
                            self.inspect_root(page, name, 'room-close')
                            page.goto(f'{self.live_server_url}/?room={self.room.pk}', wait_until='domcontentloaded')
                            page.wait_for_selector('.thread-detail-pane [data-room-fragment]')
                            page.wait_for_timeout(350)
                            page.locator('#close-thread-detail').click()
                            self.inspect_root(page, name, 'url-room-close')
                            page.go_back(wait_until='domcontentloaded')
                            page.wait_for_selector('.thread-detail-pane [data-room-fragment]')
                            page.go_forward(wait_until='domcontentloaded')
                            self.inspect_root(page, name, 'history-forward')
                            page.reload(wait_until='domcontentloaded')
                            self.inspect_root(page, name, 'reload')
                            page.goto(f'{self.live_server_url}/?thread={self.threads[0].pk}', wait_until='domcontentloaded')
                            page.wait_for_selector(f'[data-thread-detail-pane="{self.threads[0].pk}"]:not([hidden])')
                            page.wait_for_timeout(350)
                            detail = page.locator('.thread-detail-pane').bounding_box()
                            self.assertAlmostEqual(detail['x'] + detail['width'], width, delta=1)
                            self.assertAlmostEqual(detail['width'], width if width <= 780 else width - 360, delta=1)
                            page.screenshot(path=self.output / f'{name}-thread-restored.png')
                            page.locator('#close-thread-detail').click()
                            self.inspect_root(page, name, 'thread-close')
                            self.assertEqual(errors, [], errors)
                        finally:
                            page.screenshot(path=self.output / f'{name}-final.png')
                            (self.output / f'{name}-errors.json').write_text(json.dumps(errors, indent=2), encoding='utf-8')
                            context.close()
            finally:
                browser.close()
