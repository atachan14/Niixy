"""Workspace regressions against a temporary SQLite DB, never the shared DB.

Run: .venv\\Scripts\\python.exe manage.py test scripts.workspace_browser_tests
"""

from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from scripts.browser_test_server import SharedSQLiteStaticFilesHandler

from events.models import Thread, ThreadAccessRule, ThreadPlacement, ThreadPost
from rooms.models import Board
from rooms.services import create_board, create_room


class WorkspaceBrowserTests(StaticLiveServerTestCase):
    static_handler = SharedSQLiteStaticFilesHandler

    def setUp(self):
        self.assertEqual(settings.DATABASES['default']['ENGINE'], 'django.db.backends.sqlite3')
        self.owner = get_user_model().objects.create_user('workspace_owner', password='test-only-password')
        self.room, _ = create_room(
            submission_id=uuid4(), owner=self.owner, name='Workspace Room', description='Test room',
            latitude='35.681236', longitude='139.767125',
        )
        self.board = Board.objects.get(name='掲示板')
        self.other_board, _ = create_board(
            submission_id=uuid4(), collection=self.room.collections.get(name='Main'), name='Second Board',
        )
        self.threads = []
        for index, board in enumerate([self.board, self.board, self.other_board]):
            thread = Thread.objects.create(creator=self.owner, title=f'Workspace Thread {index}')
            ThreadPost.objects.create(thread=thread, number=1, creator=self.owner, body='First post')
            ThreadPost.objects.create(thread=thread, number=2, creator=self.owner, body='Second post')
            ThreadPlacement.objects.create(thread=thread, kind=ThreadPlacement.BOARD, board=board)
            for capability in ['view', 'write']:
                for audience in ['guest', 'account']:
                    ThreadAccessRule.objects.create(thread=thread, capability=capability, audience=audience)
            self.threads.append(thread)

    def assert_track_motion(self, page, control, reduced=False):
        page.wait_for_timeout(350)
        motion = control.evaluate("""async el => {
            const track = document.querySelector('.ui-workspace-track');
            const events = [], samples = [];
            const record = e => {
                if (e.target === track && e.propertyName === 'transform') events.push(e.type);
            };
            track.addEventListener('transitionrun', record);
            track.addEventListener('transitionend', record);
            const x = () => new DOMMatrixReadOnly(getComputedStyle(track).transform).m41;
            const before = x();
            el.click();
            const suppressed = track.classList.contains('is-workspace-trail-aligning');
            const start = performance.now();
            await new Promise(resolve => {
                const sample = now => {
                    samples.push(x());
                    if (now - start < 650) requestAnimationFrame(sample);
                    else resolve();
                };
                requestAnimationFrame(sample);
            });
            track.removeEventListener('transitionrun', record);
            track.removeEventListener('transitionend', record);
            return {before, after: x(), samples, events, suppressed};
        }""")
        self.assertGreater(abs(motion['after'] - motion['before']), 1, motion)
        if reduced:
            self.assertEqual(motion['events'], [], motion)
        else:
            self.assertFalse(motion['suppressed'], motion)
            self.assertIn('transitionrun', motion['events'], motion)
            self.assertIn('transitionend', motion['events'], motion)
            low, high = sorted([motion['before'], motion['after']])
            self.assertTrue(any(low + 1 < x < high - 1 for x in motion['samples']), motion)

    def test_desktop_and_mobile_workspace(self):
        from playwright.sync_api import sync_playwright
        from scripts.browser_smoke import run_viewport, wait_for_trail_count, close_current_trail

        output = Path(settings.BASE_DIR) / '.artifacts' / 'workspace-regression'
        output.mkdir(parents=True, exist_ok=True)
        self.client.force_login(self.owner)
        session = self.client.cookies[settings.SESSION_COOKIE_NAME].value
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True)
            try:
                for name, size in [('desktop', {'width': 1280, 'height': 720}), ('mobile', {'width': 390, 'height': 844})]:
                    with self.subTest(viewport=name):
                        result = run_viewport(browser, self.live_server_url, output, name, size)
                        self.assertEqual(result.warnings, [], result.warnings)
                        context = browser.new_context(viewport=size, is_mobile=name == 'mobile', has_touch=name == 'mobile')
                        context.add_cookies([{'name': settings.SESSION_COOKIE_NAME, 'value': session, 'url': self.live_server_url}])
                        page = context.new_page()
                        errors = []
                        page.on('pageerror', lambda error: errors.append(str(error)))
                        page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
                        page.set_default_timeout(10000)
                        try:
                            page.goto(self.live_server_url + '/', wait_until='domcontentloaded')
                            self.assert_track_motion(page, page.locator(f'a.room-summary[href="/rooms/{self.room.pk}/"]'))
                            room = page.locator('.ui-workspace-trail-pane').nth(0)
                            self.assert_track_motion(page, room.locator('[data-open-room-boards]'))
                            boards = page.locator('.ui-workspace-trail-pane').nth(1)
                            boards.evaluate('(el) => { window.workspaceOrigin = el; }')
                            self.assert_track_motion(page, boards.locator(f'[data-open-board="{self.board.pk}"]'))
                            board = page.locator('.ui-workspace-trail-pane').nth(2)
                            self.assert_track_motion(page, board.locator(f'[data-room-thread="{self.threads[0].pk}"]'))
                            wait_for_trail_count(page, 4)
                            page.wait_for_selector('.ui-workspace-trail-pane:last-child [data-thread-detail-pane]')
                            page.locator('.ui-workspace-trail-pane').last.evaluate('(el) => el.dataset.discarded = "true"')
                            board.locator(f'[data-room-thread="{self.threads[1].pk}"]').evaluate('(el) => el.click()')
                            wait_for_trail_count(page, 4)
                            self.assertEqual(page.locator('[data-discarded]').count(), 0)
                            page.wait_for_selector(f'.ui-workspace-trail-pane:last-child [data-thread-detail-pane="{self.threads[1].pk}"]')

                            boards.locator(f'[data-open-board="{self.other_board.pk}"]').evaluate('(el) => el.click()')
                            wait_for_trail_count(page, 3)
                            self.assertTrue(page.evaluate('window.workspaceOrigin === document.querySelectorAll(".ui-workspace-trail-pane")[1]'))
                            page.wait_for_selector(f'.ui-workspace-trail-pane:last-child [data-room-thread="{self.threads[2].pk}"]')
                            room.locator('[data-open-room-members]').evaluate('(el) => el.click()')
                            wait_for_trail_count(page, 2)
                            page.wait_for_selector('.ui-workspace-trail-pane:last-child a[href^="/accounts/"]')
                            page.locator('.ui-workspace-trail-pane').last.locator('a[href^="/accounts/"]').first.click()
                            wait_for_trail_count(page, 3)
                            page.wait_for_selector('.ui-workspace-trail-pane:last-child [data-account-fragment]')
                            # The Room is preserved, but both Member and Account panes are replaced.
                            room.locator('[data-open-room-boards]').evaluate('(el) => el.click()')
                            wait_for_trail_count(page, 2)

                            # Hold a completed response so abort alone cannot hide a stale callback.
                            page.evaluate("""() => {
                                const original = window.fetch;
                                window.fetch = async (...args) => {
                                    const response = await original(...args);
                                    if (String(args[0]).includes('/boards/')) {
                                        const text = await response.text();
                                        await new Promise(resolve => { window.releaseWorkspaceResponse = resolve; });
                                        return new Response(text, {status: response.status});
                                    }
                                    return response;
                                };
                            }""")
                            boards.locator(f'[data-open-board="{self.board.pk}"]').click()
                            page.wait_for_function('!!window.releaseWorkspaceResponse')
                            room.locator('[data-open-room-members]').evaluate('(el) => el.click()')
                            wait_for_trail_count(page, 2)
                            page.evaluate('window.releaseWorkspaceResponse()')
                            page.wait_for_timeout(250)
                            wait_for_trail_count(page, 2)
                            self.assertEqual(page.locator('.ui-workspace-trail-pane [data-board-name]').count(), 0)
                            page.screenshot(path=output / f'{name}-replacement.png', full_page=True)
                            self.assert_track_motion(page, page.locator('.ui-workspace-trail-pane').last.locator('.ui-workspace-trail-header .icon-button'))
                            wait_for_trail_count(page, 1)
                            close_current_trail(page, 0)

                            # A native list with a trail descendant must use the same replacement rule.
                            page.goto(f'{self.live_server_url}/rooms/{self.room.pk}/?boards=1', wait_until='domcontentloaded')
                            page.locator(f'#room-list-content [data-open-board="{self.board.pk}"]').click()
                            page.locator(f'#room-thread-list-content [data-room-thread="{self.threads[0].pk}"]').click()
                            page.locator('#room-thread-detail-content a[href^="/accounts/"]').first.click()
                            wait_for_trail_count(page, 1)
                            page.locator('[data-open-room-members]').first.evaluate('(el) => el.click()')
                            wait_for_trail_count(page, 0)
                            self.assertIn('/rooms/', page.url)
                            self.assertIn('members=1', page.url)

                            page.goto(f'{self.live_server_url}/accounts/{self.owner.username}/?pane=room', wait_until='domcontentloaded')
                            source = page.locator('.account-room-list-pane a[href^="/rooms/"]').first
                            source.click()
                            page.locator('.ui-workspace-trail-pane [data-open-room-boards]').click()
                            wait_for_trail_count(page, 2)
                            source.evaluate('(el) => el.click()')
                            wait_for_trail_count(page, 1)
                            close_current_trail(page, 0)
                            self.assertIn('/accounts/', page.url)
                            self.assertIn('pane=room', page.url)

                            # Replacing Board's descendants also disposes its Account-condition picker.
                            page.goto(self.live_server_url + '/', wait_until='domcontentloaded')
                            page.locator(f'a.room-summary[href="/rooms/{self.room.pk}/"]').evaluate('(el) => el.click()')
                            room = page.locator('.ui-workspace-trail-pane').nth(0)
                            room.locator('[data-open-room-boards]').click()
                            page.locator('.ui-workspace-trail-pane').nth(1).locator(f'[data-open-board="{self.board.pk}"]').click()
                            board = page.locator('.ui-workspace-trail-pane').nth(2)
                            board.locator('[data-board-information-toggle]').click()
                            board.locator('[data-board-edit-toggle]').click()
                            self.assert_track_motion(page, board.locator('[data-open-account-conditions]').first)
                            page.wait_for_selector('.account-condition-pane')
                            self.assertEqual(page.locator('.account-condition-pane').count(), 1)
                            page.wait_for_timeout(350)
                            picker_box = page.locator('.account-condition-pane').bounding_box()
                            self.assertAlmostEqual(picker_box['x'] + picker_box['width'], size['width'], delta=2)
                            page.screenshot(path=output / f'{name}-conditions.png', full_page=True)
                            self.assert_track_motion(page, page.locator('[data-browse-account-conditions]'))
                            page.wait_for_selector('.account-selector-pane')
                            self.assert_track_motion(page, page.locator('[data-close-account-selector]'))
                            self.assert_track_motion(page, page.locator('[data-close-account-conditions]'))
                            board.locator('[data-open-account-conditions]').first.evaluate('(el) => el.click()')
                            page.wait_for_selector('.account-condition-pane')
                            room.locator('[data-open-room-members]').evaluate('(el) => el.click()')
                            wait_for_trail_count(page, 2)
                            self.assertEqual(page.locator('.account-condition-pane').count(), 0)

                            room.locator('[data-open-room-boards]').evaluate('(el) => el.click()')
                            page.locator('.ui-workspace-trail-pane').nth(1).locator(f'[data-open-board="{self.board.pk}"]').click()
                            board = page.locator('.ui-workspace-trail-pane').nth(2)
                            board.locator('[data-board-create-toggle]').click()
                            self.assert_track_motion(page, board.locator('[data-open-thread-field-selector]'))
                            self.assert_track_motion(page, page.locator('.thread-field-list-pane .icon-button'))
                            self.assertEqual(page.locator('.thread-create-module-selector-pane').count(), 0)
                            self.assert_track_motion(page, board.locator('[data-open-thread-field-selector]'))
                            room.locator('[data-open-room-members]').evaluate('(el) => el.click()')
                            wait_for_trail_count(page, 2)
                            self.assertEqual(page.locator('.thread-create-module-selector-pane').count(), 0)

                            room.locator('[data-open-room-boards]').evaluate('(el) => el.click()')
                            page.locator('.ui-workspace-trail-pane').nth(1).locator(f'[data-open-board="{self.board.pk}"]').click()
                            page.locator('.ui-workspace-trail-pane').nth(2).locator(f'[data-room-thread="{self.threads[0].pk}"]').click()
                            wait_for_trail_count(page, 4)
                            page.reload(wait_until='domcontentloaded')
                            page.wait_for_selector(f'#room-thread-detail-content [data-thread-detail-pane="{self.threads[0].pk}"]')
                            page.emulate_media(reduced_motion='reduce')
                            page.goto(self.live_server_url + '/', wait_until='domcontentloaded')
                            self.assert_track_motion(page, page.locator(f'a.room-summary[href="/rooms/{self.room.pk}/"]'), reduced=True)
                            self.assert_track_motion(page, page.locator('.ui-workspace-trail-header .icon-button'), reduced=True)
                            self.assertEqual(errors, [], errors)
                        finally:
                            page.screenshot(path=output / f'{name}-final.png', full_page=True)
                            context.close()
            finally:
                browser.close()

    def test_browser_smoke_cli(self):
        import subprocess
        import sys
        result = subprocess.run(
            [sys.executable, str(Path(settings.BASE_DIR) / 'scripts' / 'browser_smoke.py'),
             '--base-url', self.live_server_url],
            cwd=settings.BASE_DIR, capture_output=True, text=True, encoding='utf-8', timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        output = Path(settings.BASE_DIR) / '.artifacts' / 'browser-smoke'
        (output / 'run.log').write_text(result.stdout + result.stderr, encoding='utf-8')
