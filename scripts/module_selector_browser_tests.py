"""Focused creation-selector regression; isolated SQLite/LiveServer only."""
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse

from interfaces.models import InterfaceDraft, InterfaceDraftField
from interfaces.services import publish_draft, publish_field_definition
from rooms.models import Board
from rooms.services import create_room
from scripts.browser_test_server import SharedSQLiteStaticFilesHandler


VIEWPORTS = [('desktop', {'width': 1280, 'height': 720}),
             ('mobile', {'width': 390, 'height': 844})]
ORIGINS = ('map-create', 'niimap-board', 'workspace-board')
SELECTOR = '.thread-create-module-selector-pane'
LIST = '.thread-create-module-list-pane'
DETAIL = '.thread-create-module-detail-pane'


class ModuleSelectorBrowserTests(StaticLiveServerTestCase):
    static_handler = SharedSQLiteStaticFilesHandler

    def setUp(self):
        self.assertEqual(settings.DATABASES['default']['ENGINE'], 'django.db.backends.sqlite3')
        self.owner = get_user_model().objects.create_user('selector_owner')
        self.field, _ = publish_field_definition(
            creator=self.owner, name='Selector Field', field_type='short_text')
        draft = InterfaceDraft.objects.create(creator=self.owner, kind='thread', name='Selector IF')
        InterfaceDraftField.objects.create(draft=draft, definition=self.field, position=0)
        self.interface, _ = publish_draft(draft.pk)
        self.room, _ = create_room(submission_id=uuid4(), owner=self.owner, name='Selector Room',
                                   description='', latitude='35.681236', longitude='139.767125')
        self.board = Board.objects.get(name='掲示板')
        self.client.force_login(self.owner)
        # Keep earlier QA images intact; these outputs are ignored by Git.
        self.output = Path(settings.BASE_DIR) / '.artifacts' / 'module-selector-followup'
        self.output.mkdir(parents=True, exist_ok=True)

    def context(self, browser, viewport, size, reduced=False):
        context = browser.new_context(viewport=size, is_mobile=viewport == 'mobile',
                                      has_touch=viewport == 'mobile',
                                      reduced_motion='reduce' if reduced else 'no-preference')
        context.add_cookies([{'name': settings.SESSION_COOKIE_NAME,
                             'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value,
                             'url': self.live_server_url}])
        page = context.new_page()
        page.set_default_timeout(7000)
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error'
                and not msg.location.get('url', '').endswith('/favicon.ico') else None)
        return context, page, errors

    def open_origin(self, page, origin):
        if origin == 'map-create':
            page.goto(self.live_server_url + '/')
            page.locator('#niimap-create-toggle').click()
            page.evaluate('map.fire("click",{lngLat:{lng:139.767125,lat:35.681236}})')
            page.locator('#open-thread-create').click()
            form = page.locator('#thread-create-form')
        elif origin == 'niimap-board':
            page.goto(f'{self.live_server_url}/?room={self.room.pk}&room_list=boards&board={self.board.pk}')
            page.locator('[data-board-create-toggle]').click()
            form = page.locator('[data-board-thread-create]')
        else:
            page.goto(self.live_server_url + '/')
            page.locator(f'a.room-summary[href="/rooms/{self.room.pk}/"]').click()
            page.locator('.ui-workspace-trail-pane').nth(0).locator('[data-open-room-boards]').click()
            page.locator('.ui-workspace-trail-pane').nth(1).locator(f'[data-open-board="{self.board.pk}"]').click()
            board = page.locator('.ui-workspace-trail-pane').nth(2)
            board.locator('[data-board-create-toggle]').click()
            form = board.locator('[data-board-thread-create]')
        form.locator('[name="title"]').fill(f'Unsaved {origin} title')
        form.evaluate('el => {window.qaOriginForm = el;}')
        page.wait_for_timeout(300)
        return form

    def selected_input(self, form, kind):
        target = '[data-selected-thread-interface]' if kind == 'interface' else '[data-selected-direct-field]'
        return form.locator(target + ' input:not([type="hidden"])').first

    def assert_origin_and_current(self, page, form, current, size):
        # Measure settled geometry, retaining the 1px right-edge/adjacency contract.
        # Wait for animation state, never for the asserted coordinate to become true.
        page.evaluate('''() => new Promise(resolve =>
            requestAnimationFrame(() => requestAnimationFrame(resolve)))''')
        page.wait_for_function('''el => el.isConnected && !el.closest('.ui-workspace-track')
            .getAnimations().some(animation => animation.playState === 'running')''',
            arg=current.element_handle())
        page.evaluate('''() => new Promise(resolve =>
            requestAnimationFrame(() => requestAnimationFrame(resolve)))''')
        self.assertTrue(form.evaluate('el => el === window.qaOriginForm && el.isConnected'))
        layout = form.evaluate("""el => {
            const origin = el.closest('.niimap-room-thread-list-pane, .ui-workspace-trail-pane, .thread-detail-pane');
            const list = document.querySelector('.thread-create-module-list-pane');
            return {display:getComputedStyle(origin).display,
                    originRight:origin.getBoundingClientRect().right,
                    listLeft:list.getBoundingClientRect().left};
        }""")
        self.assertNotEqual(layout['display'], 'none')
        self.assertAlmostEqual(layout['originRight'], layout['listLeft'], delta=1)
        box = current.bounding_box()
        if abs(box['x'] + box['width'] - size['width']) > 1:
            print('Selector geometry failure:', current.evaluate('''el => ({
                pane:el.getBoundingClientRect().toJSON(),
                trackTransform:getComputedStyle(el.parentElement).transform,
                viewport:innerWidth, documentScroll:document.scrollingElement.scrollLeft,
                workspaceScroll:el.closest('.thread-workspace').scrollLeft,
                nativeScroll:el.parentElement.scrollLeft,
                classes:el.closest('.thread-workspace').className
            })'''), flush=True)
            page.screenshot(path=self.output / 'geometry-failure.png', full_page=True)
        self.assertAlmostEqual(box['x'] + box['width'], size['width'], delta=1)
        self.assertEqual(current.evaluate('el => el.closest(".thread-workspace").scrollLeft'), 0)
        close = current.locator('.ui-pane-header button').bounding_box()
        self.assertGreaterEqual(close['x'], -1)
        self.assertLessEqual(close['x'] + close['width'], size['width'] + 1)
        self.assertGreaterEqual(close['y'], 0)
        self.assertLessEqual(close['y'] + close['height'], size['height'])

    def exercise_selector(self, page, form, kind, size, value, screenshot=None):
        from playwright.sync_api import expect
        title = form.locator('[name="title"]').input_value()
        form.locator(f'[data-open-thread-{kind}-selector]').click()
        listing = page.locator(LIST)
        listing.wait_for()
        page.wait_for_timeout(300)
        self.assert_origin_and_current(page, form, listing, size)
        listing.locator('.ui-summary-item').first.click()
        detail = page.locator(DETAIL)
        detail.locator('.interface-implementation-editor input').first.fill(value)
        page.wait_for_timeout(300)
        self.assert_origin_and_current(page, form, detail, size)
        if screenshot:
            page.screenshot(path=self.output / screenshot, full_page=True)
        detail.locator('.interface-detail-actions button').click()
        expect(page.locator(SELECTOR)).to_have_count(0)
        expect(form.locator('[name="title"]')).to_have_value(title)
        expect(self.selected_input(form, kind)).to_have_value(value)
        # Re-select the same item, retaining values without adding a second item.
        form.locator(f'[data-open-thread-{kind}-selector]').click()
        page.locator(LIST + ' .ui-summary-item').first.click()
        expect(page.locator(DETAIL + ' .interface-implementation-editor input').first).to_have_value(value)
        page.locator(DETAIL + ' .ui-pane-header button').click()
        expect(page.locator(DETAIL)).to_have_count(0)
        page.wait_for_timeout(300)
        self.assert_origin_and_current(page, form, page.locator(LIST), size)
        page.locator(LIST + ' .ui-pane-header button').click()
        expect(page.locator(SELECTOR)).to_have_count(0)
        expect(form.locator('[name="title"]')).to_have_value(title)
        expect(self.selected_input(form, kind)).to_have_value(value)
        target = '[data-selected-thread-interface]' if kind == 'interface' else '[data-selected-direct-field]'
        expect(form.locator(target)).to_have_count(1)
        self.assertTrue(form.evaluate('el => el === window.qaOriginForm'))

    def test_create_selectors_preserve_origin_and_input(self):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True)
            try:
                for viewport, size in VIEWPORTS:
                    context, page, errors = self.context(browser, viewport, size)
                    try:
                        for origin in ORIGINS:
                            form = self.open_origin(page, origin)
                            room_width = (page.locator('.thread-detail-pane').bounding_box()['width']
                                          if origin == 'niimap-board' else None)
                            for kind in ('interface', 'field'):
                                with self.subTest(viewport=viewport, origin=origin, kind=kind):
                                    self.exercise_selector(page, form, kind, size, f'{origin} {kind}',
                                                           f'{viewport}-{origin}-{kind}.png')
                                    if origin == 'niimap-board':
                                        self.assertAlmostEqual(page.locator('.thread-detail-pane').bounding_box()['width'],
                                                               room_width, delta=1)
                                    if origin == 'workspace-board':
                                        self.assertEqual(page.locator('.ui-workspace-trail-pane').count(), 3)
                            self.assertEqual(errors, [])
                        # Search selectors remain distinct from creation selectors.
                        page.goto(self.live_server_url + '/')
                        page.locator('#niimap-search-toggle').click()
                        page.locator('details.niimap-search-section').filter(
                            has=page.locator('[data-search-select="interface"]')).locator(':scope > summary').click()
                        for kind in ('interface', 'field'):
                            page.locator(f'[data-search-select="{kind}"]').click()
                            page.locator(f'#thread-{kind}-selector').wait_for()
                            self.assertEqual(page.locator(SELECTOR).count(), 0)
                            if viewport == 'desktop':
                                self.assertEqual(page.locator('.thread-detail-pane').evaluate(
                                    'el => getComputedStyle(el).display'), 'none')
                            page.locator(f'#close-thread-{kind}-selector').click()
                        self.assertEqual(errors, [])
                    finally:
                        page.screenshot(path=self.output / f'{viewport}-normal-final.png', full_page=True)
                        context.close()
            finally:
                browser.close()

    def test_reduced_motion_creation_selectors(self):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True)
            try:
                for viewport, size in VIEWPORTS:
                    context, page, errors = self.context(browser, viewport, size, reduced=True)
                    try:
                        for origin in ORIGINS:
                            form = self.open_origin(page, origin)
                            page.evaluate("""() => {
                                window.qaMotionEvents = [];
                                document.addEventListener('transitionrun', event => {
                                    if (event.target.matches('.ui-workspace-track') && event.propertyName === 'transform')
                                        window.qaMotionEvents.push(event.propertyName);
                                });
                            }""")
                            self.assertTrue(page.evaluate('matchMedia("(prefers-reduced-motion: reduce)").matches'))
                            for kind in ('interface', 'field'):
                                with self.subTest(viewport=viewport, origin=origin, kind=kind):
                                    self.exercise_selector(page, form, kind, size, f'reduced {kind}')
                                    self.assertEqual(page.evaluate('window.qaMotionEvents'), [])
                                    self.assertEqual(page.locator('.ui-workspace-track').first.evaluate(
                                        'el => getComputedStyle(el).transitionDuration'), '0s')
                            page.screenshot(path=self.output / f'{viewport}-{origin}-reduced.png', full_page=True)
                        self.assertEqual(errors, [])
                    finally:
                        context.close()
            finally:
                browser.close()

    def test_native_focus_scroll_after_initial_alignment(self):
        from playwright.sync_api import sync_playwright
        cases = [('desktop', VIEWPORTS[0][1], 'map-create', 'field'),
                 ('mobile', VIEWPORTS[1][1], 'niimap-board', 'interface')]
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True)
            try:
                for viewport, size, origin, kind in cases:
                    with self.subTest(viewport=viewport, origin=origin, kind=kind):
                        context, page, errors = self.context(browser, viewport, size)
                        try:
                            form = self.open_origin(page, origin)
                            form.locator(f'[data-open-thread-{kind}-selector]').click()
                            page.locator(LIST + ' .ui-summary-item').first.click()
                            editor = page.locator(DETAIL + ' .interface-implementation-editor input').first
                            editor.wait_for()
                            # Reproduce the observed native scroll after the focus handler's
                            # initial alignment; the test never calls a product align API.
                            scroll = editor.evaluate('''async el => {
                                el.blur();
                                el.focus({preventScroll:true});
                                return await new Promise(resolve => requestAnimationFrame(() => {
                                    const viewport = el.closest('.thread-workspace');
                                    viewport.scrollLeft = 80;
                                    resolve(viewport.scrollLeft);
                                }));
                            }''')
                            self.assertEqual(scroll, 80)
                            self.assert_origin_and_current(page, form, page.locator(DETAIL), size)
                            page.screenshot(path=self.output / f'{viewport}-{origin}-focus-scroll.png', full_page=True)
                            self.assertEqual(errors, [])
                        finally:
                            context.close()
            finally:
                browser.close()

    def hold_detail(self, page, kind):
        path = reverse('interfaces:definition-detail', args=[self.interface.pk]) if kind == 'interface' else reverse(
            'interfaces:field-detail', args=[self.field.pk])
        page.evaluate("""path => {
            window.qaOriginalFetch ||= window.fetch;
            window.qaReleaseDetail = null;
            window.qaDetailDelivered = false;
            let holdNext = true;
            window.fetch = async (...args) => {
                const held = holdNext && new URL(String(args[0]), location.href).pathname === path;
                if (held) holdNext = false;
                const response = await window.qaOriginalFetch(...args);
                if (!held) return response;
                const text = await response.text();
                await new Promise(resolve => {window.qaReleaseDetail = resolve;});
                window.qaDetailDelivered = true;
                return new Response(text, {status:response.status, headers:response.headers});
            };
        }""", path)

    def release_detail(self, page):
        page.evaluate('window.qaReleaseDetail()')
        page.wait_for_function('window.qaDetailDelivered')
        page.wait_for_timeout(300)

    def test_late_details_after_close_and_reselection(self):
        from playwright.sync_api import expect, sync_playwright
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True)
            try:
                for viewport, size in VIEWPORTS:
                    context, page, errors = self.context(browser, viewport, size)
                    try:
                        for origin in ORIGINS:
                            for kind in ('interface', 'field'):
                                with self.subTest(viewport=viewport, origin=origin, kind=kind):
                                    form = self.open_origin(page, origin)
                                    title = form.locator('[name="title"]').input_value()
                                    form.locator(f'[data-open-thread-{kind}-selector]').click()
                                    self.hold_detail(page, kind)
                                    page.locator(LIST + ' .ui-summary-item').first.click()
                                    page.wait_for_function('typeof window.qaReleaseDetail === "function"')
                                    expect(page.locator(DETAIL + ' .ui-pane-loading')).to_be_visible()
                                    page.locator(DETAIL + ' .ui-pane-header button').click()
                                    expect(page.locator(DETAIL)).to_have_count(0)
                                    # Re-use the detail node with a new request before the old one returns.
                                    page.locator(LIST + ' .ui-summary-item').first.click()
                                    editor = page.locator(DETAIL + ' .interface-implementation-editor input').first
                                    editor.fill(f'new {kind}')
                                    self.release_detail(page)
                                    expect(editor).to_have_value(f'new {kind}')
                                    expect(page.locator(DETAIL + ' .interface-implementation-editor')).to_have_count(1)
                                    self.assert_origin_and_current(page, form, page.locator(DETAIL), size)
                                    page.locator(DETAIL + ' .interface-detail-actions button').click()
                                    expect(self.selected_input(form, kind)).to_have_value(f'new {kind}')
                                    # Destroy a pending selector, then open the other kind before releasing it.
                                    form.locator(f'[data-open-thread-{kind}-selector]').click()
                                    self.hold_detail(page, kind)
                                    page.locator(LIST + ' .ui-summary-item').first.click()
                                    page.wait_for_function('typeof window.qaReleaseDetail === "function"')
                                    page.locator(DETAIL + ' .ui-pane-header button').click()
                                    page.locator(LIST + ' .ui-pane-header button').click()
                                    other = 'field' if kind == 'interface' else 'interface'
                                    form.locator(f'[data-open-thread-{other}-selector]').click()
                                    page.locator(LIST + ' .ui-summary-item').first.click()
                                    page.locator(DETAIL + ' .interface-implementation-editor input').first.fill('other kind input')
                                    before = page.locator(DETAIL).inner_html()
                                    self.release_detail(page)
                                    self.assertEqual(page.locator(DETAIL).inner_html(), before)
                                    self.assertEqual(page.locator(DETAIL).evaluate(
                                        'el => el.classList.contains("thread-field-detail-pane")'), other == 'field')
                                    self.assert_origin_and_current(page, form, page.locator(DETAIL), size)
                                    page.screenshot(path=self.output / f'{viewport}-{origin}-{kind}-late.png', full_page=True)
                                    page.locator(DETAIL + ' .ui-pane-header button').click()
                                    page.locator(LIST + ' .ui-pane-header button').click()
                                    expect(page.locator(SELECTOR)).to_have_count(0)
                                    expect(form.locator('[name="title"]')).to_have_value(title)
                                    expect(self.selected_input(form, kind)).to_have_value(f'new {kind}')
                                    self.assertTrue(form.evaluate('el => el === window.qaOriginForm'))
                                    self.assertEqual(errors, [])
                    finally:
                        context.close()
            finally:
                browser.close()
