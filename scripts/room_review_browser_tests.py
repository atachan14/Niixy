"""Review CRUD and shared Pane regressions on isolated SQLite + Edge."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.db import connections
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase

from rooms.models import RoomReview
from events.models import Thread, ThreadAccessRule, ThreadPlacement, ThreadPost
from rooms.models import Board
from rooms.services import create_room
from scripts.browser_test_server import SharedSQLiteStaticFilesHandler


class RoomReviewBrowserTests(StaticLiveServerTestCase):
    static_handler = SharedSQLiteStaticFilesHandler

    def review_row(self):
        # Playwright's sync API runs an event loop on the calling thread.
        # Read SQLite from a worker and share the request serialization lock.
        def read():
            try:
                with SharedSQLiteStaticFilesHandler.request_lock:
                    return RoomReview.objects.filter(author_id=self.author.pk, target_id=self.room.pk).values('id', 'sentiment', 'revision', 'body').first()
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=1) as worker:
            return worker.submit(read).result()

    def setUp(self):
        self.assertEqual(settings.DATABASES['default']['ENGINE'], 'django.db.backends.sqlite3')
        User = get_user_model()
        self.author = User.objects.create_user('review_browser_author')
        self.target = User.objects.create_user('review_browser_target')
        self.target.niixy_profile.display_name = '紹介される人'
        self.target.niixy_profile.save()
        self.room, _ = create_room(submission_id=uuid4(), owner=self.target, name='Room Review QA',
            description='SQLite only', latitude='35.681236', longitude='139.767125')
        for index in range(13):
            author = User.objects.create_user(f'review_fixture_{index}')
            author.niixy_profile.display_name = '長い表示名テスト'
            author.niixy_profile.save()
            RoomReview.objects.create(author=author, target=self.room,
                sentiment='love' if index % 2 == 0 else 'hate', body=f'紹介文 {index}\n二行目の文章です。')
        board = Board.objects.get(placement__collection__room=self.room, name='掲示板')
        for location in [board, None]:
            thread = Thread.objects.create(creator=self.target, title='Review QA Thread')
            ThreadPost.objects.create(thread=thread, number=1, creator=self.target, body='最初の投稿')
            ThreadPost.objects.create(thread=thread, number=2, creator=self.target, body='返信')
            ThreadPlacement.objects.create(thread=thread,
                kind=ThreadPlacement.BOARD if location else ThreadPlacement.NII_MAP, board=location,
                latitude=None if location else '35.681236', longitude=None if location else '139.767125')
            for capability in ['view', 'write']:
                for audience in ['guest', 'account']:
                    ThreadAccessRule.objects.create(thread=thread, capability=capability, audience=audience)
        self.client.force_login(self.author)

    def test_room_review_pc_mobile_and_existing_smoke(self):
        from playwright.sync_api import sync_playwright, expect
        from scripts.browser_smoke import main as smoke_main, wait_for_trail_count

        output = Path(settings.BASE_DIR) / '.artifacts' / 'room-review'
        output.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True)
            try:
                for name, size in [('desktop', {'width': 1280, 'height': 900}), ('mobile', {'width': 390, 'height': 844})]:
                    context = browser.new_context(viewport=size, is_mobile=name == 'mobile', has_touch=name == 'mobile')
                    context.add_cookies([{'name': settings.SESSION_COOKIE_NAME, 'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url': self.live_server_url}])
                    page = context.new_page(); page.set_default_timeout(10000)
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' and not msg.location.get('url', '').endswith('/favicon.ico') else None)
                    page.goto(self.live_server_url + f'/rooms/{self.room.pk}/')
                    section = page.locator('.room-overview-pane [data-review-section]')
                    expect(section.locator('.review-post')).to_have_count(3)
                    expect(section.locator('[data-review-edit=love]').first).to_have_attribute('aria-pressed', 'false')
                    # Drafts, Close/Cancel and saved header stay independent.
                    section.locator('[data-review-edit=love]').first.click()
                    form = page.locator('[data-review-form]')
                    expect(form).to_be_visible()
                    form.locator('textarea').fill('保存前の紹介文 ' + name)
                    form.locator('[data-review-cancel]').click()
                    wait_for_trail_count(page, 0)
                    self.assertIsNone(self.review_row())
                    section.locator('[data-review-edit=hate]').first.click()
                    expect(form.locator('textarea')).to_have_value('保存前の紹介文 ' + name)
                    expect(form.locator('[value=hate]')).to_be_checked()
                    form.locator('textarea').fill(' \n\u3000')
                    form.locator('[type=submit]').click()
                    expect(form.locator('.review-error')).to_contain_text('紹介文を入力')
                    form.locator('textarea').fill('保存した紹介文 ' + name + '\n<script>alert(1)</script>')
                    wait_for_trail_count(page, 1)
                    page.wait_for_function("""() => {
                        const pane = document.querySelector('.ui-workspace-trail-pane');
                        const box = pane.getBoundingClientRect();
                        return box.left >= -1 && Math.abs(box.right - innerWidth) < 2;
                    }""")
                    self.assertFalse(form.evaluate('el => el.scrollWidth > el.clientWidth + 1'))
                    page.screenshot(path=output / f'{name}-editor.png')
                    # Delay one write and dispatch twice to exercise the pending guard.
                    page.evaluate("""() => { window.reviewFetch = window.fetch; window.reviewSubmitCount = 0;
                        window.fetch = (...args) => {
                            if (!String(args[0]).endsWith('/reviews/save/')) return window.reviewFetch(...args);
                            window.reviewSubmitCount++;
                            return new Promise(resolve => setTimeout(resolve, 300)).then(() => window.reviewFetch(...args));
                        }; }""")
                    form.evaluate("el => { el.dispatchEvent(new Event('submit', {bubbles:true,cancelable:true})); el.dispatchEvent(new Event('submit', {bubbles:true,cancelable:true})); }")
                    expect(form).to_have_count(0)
                    self.assertEqual(page.evaluate('window.reviewSubmitCount'), 1)
                    page.evaluate('() => { window.fetch = window.reviewFetch; }')
                    expect(section.locator('[data-review-edit=hate]').first).to_have_attribute('aria-pressed', 'true')
                    own = self.review_row()
                    self.assertEqual((own['sentiment'], own['revision']), ('hate', 1))
                    expect(section.locator('.thread-post-body').first).to_contain_text('<script>alert(1)</script>')
                    section.scroll_into_view_if_needed()
                    page.screenshot(path=output / f'{name}-review.png')
                    self.assertFalse(section.evaluate('el => el.scrollWidth > el.clientWidth + 1'))

                    # Existing Review -> Hate/Love changes only in the editor until Save.
                    section.locator('[data-review-edit=love]').first.click()
                    expect(form.locator('textarea')).to_contain_text('保存した紹介文')
                    self.assertEqual(self.review_row()['sentiment'], 'hate')
                    form.locator('textarea').fill('Closeで保つ本文 ' + name)
                    page.locator('.ui-workspace-trail-pane .ui-workspace-trail-header .icon-button').click()
                    section.locator('[data-review-edit=love]').first.click()
                    expect(form.locator('textarea')).to_have_value('Closeで保つ本文 ' + name)
                    # Failed transport leaves input editable and retryable.
                    page.evaluate("""() => { window.reviewFetch = window.fetch; window.fetch = (...args) => String(args[0]).endsWith('/reviews/save/') ? Promise.reject(new Error('テスト通信失敗')) : window.reviewFetch(...args); }""")
                    form.locator('[type=submit]').click()
                    expect(form.locator('.review-error')).to_contain_text('テスト通信失敗')
                    expect(form.locator('textarea')).to_have_value('Closeで保つ本文 ' + name)
                    expect(form.locator('[type=submit]')).to_be_enabled()
                    page.evaluate('() => { window.fetch = window.reviewFetch; }')
                    form.locator('[type=submit]').click()
                    expect(form).to_have_count(0)
                    expect(section.locator('[data-review-edit=love]').first).to_have_attribute('aria-pressed', 'true')
                    own = self.review_row(); self.assertEqual((own['sentiment'], own['revision']), ('love', 2))

                    # Close during a write, then reopen: wait for its committed
                    # revision and do not close the newly opened editor on reply.
                    section.locator('[data-review-edit=love]').first.click()
                    form.locator('textarea').fill('送信中Close後も保存 ' + name)
                    page.evaluate("""() => { window.reviewFetch = window.fetch; window.fetch = (...args) =>
                        String(args[0]).endsWith('/reviews/save/')
                        ? new Promise(resolve => setTimeout(resolve, 300)).then(() => window.reviewFetch(...args))
                        : window.reviewFetch(...args); }""")
                    form.locator('[type=submit]').click()
                    page.locator('.ui-workspace-trail-header .icon-button').click()
                    section.locator('[data-review-edit=hate]').first.click()
                    expect(form.locator('textarea')).to_have_value('送信中Close後も保存 ' + name)
                    expect(form.locator('[name=revision]')).to_have_value('3')
                    page.evaluate('() => { window.fetch = window.reviewFetch; }')
                    form.locator('[data-review-cancel]').click()
                    wait_for_trail_count(page, 0)
                    expect(section.locator('[data-review-edit=love]').first).to_have_attribute('aria-pressed', 'true')

                    section.locator('[data-review-expand]').click()
                    expect(section.locator('.review-post')).to_have_count(10)
                    section.locator('[data-review-go-page="2"]').click()
                    expect(section.locator('.review-post')).to_have_count(4)
                    section.locator('[data-review-collapse]').click()
                    expect(section.locator('.review-post')).to_have_count(3)
                    section.locator('[data-review-tab=love]').click()
                    expect(section.locator('[data-review-tab=love]')).to_have_attribute('aria-selected', 'true')
                    expect(section.locator('.review-sentiment')).to_have_text(['Love'] * 3)
                    section.locator('[data-review-tab=hate]').click()
                    expect(section.locator('.review-sentiment')).to_have_text(['Hate'] * 3)
                    section.locator('[data-review-tab=all]').click()
                    # Late tab response may not replace a newer selection.
                    page.evaluate("""() => { window.reviewFetch = window.fetch; window.fetch = (...args) => {
                        if (!String(args[0]).includes('/reviews/?') || !String(args[0]).includes('review_filter=love')) return window.reviewFetch(...args);
                        args[1] = {...args[1], signal: undefined};
                        return window.reviewFetch(...args).then(response => new Promise(resolve => setTimeout(() => resolve(response), 300)));
                    }; }""")
                    section.locator('[data-review-tab=love]').evaluate('el => el.click()')
                    section.locator('[data-review-tab=hate]').evaluate('el => el.click()')
                    expect(section.locator('[data-review-tab=hate]')).to_have_attribute('aria-selected', 'true')
                    page.wait_for_timeout(400)
                    page.evaluate('() => { window.fetch = window.reviewFetch; }')
                    expect(section.locator('[data-review-tab=hate]')).to_have_attribute('aria-selected', 'true')
                    section.locator('[data-review-tab=all]').click()

                    # Author link opens retained Account; editing nested Review uses the same Pane.
                    section.locator('.review-post-info a').first.click()
                    wait_for_trail_count(page, 1)
                    nested = page.locator('.ui-workspace-trail-pane [data-review-section]')
                    # This Account belongs to the current author: self actions disabled.
                    expect(nested.locator('[data-review-edit=love]')).to_be_disabled()
                    page.locator('.ui-workspace-trail-header .icon-button').click()
                    page.evaluate('(url) => NiixyWorkspaceTrail.open(url)', f'/rooms/{self.room.pk}/')
                    wait_for_trail_count(page, 1)
                    nested = page.locator('.ui-workspace-trail-pane [data-review-section]')
                    nested.locator('[data-review-edit=hate]').first.click()
                    wait_for_trail_count(page, 2)
                    form.locator('textarea').fill('Nestedの未保存本文')
                    form.locator('[data-review-cancel]').click()
                    wait_for_trail_count(page, 1)
                    expect(nested.locator('[data-review-edit=love]').first).to_have_attribute('aria-pressed', 'true')
                    page.locator('.ui-workspace-trail-header .icon-button').click()
                    wait_for_trail_count(page, 0)
                    # A dismissed editor's late GET cannot recreate the Pane.
                    page.evaluate("""() => { window.reviewFetch = window.fetch; window.fetch = (...args) => {
                        if (!String(args[0]).includes('/reviews/editor/?')) return window.reviewFetch(...args);
                        args[1] = {...args[1], signal: undefined};
                        return window.reviewFetch(...args).then(response => new Promise(resolve => setTimeout(() => resolve(response), 300)));
                    }; }""")
                    section.locator('[data-review-edit=love]').first.click()
                    page.locator('.ui-workspace-trail-header .icon-button').click()
                    page.wait_for_timeout(400)
                    expect(form).to_have_count(0)
                    page.evaluate('() => { window.fetch = window.reviewFetch; }')
                    section.locator('[data-review-edit=love]').first.click()
                    form.locator('[data-review-delete]').click()
                    expect(form).to_have_count(0)
                    expect(section.locator('[data-review-edit=love]').first).to_have_attribute('aria-pressed', 'false')
                    self.assertIsNone(self.review_row())

                    context.clear_cookies()
                    page.reload()
                    expect(section.locator('[data-review-edit=love]')).to_be_disabled()
                    expect(section.locator('[data-review-edit=hate]')).to_be_disabled()
                    expect(section.locator('.review-post')).to_have_count(3)
                    section.scroll_into_view_if_needed()
                    page.screenshot(path=output / f'{name}-guest.png')
                    self.assertEqual(errors, [])
                    context.close()
            finally:
                browser.close()

        # Execute the unchanged smoke script's entry point against this verified
        # isolated LiveServer, including both Workspace and Account captures.
        with patch('sys.argv', ['scripts/browser_smoke.py', '--base-url', self.live_server_url,
                               '--output-dir', str(Path(settings.BASE_DIR) / '.artifacts' / 'browser-smoke')]):
            self.assertEqual(smoke_main(), 0)
