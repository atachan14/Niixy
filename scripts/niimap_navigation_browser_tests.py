"""Focused NiiMap navigation and map/search readiness QA on isolated SQLite."""
import json
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase

from events.models import Thread, ThreadAccessRule, ThreadPlacement, ThreadPost
from rooms.services import create_board, create_room
from scripts.browser_test_server import SharedSQLiteStaticFilesHandler


VIEWPORTS = [('desktop', {'width': 1280, 'height': 720}),
             ('mobile', {'width': 390, 'height': 844})]
STYLE = json.dumps({'version': 8, 'sources': {}, 'layers': [
    {'id': 'background', 'type': 'background', 'paint': {'background-color': '#f7f6f2'}}]})
WARNING = 'Source layer "oc-glacier" does not exist on source "geolonia" as specified by style layer "oc-glacier".'
RECORDS = []
MAP_PROBE = '''const QaMap = geolonia.Map;
geolonia.Map = new Proxy(QaMap, {construct(Target, args, NewTarget) {
  const map = Reflect.construct(Target, args, NewTarget); window.qaMap = map; return map;
}});\n'''


class NiiMapBrowserTests(StaticLiveServerTestCase):
    static_handler = SharedSQLiteStaticFilesHandler

    def setUp(self):
        self.assertEqual(settings.DATABASES['default']['ENGINE'], 'django.db.backends.sqlite3')
        self.assertNotEqual(urlsplit(self.live_server_url).port, 8000)
        self.owner = get_user_model().objects.create_user('niimap_transition_qa')
        self.room, _ = create_room(submission_id=uuid4(), owner=self.owner, name='Parent Room',
                                  description='', latitude='35.681236', longitude='139.767125')
        self.board, _ = create_board(submission_id=uuid4(), name='Spot Board',
                                    latitude='35.681236', longitude='139.767125')
        self.thread = Thread.objects.create(title='Parent Thread', creator=self.owner)
        ThreadPost.objects.create(thread=self.thread, number=1, creator=self.owner, body='Fixture post')
        ThreadPlacement.objects.create(thread=self.thread, latitude='35.681236', longitude='139.767125')
        for capability in ('view', 'write'):
            for audience in ('guest', 'account'):
                ThreadAccessRule.objects.create(thread=self.thread, capability=capability, audience=audience)
        self.output = Path(settings.BASE_DIR) / '.artifacts/niimap-fixes-2026-10-08'
        self.output.mkdir(parents=True, exist_ok=True)

    def context(self, browser, viewport, size, hold_style=False, hold_search=False, search_failure=False):
        context = browser.new_context(viewport=size, is_mobile=viewport == 'mobile', has_touch=viewport == 'mobile')
        page = context.new_page()
        page.set_default_timeout(7000)
        errors, held = [], {}
        allowed = urlsplit(self.live_server_url)

        def guard(route):
            target = urlsplit(route.request.url)
            if ((target.hostname in ('127.0.0.1', 'localhost') and target.port != allowed.port)
                    or target.hostname == 'niixy-psi.vercel.app'
                    or (route.request.method not in ('GET', 'HEAD') and target.netloc != allowed.netloc)):
                errors.append('forbidden QA endpoint or method: ' + target.netloc)
                route.abort()
            else:
                route.continue_()

        def style(route):
            if hold_style and 'style' not in held:
                held['style'] = route
            else:
                self.release_style(route)

        def search(route):
            if hold_search and 'search' not in held:
                held['search'] = route
            elif search_failure and 'failed_search' not in held:
                held['failed_search'] = True
                # A real response.json() failure, without unrelated console HTTP errors.
                route.fulfill(status=200, content_type='application/json', body='{')
            else:
                route.continue_()

        def instrument(route):
            response = route.fetch()
            route.fulfill(response=response, body=MAP_PROBE + response.text())

        context.route('**/*', guard)
        context.route('https://cdn.geolonia.com/style/**', style)
        context.route('**/threads/search/', search)
        context.route('**/static/events/map.js?*', instrument)
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('console', lambda message: errors.append(message.text) if message.type == 'error'
                and not message.location.get('url', '').endswith('/favicon.ico') else None)
        return context, page, errors, held

    @staticmethod
    def release_style(route, body=STYLE):
        route.fulfill(status=200, content_type='application/json',
                      headers={'Access-Control-Allow-Origin': '*'}, body=body)

    @staticmethod
    def settle(page):
        page.wait_for_timeout(350)

    def record(self, page, viewport, scenario, errors, failure=None):
        image = f'{viewport}-{scenario}.png'
        page.screenshot(path=self.output / image)
        state = page.evaluate('''() => {
          const root = document.querySelector('.thread-workspace'), track = root.querySelector('.thread-track');
          return {url:location.pathname+location.search,stage:track.niixyWorkspace.stage,
            offset:track.style.getPropertyValue('--ui-workspace-offset'),mapReady,searchReady,mapFailed,
            status:document.getElementById('niimap-list-status').textContent,
            statusHidden:document.getElementById('niimap-list-status').hidden,
            panes:Array.from(track.children).filter(e=>e.getBoundingClientRect().width).map(e=>{
              const r=e.getBoundingClientRect();return {class:e.className,left:r.left,right:r.right,width:r.width};})};
        }''')
        record = {'viewport': viewport, 'scenario': scenario, 'result': 'failed' if failure else 'passed',
                  'failure': str(failure) if failure else None, 'browser_errors': list(errors),
                  'state': state, 'screenshot': image}
        RECORDS.append(record)
        (self.output / 'result.json').write_text(json.dumps(RECORDS, ensure_ascii=False, indent=2), encoding='utf-8')
        print('QA_CASE ' + json.dumps({'viewport': viewport, 'scenario': scenario, 'result': record['result']}) , flush=True)

    def test_spot_board_and_native_parent_close(self):
        from playwright.sync_api import sync_playwright, expect
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='msedge', headless=True)
            try:
                for viewport, size in VIEWPORTS:
                    for origin in ('spot', 'thread', 'room'):
                        with self.subTest(viewport=viewport, origin=origin):
                            context, page, errors, _ = self.context(browser, viewport, size)
                            failure = None
                            try:
                                page.goto(self.live_server_url + ('/?room=' + str(self.room.pk) if origin == 'room' else '/'))
                                expect(page.locator('#thread-list')).to_be_visible()
                                if origin == 'spot':
                                    page.locator(f'.board-item[data-board-id="{self.board.pk}"] .board-summary').click()
                                    expect(page.locator('.ui-workspace-trail-pane [data-board-name]')).to_have_attribute('data-board-name', self.board.name)
                                elif origin == 'thread':
                                    page.locator(f'.thread-item[data-thread-id="{self.thread.pk}"] .thread-summary').click()
                                    page.locator(f'[data-thread-detail-pane="{self.thread.pk}"] .thread-post-info a[href="/accounts/{self.owner.username}/"]').click()
                                    expect(page.locator('.ui-workspace-trail-pane [data-account-fragment]')).to_be_visible()
                                else:
                                    parent = page.locator('.thread-detail-pane [data-room-fragment]')
                                    expect(parent).to_be_visible()
                                    parent.locator('[data-open-room-members]').click()
                                    page.locator(f'.niimap-room-list-pane a[href="/accounts/{self.owner.username}/"]').first.click()
                                    expect(page.locator('.ui-workspace-trail-pane [data-account-fragment]')).to_be_visible()
                                self.settle(page)
                                native = page.locator('.thread-track > .thread-detail-pane')
                                self.assertEqual(page.locator('.ui-workspace-trail-pane').count(), 1)
                                if origin == 'spot':
                                    self.assertEqual(native.evaluate('e=>e.getBoundingClientRect().width'), 0)
                                    adjacent = page.evaluate('''() => {
                                      const spot=document.querySelector('.thread-list-pane').getBoundingClientRect();
                                      const board=document.querySelector('.ui-workspace-trail-pane').getBoundingClientRect();
                                      return {gap:board.left-spot.right,right:board.right,scroll:document.querySelector('.thread-workspace').scrollLeft};
                                    }''')
                                    self.assertLessEqual(abs(adjacent['gap']), 1)
                                    self.assertLessEqual(abs(adjacent['right'] - size['width']), 1)
                                    self.assertEqual(adjacent['scroll'], 0)
                                else:
                                    self.assertGreater(native.evaluate('e=>e.getBoundingClientRect().width'), 0)
                                self.record(page, viewport, origin + '-open', errors)
                                previous = page.url
                                page.locator('.ui-workspace-trail-header .icon-button').click()
                                self.settle(page)
                                self.assertEqual(page.locator('.ui-workspace-trail-pane').count(), 0)
                                self.assertFalse(page.locator('.thread-workspace').evaluate('e=>e.classList.contains("is-workspace-trail-open")'))
                                self.assertGreater(native.evaluate('e=>e.getBoundingClientRect().width'), 0)
                                stage = page.evaluate('document.querySelector(".thread-track").niixyWorkspace.stage')
                                self.assertEqual(stage, {'spot': 'list', 'thread': 'detail', 'room': 'room-list'}[origin])
                                if origin == 'spot':
                                    self.assertEqual(urlsplit(page.url).query, '')
                                    self.assertEqual(page.locator('.thread-track').evaluate('e=>e.style.getPropertyValue("--ui-workspace-offset")'), '0px')
                                else:
                                    self.assertNotEqual(previous, page.url)
                                    expect(page.locator('.thread-detail-pane')).to_be_visible()
                                    if origin == 'room':
                                        page.locator('.niimap-room-list-pane > header .icon-button').click()
                                        self.settle(page)
                                        self.assertEqual(page.evaluate('document.querySelector(".thread-track").niixyWorkspace.stage'), 'room')
                                        expect(page.locator('.thread-detail-pane [data-room-fragment]')).to_be_visible()
                                self.assertEqual(errors, [])
                            except Exception as error:
                                failure = error
                                raise
                            finally:
                                self.record(page, viewport, origin + '-closed', errors, failure)
                                context.close()
            finally:
                browser.close()

    def test_map_warning_failure_search_and_retry(self):
        from playwright.sync_api import sync_playwright, expect
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='msedge', headless=True)
            try:
                for viewport, size in VIEWPORTS:
                    for scenario in ('warning-search-wait', 'failed-style-retry', 'failed-search-retry'):
                        with self.subTest(viewport=viewport, scenario=scenario):
                            context, page, errors, held = self.context(browser, viewport, size,
                                hold_style=scenario != 'failed-search-retry',
                                hold_search=scenario == 'warning-search-wait',
                                search_failure=scenario == 'failed-search-retry')
                            failure = None
                            try:
                                page.goto(self.live_server_url + '/', wait_until='domcontentloaded')
                                status = page.locator('#niimap-list-status')
                                retry = page.locator('#niimap-list-retry')
                                if scenario == 'warning-search-wait':
                                    page.wait_for_function('window.qaMap && !mapReady && !searchReady')
                                    expect(status).to_have_text('読み込み中...')
                                    page.evaluate('(message)=>qaMap.fire("error",{error:new Error(message)})', WARNING)
                                    expect(status).to_have_text('読み込み中...')
                                    expect(retry).to_be_hidden()
                                    # Matching text must still fail when it carries an HTTP failure.
                                    page.evaluate('(message)=>qaMap.fire("error",{error:Object.assign(new Error(message),{status:503})})', WARNING)
                                    expect(status).to_have_text('地図の読み込みに失敗しました。')
                                    expect(retry).to_be_visible()
                                    self.release_style(held['style'])
                                    page.wait_for_function('mapReady && !searchReady')
                                    expect(status).to_have_text('読み込み中...')
                                    expect(status).to_be_visible()
                                    self.record(page, viewport, 'search-wait-after-map-load', errors)
                                    held['search'].continue_()
                                elif scenario == 'failed-style-retry':
                                    page.wait_for_function('window.qaMap && searchReady && !mapReady')
                                    # Successful HTTP with invalid JSON genuinely fails the SDK's style load.
                                    self.release_style(held['style'], body='{')
                                    expect(status).to_have_text('地図の読み込みに失敗しました。')
                                    expect(retry).to_be_visible()
                                    self.assertFalse(page.evaluate('mapReady'))
                                    self.record(page, viewport, 'failed-style', errors)
                                    retry.click()
                                else:
                                    page.wait_for_function('mapReady && !searchReady')
                                    expect(status).to_be_visible()
                                    self.assertNotEqual(status.inner_text(), '地図の読み込みに失敗しました。')
                                    expect(retry).to_be_visible()
                                    self.record(page, viewport, 'failed-search', errors)
                                    retry.click()
                                expect(page.locator('#thread-list')).to_be_visible()
                                expect(status).to_be_hidden()
                                expect(retry).to_be_hidden()
                                self.assertTrue(page.evaluate('mapReady && searchReady && !mapFailed'))
                                self.assertEqual(errors, [])
                            except Exception as error:
                                failure = error
                                raise
                            finally:
                                self.record(page, viewport, scenario, errors, failure)
                                context.close()
            finally:
                browser.close()
