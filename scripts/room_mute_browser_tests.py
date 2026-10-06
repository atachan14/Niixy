"""Room/Account draft isolation, RoomMute and Account Room tabs in isolated Edge."""
from pathlib import Path
from uuid import uuid4
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client
from django.urls import reverse
from accounts.models import AccountReview
from rooms.models import RoomMute, RoomReview
from rooms.services import create_room
from scripts.browser_test_server import SharedSQLiteStaticFilesHandler


class RoomMuteBrowserTests(StaticLiveServerTestCase):
    static_handler = SharedSQLiteStaticFilesHandler

    def setUp(self):
        self.assertEqual(settings.DATABASES['default']['ENGINE'], 'django.db.backends.sqlite3')
        User = get_user_model()
        self.viewer = User.objects.create_user('room_browser_viewer')
        self.owner = User.objects.create_user('room_browser_owner')
        self.room = self.make_room('Room draft and Mute QA')
        self.hate_room = self.make_room('Hate Room QA')
        # An Account username that equals a Room PK must never share its draft key.
        self.numeric = User.objects.create_user(str(self.room.pk))
        AccountReview.objects.create(author=self.viewer, target=self.numeric, sentiment='love', body='ACCOUNT SAVED')
        for index in range(21):
            room = self.make_room(f'Love Room {index}')
            RoomReview.objects.create(author=self.viewer, target=room, sentiment='love', body='List fixture')
        RoomReview.objects.create(author=self.viewer, target=self.room, sentiment='love', body='ROOM SAVED')
        RoomReview.objects.create(author=self.viewer, target=self.hate_room, sentiment='hate', body='HATE SAVED')
        for index in range(12):
            author = User.objects.create_user(f'room_mute_browser_fixture_{index}')
            author.niixy_profile.display_name = '非常に長い名前のMuter紹介表示'
            author.niixy_profile.save()
            RoomMute.objects.create(muter=author, room=self.room)
        self.client.force_login(self.viewer)
        self.owner_client = Client(); self.owner_client.force_login(self.owner)

    def make_room(self, name):
        return create_room(submission_id=uuid4(), owner=self.owner, name=name, description='SQLite only', latitude='35', longitude='139')[0]

    def context(self, browser, name, size):
        context = browser.new_context(viewport=size, is_mobile=name == 'mobile', has_touch=name == 'mobile')
        context.add_cookies([{'name': settings.SESSION_COOKIE_NAME, 'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url': self.live_server_url}])
        return context

    def observe(self, context):
        page = context.new_page(); page.set_default_timeout(10000)
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' and not msg.location.get('url', '').endswith('/favicon.ico') else None)
        return page, errors

    def test_room_mute_draft_isolation_failure_restore_public_muters_pc_mobile(self):
        from playwright.sync_api import sync_playwright, expect
        from scripts.browser_smoke import wait_for_trail_count
        output = Path(settings.BASE_DIR) / '.artifacts' / 'room-mute'; output.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='msedge', headless=True)
            try:
                for name, size in [('desktop', {'width': 1280, 'height': 900}), ('mobile', {'width': 390, 'height': 844})]:
                    with self.subTest(viewport=name):
                        context = self.context(browser, name, size)
                        try:
                            page, errors = self.observe(context)
                            page.goto(self.live_server_url + reverse('rooms:detail', args=[self.room.pk]))
                            section = page.locator('.room-overview-pane [data-review-section]')
                            form = page.locator('[data-review-form]')
                            section.locator('[data-review-edit=love]').first.click()
                            expect(form.locator('textarea')).to_have_value('ROOM SAVED')
                            form.locator('textarea').fill('ROOM DRAFT ' + name)
                            form.locator('[data-review-cancel]').click(); wait_for_trail_count(page, 0)
                            page.evaluate('(url) => NiixyWorkspaceTrail.open(url, document.querySelector(".room-overview-pane"))', reverse('accounts:detail', args=[self.numeric.username]))
                            wait_for_trail_count(page, 1)
                            nested = page.locator('.ui-workspace-trail-pane [data-review-kind=account]')
                            nested.locator('[data-review-edit=love]').first.click(); wait_for_trail_count(page, 2)
                            expect(form.locator('textarea')).to_have_value('ACCOUNT SAVED')
                            form.locator('textarea').fill('ACCOUNT DRAFT ' + name)
                            form.locator('[data-review-cancel]').click(); wait_for_trail_count(page, 1)
                            page.once('dialog', lambda dialog: dialog.dismiss())
                            nested.locator('[data-mute-form]').evaluate("el => el.dispatchEvent(new Event('submit', {bubbles:true, cancelable:true}))")
                            expect(nested.locator('[data-mute-form] button')).to_have_attribute('aria-pressed', 'false')
                            nested.locator('[data-review-edit=love]').first.click()
                            expect(form.locator('textarea')).to_have_value('ACCOUNT DRAFT ' + name)
                            form.locator('[data-review-cancel]').click()
                            page.locator('.ui-workspace-trail-header .icon-button').last.click(); wait_for_trail_count(page, 0)
                            section.locator('[data-review-edit=hate]').first.click()
                            expect(form.locator('textarea')).to_have_value('ROOM DRAFT ' + name)
                            expect(section.locator('[data-review-edit=love]').first).to_have_attribute('aria-pressed', 'true')
                            # Canceled Mute sends nothing and retains the active Room draft.
                            page.evaluate('''() => {window.qaWrites=0;window.qaFetch=fetch;window.fetch=(...args)=>{
                                if(String(args[0]).endsWith('/mute/'))window.qaWrites++;return window.qaFetch(...args);};}''')
                            page.once('dialog', lambda dialog: dialog.dismiss())
                            section.locator('[data-mute-form]').evaluate("el => el.dispatchEvent(new Event('submit', {bubbles:true, cancelable:true}))")
                            self.assertEqual(page.evaluate('window.qaWrites'), 0)
                            expect(form.locator('textarea')).to_have_value('ROOM DRAFT ' + name)
                            # Hold a failed transport so pending input lock and restoration are observable.
                            page.evaluate('''() => {window.fetch=(...args)=>String(args[0]).endsWith('/mute/')
                                ? new Promise((resolve,reject)=>{window.qaReject=()=>reject(new Error('RoomMute通信失敗'));})
                                : window.qaFetch(...args);}''')
                            page.once('dialog', lambda dialog: dialog.accept())
                            section.locator('[data-mute-form]').evaluate("el => el.dispatchEvent(new Event('submit', {bubbles:true, cancelable:true}))")
                            expect(form.locator('textarea')).to_be_disabled()
                            expect(section.locator('[data-review-edit=love]').first).to_be_disabled()
                            page.evaluate('() => window.qaReject()')
                            expect(section.locator('.review-error')).to_contain_text('RoomMute通信失敗')
                            expect(form.locator('textarea')).to_be_enabled()
                            expect(form.locator('textarea')).to_have_value('ROOM DRAFT ' + name)
                            expect(section.locator('[data-mute-form] button')).to_have_attribute('aria-pressed', 'false')
                            page.evaluate('() => {window.fetch=window.qaFetch;}')
                            form.locator('[data-review-cancel]').click(); wait_for_trail_count(page, 0)
                            # Successful Mute re-fetches every list; direct Room and Review remain readable.
                            page.once('dialog', lambda dialog: dialog.accept())
                            with page.expect_navigation(): section.locator('[data-mute-form] button').click()
                            expect(section.locator('[data-mute-form] button')).to_have_attribute('aria-pressed', 'true')
                            expect(section.locator('[data-review-edit=love]').first).to_have_attribute('aria-pressed', 'true')
                            expect(section.locator('.thread-post-body')).to_have_text('ROOM SAVED')
                            section.locator('[data-review-tab=muter]').click()
                            expect(section.locator('.muter-summary')).to_have_count(8)
                            section.locator('[data-review-expand]').click(); expect(section.locator('.muter-summary')).to_have_count(10)
                            section.locator('[data-review-go-page="2"]').click(); expect(section.locator('.muter-summary')).to_have_count(3)
                            section.locator('[data-review-collapse]').click(); expect(section.locator('.muter-summary')).to_have_count(8)
                            section.scroll_into_view_if_needed()
                            self.assertFalse(section.evaluate('el=>el.scrollWidth>el.clientWidth+1'))
                            page.screenshot(path=output / f'{name}-muters.png')
                            # Origin Room remains filtered in Account Love, then returns after Unmute.
                            page.goto(self.live_server_url + reverse('accounts:detail', args=[self.viewer.username]))
                            page.locator('.account-overview-pane [data-open-account-rooms]').click()
                            room_list = page.locator('[data-account-room-list-container]')
                            room_list.locator('[data-ui-tab=love]').click()
                            expect(room_list.locator(f'[data-account-room-detail="{self.room.pk}"]')).to_have_count(0)
                            page.goto(self.live_server_url + reverse('rooms:detail', args=[self.room.pk]))
                            with page.expect_navigation(): section.locator('[data-mute-form] button').click()
                            expect(section.locator('[data-mute-form] button')).to_have_attribute('aria-pressed', 'false')
                            context.add_cookies([{'name': settings.SESSION_COOKIE_NAME, 'value': self.owner_client.cookies[settings.SESSION_COOKIE_NAME].value, 'url': self.live_server_url}])
                            page.reload()
                            expect(section.locator('[data-review-edit=love]').first).to_be_enabled()
                            section.locator('[data-review-edit=love]').first.click(); expect(form).to_be_visible()
                            form.locator('[data-review-cancel]').click()
                            self.assertEqual(errors, [])
                        finally: context.close()
            finally: browser.close()

    def test_account_room_tabs_pagination_origin_replacement_close_late_responses_pc_mobile(self):
        from playwright.sync_api import sync_playwright, expect
        from scripts.browser_smoke import wait_for_trail_count
        output = Path(settings.BASE_DIR) / '.artifacts' / 'room-mute'; output.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='msedge', headless=True)
            try:
                for name, size in [('desktop', {'width': 1280, 'height': 900}), ('mobile', {'width': 390, 'height': 844})]:
                    with self.subTest(viewport=name):
                        context = self.context(browser, name, size)
                        try:
                            page, errors = self.observe(context)
                            page.goto(self.live_server_url + reverse('accounts:detail', args=[self.viewer.username]))
                            origin = page.locator('.account-overview-pane'); origin.evaluate('el=>window.qaOrigin=el')
                            origin.locator('[data-open-account-rooms]').click()
                            room_list = page.locator('[data-account-room-list-container]')
                            expect(room_list.locator('[data-ui-tab]')).to_have_text(['Owner', '参加中', 'Love', 'Hate'])
                            room_list.locator('[data-ui-tab=love]').click()
                            love = room_list.locator('[data-ui-tab-panel=love]')
                            expect(love.locator('[data-account-room-detail]')).to_have_count(20)
                            love.locator('[data-room-pagination]').click()
                            expect(room_list.locator('[data-ui-tab=love]')).to_have_attribute('aria-selected', 'true')
                            expect(love.locator('[data-account-room-detail]')).to_have_count(2)
                            love.locator('[data-room-pagination]').click()
                            expect(love.locator('[data-account-room-detail]')).to_have_count(20)
                            room_list.locator('[data-ui-tab=hate]').click()
                            hate = room_list.locator('[data-ui-tab-panel=hate]')
                            expect(hate.locator('[data-account-room-detail]')).to_have_count(1)
                            page.screenshot(path=output / f'{name}-account-room-tabs.png')
                            hate.locator('[data-account-room-detail]').click(); wait_for_trail_count(page, 1)
                            nested = page.locator('.ui-workspace-trail-pane [data-review-kind=room]')
                            nested.locator('[data-review-edit=hate]').first.click(); wait_for_trail_count(page, 2)
                            form = page.locator('[data-review-form]')
                            form.locator('[value=love]').check(); form.locator('textarea').fill('Live Love')
                            form.locator('[type=submit]').click(); expect(form).to_have_count(0)
                            expect(hate.locator('[data-account-room-detail]')).to_have_count(0)
                            expect(room_list.locator('[data-ui-tab=hate]')).to_have_attribute('aria-selected', 'true')
                            nested.locator('[data-review-edit=hate]').first.click()
                            form.locator('textarea').fill('HATE SAVED'); form.locator('[type=submit]').click(); expect(form).to_have_count(0)
                            expect(hate.locator('[data-account-room-detail]')).to_have_count(1)
                            nested.locator('[data-review-edit=hate]').first.click()
                            form.locator('textarea').fill('Discarded branch draft')
                            # Selecting another feature at Account origin replaces the full branch.
                            origin.locator('[data-open-account-boards]').evaluate('el=>el.click()'); wait_for_trail_count(page, 1)
                            expect(page.locator('[data-review-form]')).to_have_count(0)
                            expect(page.locator('[data-room-fragment]')).to_have_count(0)
                            self.assertTrue(origin.evaluate('el=>el===window.qaOrigin'))
                            page.locator('.ui-workspace-trail-header .icon-button').last.click(); wait_for_trail_count(page, 0)
                            expect(page.locator('.account-track')).to_have_attribute('data-ui-workspace-stage', 'overview')
                            # Late Room pane responses must not recreate the dismissed branch.
                            origin.locator('[data-open-account-rooms]').click()
                            room_list.locator('[data-ui-tab=hate]').click()
                            page.evaluate('''id=>{window.qaFetch=fetch;window.qaHeld=false;window.fetch=(...args)=>{
                                const options={...args[1],signal:undefined};
                                return window.qaFetch(args[0],options).then(response=>String(args[0]).includes('/rooms/'+id+'/pane/')
                                    ?new Promise(resolve=>{window.qaHeld=true;window.qaRelease=()=>resolve(response);}) : response);};}''', self.hate_room.pk)
                            hate.locator('[data-account-room-detail]').click(); page.wait_for_function('window.qaHeld===true')
                            origin.locator('[data-open-account-boards]').evaluate('el=>el.click()'); wait_for_trail_count(page, 1)
                            page.evaluate('() => {window.qaRelease();window.fetch=window.qaFetch;}'); page.wait_for_timeout(150)
                            expect(page.locator('[data-room-fragment]')).to_have_count(0)
                            page.locator('.ui-workspace-trail-header .icon-button').last.click(); wait_for_trail_count(page, 0)
                            # Nested Account Room pagination uses a fragment URL and preserves selected tab.
                            page.evaluate('(url)=>NiixyWorkspaceTrail.open(url,document.querySelector(".account-overview-pane"))', reverse('accounts:detail', args=[self.viewer.username]))
                            wait_for_trail_count(page, 1)
                            account = page.locator('.ui-workspace-trail-pane [data-account-fragment]')
                            account.locator('[data-open-account-rooms]').click(); wait_for_trail_count(page, 2)
                            shared_list = page.locator('.ui-workspace-trail-pane .account-room-lists')
                            page.locator('.ui-workspace-trail-pane [data-ui-tab=love]').click()
                            shared_list.locator('[data-ui-tab-panel=love] [data-room-pagination]').click()
                            expect(shared_list.locator('[data-ui-tab-panel=love] [data-account-room-detail]')).to_have_count(2)
                            expect(page.locator('.ui-workspace-trail-pane [data-ui-tab=love]')).to_have_attribute('aria-selected', 'true')
                            shared_list.locator('[data-ui-tab-panel=love] [data-account-room-detail]').first.click(); wait_for_trail_count(page, 3)
                            shared_review = page.locator('.ui-workspace-trail-pane [data-review-kind=room]')
                            shared_review.locator('[data-review-edit=hate]').first.click(); wait_for_trail_count(page, 4)
                            form.locator('textarea').fill('Live shared Hate'); form.locator('[type=submit]').click(); expect(form).to_have_count(0)
                            expect(shared_list.locator('[data-ui-tab-panel=love] [data-account-room-detail]')).to_have_count(1)
                            shared_review.locator('[data-review-edit=love]').first.click()
                            form.locator('textarea').fill('List fixture'); form.locator('[type=submit]').click(); expect(form).to_have_count(0)
                            expect(shared_list.locator('[data-ui-tab-panel=love] [data-account-room-detail]')).to_have_count(2)
                            page.locator('.ui-workspace-trail-header .icon-button').last.click(); wait_for_trail_count(page, 2)
                            page.locator('.ui-workspace-trail-header .icon-button').last.click(); wait_for_trail_count(page, 1)
                            self.assertEqual(errors, [])
                        finally: context.close()
            finally: browser.close()
