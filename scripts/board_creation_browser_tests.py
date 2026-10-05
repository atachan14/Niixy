"""Focused v0.11 Board creation UI checks against isolated SQLite."""
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from rooms.models import Board
from rooms.services import create_room
from scripts.browser_test_server import SharedSQLiteStaticFilesHandler


class BoardCreationBrowserTests(StaticLiveServerTestCase):
    static_handler = SharedSQLiteStaticFilesHandler

    def setUp(self):
        self.assertEqual(settings.DATABASES['default']['ENGINE'], 'django.db.backends.sqlite3')
        owner = get_user_model().objects.create_user('board_create_owner')
        self.room, _ = create_room(submission_id=uuid4(), owner=owner, name='Board Create Room',
            description='', latitude='35.681236', longitude='139.767125')
        self.client.force_login(owner)
        self.assertEqual(list(Board.objects.values_list('name', flat=True)), ['お知らせ', '掲示板'])
        from django.urls import reverse
        html = self.client.get(reverse('rooms:boards', args=[self.room.pk])).content.decode()
        self.assertLess(html.index('data-board-title="お知らせ"'), html.index('data-board-title="掲示板"'))


    def test_policy_picker_preserves_list_origin_and_submits(self):
        from playwright.sync_api import sync_playwright, expect
        output = Path(settings.BASE_DIR) / '.artifacts' / 'board-creation'
        output.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True)
            try:
                for viewport, size in [('desktop', {'width': 1280, 'height': 720}), ('mobile', {'width': 390, 'height': 844})]:
                    context = browser.new_context(viewport=size, is_mobile=viewport == 'mobile', has_touch=viewport == 'mobile')
                    context.add_cookies([{'name': settings.SESSION_COOKIE_NAME,
                        'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url': self.live_server_url}])
                    page = context.new_page()
                    page.set_default_timeout(7000)
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error'
                        and '400 (Bad Request)' not in msg.text and not msg.location.get('url', '').endswith('/favicon.ico') else None)
                    try:
                        page.goto(self.live_server_url + '/')
                        page.locator(f'a.room-summary[href="/rooms/{self.room.pk}/"]').click()
                        page.locator('.ui-workspace-trail-pane').nth(0).locator('[data-open-room-boards]').click()
                        origin = page.locator('.ui-workspace-trail-pane').nth(1)
                        panel = origin.locator('[data-collection-panel-id]').first
                        titles = panel.locator('[data-open-board] strong').all_text_contents()
                        self.assertLess(next(i for i, title in enumerate(titles) if title.startswith('お知らせ')), next(i for i, title in enumerate(titles) if title.startswith('掲示板')))
                        panel.locator('[data-collection-create-toggle]').click()
                        form = panel.locator('[data-board-action-kind="create"]')
                        form.locator('[name="name"]').fill('Created ' + viewport)
                        expect(form.locator('[data-account-condition-groups-input]')).to_have_count(4)
                        form.locator('summary').click()
                        page.wait_for_timeout(300)
                        origin_box = origin.bounding_box()
                        self.assertAlmostEqual(origin_box['x'] + origin_box['width'], size['width'], delta=1)
                        page.screenshot(path=output / f'{viewport}-form.png', full_page=True)
                        row = form.locator('.room-board-policy-editor-row').nth(1)
                        row.locator('[data-open-account-conditions]').click()
                        history = page.locator('.account-condition-pane')
                        expect(history).to_be_visible()
                        page.wait_for_timeout(300)
                        self.assertTrue(origin.evaluate('el => el.nextElementSibling.matches(".account-condition-pane")'))
                        self.assertNotEqual(origin.evaluate('el => getComputedStyle(el).display'), 'none')
                        box = history.bounding_box()
                        self.assertAlmostEqual(box['x'] + box['width'], size['width'], delta=1)
                        page.screenshot(path=output / f'{viewport}-picker.png', full_page=True)
                        history.locator('[data-browse-account-conditions]').click()
                        page.locator('.account-selector-pane .ui-summary-item').filter(has=page.locator('strong', has_text='Guest')).click()
                        history.locator('.ui-summary-item').filter(has=page.locator('strong', has_text='Guest')).click()
                        history.locator('[data-add-account-condition-group]').click()
                        history.locator('[data-close-account-conditions]').click()
                        expect(page.locator('.account-condition-pane')).to_have_count(0)
                        expect(page.locator('.ui-workspace-trail-pane')).to_have_count(2)
                        expect(form.locator('[name="name"]')).to_have_value('Created ' + viewport)
                        expect(row.locator('.niimap-selected-account-condition')).to_have_count(1)
                        policy_input = form.locator('[name="policy_view_allow_groups"]')
                        saved = policy_input.input_value()
                        policy_input.evaluate('(el) => el.value = "invalid"')
                        form.locator('[type="submit"]').click()
                        expect(form.locator('.room-form-error')).to_be_visible()
                        expect(form.locator('[name="name"]')).to_have_value('Created ' + viewport)
                        policy_input.evaluate('(el, value) => el.value = value', saved)
                        form.locator('[type="submit"]').click()
                        created = page.locator('.ui-workspace-trail-pane').nth(2)
                        expect(created.locator('[data-board-name]')).to_have_attribute('data-board-name', 'Created ' + viewport)
                        page.wait_for_timeout(300)
                        page.screenshot(path=output / f'{viewport}-created.png', full_page=True)
                        self.assertEqual(errors, [])
                    finally:
                        page.screenshot(path=output / f'{viewport}-final.png', full_page=True)
                        context.close()
            finally:
                browser.close()
        for name in ('Created desktop', 'Created mobile'):
            board = Board.objects.get(name=name)
            self.assertEqual(board.policy_conditions.count(), 4)
            self.assertEqual(board.policy_conditions.get(capability='view', decision='deny').definition, {'code': 'guest'})
