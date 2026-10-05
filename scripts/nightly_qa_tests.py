"""Cross-feature QA: isolated SQLite, ephemeral LiveServer and local Edge only.

Run: .venv\\Scripts\\python.exe manage.py test scripts.nightly_qa_tests --noinput
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connections
from django.test import TestCase
from django.urls import reverse

from accounts.content_lists import route
from accounts.models import AccountList, AccountListReference, AccountMute, AccountReview
from interfaces.models import Interface, InterfaceDraft, InterfaceList, InterfaceListReference, InterfaceRating
from interfaces.services import publish_draft
from rooms.models import Board, BoardListReference, BoardPlacement, BoardRating
from scripts.browser_test_server import SharedSQLiteStaticFilesHandler


def seed(case):
    case.assertEqual(settings.DATABASES['default']['ENGINE'], 'django.db.backends.sqlite3')
    case.owner = get_user_model().objects.create_user('nightly_owner')
    case.target = get_user_model().objects.create_user('nightly_target')
    case.review = AccountReview.objects.create(
        author=case.owner, target=case.target, sentiment='love', body='Saved cross-feature Review')
    case.account_list = AccountList.objects.create(owner=case.owner, name='QA People', submission_id=uuid4())
    AccountListReference.objects.create(account_list=case.account_list, target=case.target)
    case.board = Board.objects.get(placement__collection__account=case.target)
    case.board_list = case.owner.collections.get(name='Main')
    BoardListReference.objects.create(board_list=case.board_list, target=case.board)
    draft = InterfaceDraft.objects.create(creator=case.target, kind='account', name='QA Public IF')
    case.interface, _ = publish_draft(draft.pk)
    InterfaceDraft.objects.create(creator=case.target, interface=case.interface,
        kind='account', name='PRIVATE QA DRAFT', description='PRIVATE QA DESCRIPTION')
    case.interface_list = InterfaceList.objects.create(owner=case.owner, name='QA IFs', submission_id=uuid4())
    InterfaceListReference.objects.create(interface_list=case.interface_list, target=case.interface)
    case.client.force_login(case.owner)


class NightlyIntegrationTests(TestCase):
    def setUp(self):
        seed(self)

    def test_account_list_deletion_preserves_cross_feature_records(self):
        AccountMute.objects.create(muter=self.owner, muted_account=self.target)
        BoardRating.objects.create(author=self.owner, target=self.board, sentiment='fav')
        InterfaceRating.objects.create(author=self.owner, target=self.interface, sentiment='bad')
        other = AccountList.objects.create(owner=self.target, name='Keep another List', submission_id=uuid4())
        AccountListReference.objects.create(account_list=other, target=self.target)
        models = [get_user_model(), AccountReview, AccountMute, BoardPlacement,
                  BoardListReference, InterfaceListReference, BoardRating, InterfaceRating]
        before = {model: list(model.objects.order_by('pk').values()) for model in models}
        response = self.client.post(reverse('accounts:list-delete', args=[self.account_list.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(AccountList.objects.filter(pk=self.account_list.pk).exists())
        self.assertTrue(other.references.filter(target=self.target).exists())
        for model, expected in before.items():
            self.assertEqual(list(model.objects.order_by('pk').values()), expected, model.__name__)

    def test_mute_filter_does_not_grant_board_rights_or_remove_references(self):
        self.board.description = 'PRIVATE QA BOARD BODY'
        self.board.save(update_fields=['description'])
        self.board.policy_conditions.all().delete()
        placement = list(BoardPlacement.objects.order_by('pk').values())
        self.assertContains(self.client.get(route('board', 'pane', self.board.pk)), 'data-board-view-unavailable')
        self.assertNotContains(self.client.get(route('board', 'pane', self.board.pk)), self.board.description)
        self.assertEqual(self.client.post(route('board', 'rating', self.board.pk), {'sentiment': 'fav'}).status_code, 403)
        self.assertEqual(self.client.post(reverse('accounts:board-edit', args=[self.target.username, self.board.pk]),
            {'name': 'unauthorized rename'}).status_code, 403)
        AccountMute.objects.create(muter=self.owner, muted_account=self.target)
        pages = [reverse('accounts:list-detail', args=[self.account_list.pk]),
                 route('board', 'list-detail', self.board_list.pk),
                 route('interface', 'list-detail', self.interface_list.pk)]
        for url in pages:
            self.assertNotContains(self.client.get(url), 'data-account-reference=')
            self.assertNotContains(self.client.get(url), 'data-content-reference=')
        self.assertEqual(self.account_list.references.count(), 1)
        self.assertEqual(self.board_list.references.count(), 1)
        self.assertEqual(self.interface_list.references.count(), 1)
        self.assertContains(self.client.get(reverse('accounts:detail', args=[self.target.username])), self.review.body)
        self.assertContains(self.client.get(route('interface', 'page', self.interface.pk)), 'QA Public IF')
        self.assertEqual(list(BoardPlacement.objects.order_by('pk').values()), placement)
        self.client.logout()
        for url in pages:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, 'data-account-list-form')
            self.assertNotContains(response, 'PRIVATE QA DRAFT')
        self.assertContains(self.client.get(pages[0]), '@nightly_target')
        self.assertContains(self.client.get(pages[1]), '閲覧不可')
        self.assertContains(self.client.get(pages[2]), 'QA Public IF')


class NightlyBrowserTests(StaticLiveServerTestCase):
    static_handler = SharedSQLiteStaticFilesHandler

    def setUp(self):
        seed(self)

    def db_call(self, operation):
        def run():
            try:
                with SharedSQLiteStaticFilesHandler.request_lock:
                    return operation()
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=1) as worker:
            return worker.submit(run).result()

    def context(self, browser, name):
        size = {'width': 1280, 'height': 900} if name == 'desktop' else {'width': 390, 'height': 844}
        context = browser.new_context(viewport=size, is_mobile=name == 'mobile', has_touch=name == 'mobile')
        context.add_cookies([{'name': settings.SESSION_COOKIE_NAME,
            'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url': self.live_server_url}])
        page = context.new_page()
        page.set_default_timeout(10000)
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('console', lambda message: errors.append(message.text) if message.type == 'error'
            and not message.location.get('url', '').endswith('/favicon.ico') else None)
        return context, page, errors

    def test_list_history_reload_and_guest_privacy_pc_mobile(self):
        from playwright.sync_api import expect, sync_playwright
        from scripts.browser_smoke import wait_for_trail_count
        output = Path(settings.BASE_DIR) / '.artifacts' / 'nightly-qa'
        output.mkdir(parents=True, exist_ok=True)
        cases = [('account', reverse('accounts:list-page', args=[self.account_list.pk]), '.account-summary'),
                 ('board', route('board', 'list-page', self.board_list.pk), '[data-content-reference] .content-reference-summary'),
                 ('interface', route('interface', 'list-page', self.interface_list.pk), '.content-reference-summary')]
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='msedge', headless=True)
            try:
                for name in ['desktop', 'mobile']:
                    for kind, path, target in cases:
                        with self.subTest(viewport=name, kind=kind):
                            context, page, errors = self.context(browser, name)
                            try:
                                url = self.live_server_url + path
                                owner_url = self.live_server_url + '/accounts/nightly_owner/'
                                page.goto(url)
                                wait_for_trail_count(page, 1)
                                detail = page.locator('[data-account-list-detail]')
                                expect(detail).to_have_attribute('data-list-id', str(
                                    self.account_list.pk if kind == 'account' else self.board_list.pk if kind == 'board' else self.interface_list.pk))
                                if kind != 'account':
                                    expect(detail).to_have_attribute('data-content-list-kind', kind)
                                detail.evaluate('el => {window.qaListDOM = el;}')
                                detail.locator(target).click()
                                wait_for_trail_count(page, 2)
                                page.locator('.ui-workspace-trail-header .icon-button').last.click()
                                wait_for_trail_count(page, 1)
                                self.assertTrue(detail.evaluate('el => el === window.qaListDOM'))
                                expect(page).to_have_url(url)
                                page.goto(owner_url)
                                page.go_back()
                                expect(page).to_have_url(url)
                                wait_for_trail_count(page, 1)
                                expect(detail).to_have_attribute('data-list-page-url', path)
                                page.go_forward()
                                expect(page).to_have_url(owner_url)
                                page.go_back()
                                page.reload()
                                wait_for_trail_count(page, 1)
                                expect(detail.locator(target)).to_have_count(1)
                                context.clear_cookies()
                                page.reload()
                                wait_for_trail_count(page, 1)
                                expect(detail.locator('[data-account-list-form]')).to_have_count(0)
                                expect(page.locator('body')).not_to_contain_text('PRIVATE QA DRAFT')
                                page.screenshot(path=output / f'{name}-{kind}-history-guest.png')
                                if kind == 'interface':
                                    self.db_call(lambda: Interface.objects.filter(pk=self.interface.pk).update(status=Interface.DELETED))
                                    page.reload()
                                    wait_for_trail_count(page, 1)
                                    expect(detail.locator('.content-reference-summary')).to_have_count(0)
                                    expect(page.locator('body')).not_to_contain_text('PRIVATE QA DESCRIPTION')
                                    response = page.request.get(self.live_server_url + route('interface', 'page', self.interface.pk))
                                    self.assertEqual(response.status, 404)
                                self.assertEqual(errors, [])
                            finally:
                                context.close()
                                self.db_call(lambda: Interface.objects.filter(pk=self.interface.pk).update(status=Interface.ACTIVE))
            finally:
                browser.close()

    def test_late_forms_mute_failure_and_detached_review_save_pc_mobile(self):
        from playwright.sync_api import expect, sync_playwright
        from scripts.browser_smoke import wait_for_trail_count
        output = Path(settings.BASE_DIR) / '.artifacts' / 'nightly-qa'
        output.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='msedge', headless=True)
            try:
                for name in ['desktop', 'mobile']:
                    with self.subTest(viewport=name):
                        context, page, errors = self.context(browser, name)
                        try:
                            page.goto(self.live_server_url + '/accounts/nightly_target/')
                            root = page.locator('.account-overview-pane [data-review-section]')
                            form = page.locator('[data-review-form]')
                            body = 'Retained Review ' + name
                            list_name = 'Retained List ' + name
                            root.locator('[data-review-edit=love]').first.click()
                            expect(form).to_be_visible()
                            form.locator('textarea').fill(body)
                            form.locator('[data-review-cancel]').click()
                            wait_for_trail_count(page, 0)
                            root.locator('[data-account-list-picker-url]').click()
                            create = page.locator('[data-list-operation=create]')
                            expect(create).to_be_visible()
                            create.locator('[name=name]').fill(list_name)
                            page.locator('.ui-workspace-trail-header .icon-button').last.click()
                            wait_for_trail_count(page, 0)
                            # Hold actual GET responses; the Mute failure is synthetic and writes no DB data.
                            page.evaluate("""() => {
                              window.qaFetch = fetch; window.qaMuteWrites = 0;
                              window.fetch = (...a) => {
                                const url = String(a[0]);
                                if (url.endsWith('/mute/')) {window.qaMuteWrites++; return new Promise(resolve => {
                                  window.qaReleaseMute = () => resolve(new Response(JSON.stringify({error:'Held Mute failure'}),
                                    {status:503,headers:{'Content-Type':'application/json'}}));});}
                                if (url.includes('/lists/picker/') || url.includes('/reviews/editor/')) {
                                  a[1] = {...a[1],signal:undefined};
                                  return window.qaFetch(...a).then(response => new Promise(resolve => {
                                    window.qaReleaseGet = () => resolve(response);
                                  }));
                                }
                                return window.qaFetch(...a);
                              };
                            }""")
                            page.once('dialog', lambda dialog: dialog.dismiss())
                            root.locator('[data-mute-form]').evaluate("f => f.requestSubmit()")
                            self.assertEqual(page.evaluate('window.qaMuteWrites'), 0)
                            # A late List form remains locked during Mute, then regains its closed draft.
                            root.locator('[data-account-list-picker-url]').click()
                            page.wait_for_function('typeof window.qaReleaseGet === "function"')
                            page.once('dialog', lambda dialog: dialog.accept())
                            root.locator('[data-mute-form]').evaluate('f => f.requestSubmit()')
                            page.wait_for_function('window.qaMuteWrites === 1')
                            page.evaluate('window.qaReleaseGet()')
                            expect(create).to_be_visible()
                            expect(create.locator('[name=name]')).to_be_disabled()
                            expect(create.locator('[name=name]')).to_have_value(list_name)
                            page.evaluate('window.qaReleaseMute()')
                            expect(create.locator('[name=name]')).to_be_enabled()
                            expect(create.locator('[name=name]')).to_have_value(list_name)
                            page.locator('.ui-workspace-trail-header .icon-button').last.click()
                            wait_for_trail_count(page, 0)
                            # A late Review GET waits for Mute to settle before enabling its input.
                            page.evaluate('delete window.qaReleaseGet')
                            root.locator('[data-review-edit=love]').first.click()
                            page.wait_for_function('typeof window.qaReleaseGet === "function"')
                            page.once('dialog', lambda dialog: dialog.accept())
                            root.locator('[data-mute-form]').evaluate('f => f.requestSubmit()')
                            page.wait_for_function('window.qaMuteWrites === 2')
                            page.evaluate('window.qaReleaseGet()')
                            expect(form).to_have_count(0)
                            page.evaluate('window.qaReleaseMute()')
                            expect(form.locator('textarea')).to_be_enabled()
                            expect(form.locator('textarea')).to_have_value(body)
                            page.screenshot(path=output / f'{name}-late-drafts-retained.png')
                            # Delay a committed Review response. Mute cannot start during that write,
                            # and its completion cannot close a newer Interface Pane.
                            page.evaluate("""() => {window.fetch = (...a) => {
                              const url = String(a[0]);
                              if (url.endsWith('/reviews/save/')) return window.qaFetch(...a).then(response =>
                                new Promise(resolve => {window.qaReleaseSave = () => resolve(response);}));
                              if (url.endsWith('/mute/')) window.qaMuteWrites++;
                              return window.qaFetch(...a);
                            };}""")
                            form.locator('[type=submit]').click()
                            page.wait_for_function('typeof window.qaReleaseSave === "function"')
                            expect(form.locator('textarea')).to_be_disabled()
                            root.locator('[data-mute-form]').evaluate('f => f.requestSubmit()')
                            self.assertEqual(page.evaluate('window.qaMuteWrites'), 2)
                            page.locator('.ui-workspace-trail-header .icon-button').last.click()
                            wait_for_trail_count(page, 0)
                            page.evaluate('(url) => NiixyContentReferences.open(url, document.querySelector(".account-overview-pane"))',
                                self.live_server_url + route('interface', 'page', self.interface.pk))
                            expect(page.locator('[data-interface-name]')).to_be_visible()
                            page.evaluate('window.qaReleaseSave()')
                            expect(root.locator('.review-post .thread-post-body')).to_have_text(body)
                            wait_for_trail_count(page, 1)
                            expect(page.locator('[data-interface-name]')).to_be_visible()
                            page.locator('.ui-workspace-trail-header .icon-button').last.click()
                            root.locator('[data-review-edit=love]').first.click()
                            expect(form.locator('textarea')).to_have_value(body)
                            self.assertEqual(errors, [])
                        finally:
                            context.close()
            finally:
                browser.close()
