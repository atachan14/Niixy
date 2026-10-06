"""Account Board workflow and shared smoke checks on an isolated LiveServer."""
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse

from events.models import Thread, ThreadAccessRule, ThreadPlacement, ThreadPost
from interfaces.models import FieldType, ThreadDirectField
from interfaces.services import publish_field_definition
from rooms.models import Board
from rooms.services import create_room
from scripts.browser_test_server import SharedSQLiteStaticFilesHandler


class AccountBoardBrowserTests(StaticLiveServerTestCase):
    static_handler = SharedSQLiteStaticFilesHandler

    def setUp(self):
        self.assertEqual(settings.DATABASES['default']['ENGINE'], 'django.db.backends.sqlite3')
        self.owner = get_user_model().objects.create_user('account_board_browser')
        self.field, _ = publish_field_definition(creator=self.owner, name='Diary Field', field_type=FieldType.SHORT_TEXT)
        self.room, _ = create_room(submission_id=uuid4(), owner=self.owner, name='Account Board Test Room',
                                  description='', latitude='35.681236', longitude='139.767125')
        board = Board.objects.get(placement__collection__room=self.room, name='掲示板')
        for index in range(3):
            thread = Thread.objects.create(creator=self.owner, title=f'Smoke Thread {index}')
            ThreadPost.objects.create(thread=thread, number=1, creator=self.owner, body='Smoke initial body')
            ThreadPost.objects.create(thread=thread, number=2, creator=self.owner, body='Smoke reply body')
            ThreadPlacement.objects.create(thread=thread, kind='board', board=board)
            ThreadAccessRule.objects.bulk_create([
                ThreadAccessRule(thread=thread, capability=capability, audience=audience)
                for capability in ('view', 'write') for audience in ('guest', 'account')
            ])
        self.client.force_login(self.owner)

    def test_account_board_workflow_desktop_and_mobile(self):
        from playwright.sync_api import expect, sync_playwright
        from scripts.browser_smoke import wait_for_trail_count
        output = Path(settings.BASE_DIR) / '.artifacts' / 'account-boards'
        output.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True)
            try:
                for viewport, size in [('desktop', {'width': 1280, 'height': 720}), ('mobile', {'width': 390, 'height': 844})]:
                    with self.subTest(viewport=viewport):
                        context = browser.new_context(viewport=size, is_mobile=viewport == 'mobile', has_touch=viewport == 'mobile')
                        context.add_cookies([{'name': settings.SESSION_COOKIE_NAME,
                            'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url': self.live_server_url}])
                        page = context.new_page()
                        page.set_default_timeout(8000)
                        errors = []
                        page.on('pageerror', lambda error: errors.append(str(error)))
                        page.on('console', lambda message: errors.append(message.text) if message.type == 'error'
                                and not message.location.get('url', '').endswith('/favicon.ico') else None)
                        try:
                            page.goto(self.live_server_url + reverse('accounts:detail', args=[self.owner.username]))
                            page.locator('.account-overview-pane [data-open-account-boards]').click()
                            wait_for_trail_count(page, 0)
                            listing = page.locator('.account-board-list-pane')
                            listing.locator('[data-collection-id]').first.click()
                            expect(listing.locator('[data-board-title="日記"]')).to_be_visible()
                            page.screenshot(path=output / f'{viewport}-board-list.png', full_page=True)
                            listing.locator('[data-ui-tab="fav"]').click()
                            expect(listing.locator('[data-ui-tab-panel="fav"]')).to_be_visible()
                            listing.locator('[data-ui-tab="bad"]').click()
                            expect(listing.locator('[data-ui-tab-panel="bad"]')).to_be_visible()
                            # Creation API remains intact; AccountPage has no List-create entry.
                            from accounts.content_lists import route
                            response=context.request.post(self.live_server_url+route('board','list-create'),form={'name':'Collection '+viewport,'submission_id':str(uuid4())},headers={'X-CSRFToken':page.locator('[name=csrfmiddlewaretoken]').first.input_value()})
                            self.assertEqual(response.status,201);new_id=response.json()['list_id']
                            page.evaluate("()=>document.dispatchEvent(new CustomEvent('niixy:content-list-changed',{detail:{kind:'board'}}))")
                            expect(listing.locator(f'[data-collection-id="{new_id}"]')).to_have_count(1)
                            listing.locator(f'[data-collection-id="{new_id}"]').click()
                            panel = listing.locator('.room-collection-panel.is-active')
                            expect(panel.locator('[data-collection-create-toggle]')).to_be_visible()
                            panel.locator('[data-collection-create-toggle]').click()
                            board_form = panel.locator('[data-board-action-kind="create"]')
                            board_form.locator('[name="name"]').fill('Board ' + viewport)
                            board_form.locator('summary').click()
                            board_form.locator('[data-open-account-conditions]').first.click()
                            history = page.locator('.account-condition-pane')
                            expect(history).to_be_visible()
                            history.locator('[data-close-account-conditions]').click()
                            expect(history).to_have_count(0)
                            expect(board_form.locator('[name="name"]')).to_have_value('Board ' + viewport)
                            board_form.locator('[type="submit"]').click()
                            wait_for_trail_count(page, 1)
                            board = page.locator('.ui-workspace-trail-pane').nth(0)
                            expect(board.locator('[data-board-name]')).to_have_attribute('data-board-name', 'Board ' + viewport)
                            board.locator('[data-board-create-toggle]').click()
                            form = board.locator('[data-board-thread-create]')
                            form.locator('[name="title"]').fill('Account Thread ' + viewport)
                            form.locator('[name="body"]').fill('Body ' + viewport)
                            form.locator('[data-open-thread-field-selector]').click()
                            page.locator('.thread-create-module-list-pane .ui-summary-item').first.click()
                            field_detail = page.locator('.thread-create-module-detail-pane')
                            field_detail.locator('.interface-implementation-editor input').first.fill('Field ' + viewport)
                            page.wait_for_timeout(300)
                            page.screenshot(path=output / f'{viewport}-field-picker.png', full_page=True)
                            field_detail.locator('.interface-detail-actions button').click()
                            expect(form.locator('[data-thread-selected-direct-fields]')).to_contain_text('Diary Field')
                            form.locator('[type="submit"]').click()
                            wait_for_trail_count(page, 2)
                            detail = page.locator('.ui-workspace-trail-pane').nth(1)
                            expect(detail.locator('.thread-detail')).to_contain_text('Body ' + viewport)
                            reply = detail.locator('.thread-reply-form')
                            reply.locator('[name="body"]').fill('Reply ' + viewport)
                            reply.locator('[type="submit"]').click()
                            expect(detail.locator('.thread-detail')).to_contain_text('Reply ' + viewport)
                            page.screenshot(path=output / f'{viewport}-workspace.png', full_page=True)
                            page.reload(wait_until='domcontentloaded')
                            wait_for_trail_count(page, 2)
                            expect(page.locator('.ui-workspace-trail-pane').nth(1).locator('.thread-detail')).to_contain_text('Reply ' + viewport)
                            for count in (1, 0):
                                page.locator('.ui-workspace-trail-pane').last.locator('.ui-workspace-trail-header .icon-button').click()
                                wait_for_trail_count(page, count)
                            expect(listing.locator('.room-collection-panel.is-active')).to_contain_text('Board ' + viewport)
                            self.assertNotIn('board=',page.url);self.assertNotIn('thread=',page.url)
                            page.reload();wait_for_trail_count(page,0)
                            expect(listing.locator('.room-collection-panel.is-active')).to_contain_text('Board ' + viewport)
                            page.locator('.account-overview-pane [data-open-account-threads]').evaluate('el => el.click()')
                            wait_for_trail_count(page, 0)
                            page.locator('.account-overview-pane [data-open-account-boards]').evaluate('el => el.click()')
                            wait_for_trail_count(page, 0)
                            listing.locator('[data-collection-id]').first.click()
                            listing.locator('[data-board-title="日記"]').click()
                            wait_for_trail_count(page, 1)
                            page.screenshot(path=output / f'{viewport}-diary.png', full_page=True)
                            # A nested Account uses the same common Board flow.
                            page.goto(self.live_server_url + '/')
                            page.evaluate('(url) => NiixyWorkspaceTrail.open(url)', reverse('accounts:detail', args=[self.owner.username]))
                            wait_for_trail_count(page, 1)
                            page.locator('.ui-workspace-trail-pane [data-open-account-boards]').click()
                            wait_for_trail_count(page, 2)
                            page.locator('.ui-workspace-trail-pane').nth(1).locator('[data-collection-id]').first.click()
                            page.locator('.ui-workspace-trail-pane').nth(1).locator('[data-board-title="日記"]').click()
                            wait_for_trail_count(page, 3)
                            expect(page.locator('.ui-workspace-trail-pane').nth(2).locator('[data-board-name]')).to_have_attribute('data-board-name', '日記')
                            self.assertEqual(errors, [])
                        finally:
                            page.screenshot(path=output / f'{viewport}-final.png', full_page=True)
                            context.close()
            finally:
                browser.close()
        for viewport in ('desktop', 'mobile'):
            thread = Thread.objects.get(title='Account Thread ' + viewport)
            self.assertEqual(ThreadDirectField.objects.get(thread=thread).binding.value.value, 'Field ' + viewport)

    def test_shared_browser_smoke_on_isolated_server(self):
        result = subprocess.run([
            sys.executable, str(Path(settings.BASE_DIR) / 'scripts' / 'browser_smoke.py'),
            '--base-url', self.live_server_url,
        ], cwd=settings.BASE_DIR, capture_output=True, text=True, encoding='utf-8', timeout=180)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout)
