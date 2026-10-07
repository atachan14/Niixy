"""Focused selector failure/lifecycle QA against an isolated SQLite LiveServer."""
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse

from events.models import Thread, ThreadPlacement, ThreadPost
from rooms.services import create_board
from scripts import module_selector_browser_tests as selector_qa


PATHS = [('workspace-board', 'interface'), ('niimap-board', 'field')]
PHASE = os.environ.get('NIIXY_AUXILIARY_QA_PHASE', 'before')
if PHASE not in ('before', 'after'):
    raise ValueError('Unknown auxiliary QA phase')
OUTPUT = Path(settings.BASE_DIR) / '.artifacts' / 'auxiliary-network-2026-10-07' / PHASE
RECORDS = []


class AuxiliaryPaneBrowserTests(StaticLiveServerTestCase):
    static_handler = selector_qa.ModuleSelectorBrowserTests.static_handler
    selected_input = selector_qa.ModuleSelectorBrowserTests.selected_input
    open_origin = selector_qa.ModuleSelectorBrowserTests.open_origin
    assert_origin_and_current = selector_qa.ModuleSelectorBrowserTests.assert_origin_and_current
    hold_detail = selector_qa.ModuleSelectorBrowserTests.hold_detail
    release_detail = selector_qa.ModuleSelectorBrowserTests.release_detail

    def setUp(self):
        selector_qa.ModuleSelectorBrowserTests.setUp(self)
        self.other_board, _ = create_board(
            submission_id=uuid4(), collection=self.room.collections.get(name='Main'),
            name='Auxiliary second Board', actor=self.owner)
        self.output = OUTPUT
        self.output.mkdir(parents=True, exist_ok=True)

    def context(self, browser, viewport, size):
        context, page, errors = selector_qa.ModuleSelectorBrowserTests.context(self, browser, viewport, size)
        allowed = urlsplit(self.live_server_url)

        def guard(route):
            target = urlsplit(route.request.url)
            if ((target.hostname in ('127.0.0.1', 'localhost') and target.port != allowed.port)
                    or target.hostname == 'niixy-psi.vercel.app'):
                errors.append('forbidden endpoint: ' + target.netloc)
                route.abort()
            else:
                route.continue_()

        context.route('**/*', guard)
        # Use the real map SDK, with map-tile rendering outside this limited QA.
        context.route('https://cdn.geolonia.com/style/**', lambda route: route.fulfill(
            status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'},
            body=json.dumps({'version': 8, 'sources': {}, 'layers': [
                {'id': 'background', 'type': 'background', 'paint': {'background-color': '#f7f6f2'}}]})))
        return context, page, errors

    def record(self, page, record, error=None):
        if error:
            record['result'] = 'failed'
            record['error'] = str(error)
        else:
            record['result'] = 'passed'
        filename = '-'.join(record[key] for key in ('viewport', 'origin', 'kind', 'scenario'))
        page.screenshot(path=self.output / (filename + '.png'), full_page=True)
        record['screenshot'] = filename + '.png'
        RECORDS.append(record)
        (self.output / 'result.json').write_text(json.dumps(RECORDS, ensure_ascii=False, indent=2), encoding='utf-8')
        print('QA_CASE ' + json.dumps(record, ensure_ascii=False), flush=True)

    def detail_path(self, kind):
        return reverse('interfaces:definition-detail', args=[self.interface.pk]) if kind == 'interface' else reverse(
            'interfaces:field-detail', args=[self.field.pk])

    def select_value(self, page, form, kind, value):
        from playwright.sync_api import expect
        form.locator(f'[data-open-thread-{kind}-selector]').click()
        page.locator(selector_qa.LIST + ' .ui-summary-item').first.click()
        page.locator(selector_qa.DETAIL + ' .interface-implementation-editor input').first.fill(value)
        page.locator(selector_qa.DETAIL + ' .interface-detail-actions button').click()
        expect(page.locator(selector_qa.SELECTOR)).to_have_count(0)
        expect(self.selected_input(form, kind)).to_have_value(value)

    def fail_next_detail(self, page, kind, failure):
        # Inject at the fetch boundary after a real successful detail GET.
        # This covers the client error paths without swallowing browser console errors.
        page.evaluate("""({path, failure}) => {
            const original = window.fetch;
            let failNext = true;
            window.qaInjectedDetailFailure = null;
            window.fetch = async (...args) => {
                const selected = failNext && new URL(String(args[0]), location.href).pathname === path;
                if (selected) failNext = false;
                const response = await original(...args);
                if (!selected) return response;
                await response.text();
                window.qaInjectedDetailFailure = {kind: failure, sourceStatus: response.status};
                if (failure === 'reject') throw new TypeError('QA simulated network failure');
                return new Response('', {status: 503});
            };
        }""", {'path': self.detail_path(kind), 'failure': failure})

    def test_failed_detail_retry_preserves_input(self):
        from playwright.sync_api import expect, sync_playwright
        counts = (Thread.objects.count(), ThreadPost.objects.count(), ThreadPlacement.objects.count())
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True)
            try:
                for viewport, size in selector_qa.VIEWPORTS:
                    for origin, kind in PATHS:
                        for failure in ('reject', 'http503'):
                            with self.subTest(viewport=viewport, origin=origin, kind=kind, failure=failure):
                                context, page, errors = self.context(browser, viewport, size)
                                record = dict(viewport=viewport, origin=origin, kind=kind, scenario=failure)
                                try:
                                    form = self.open_origin(page, origin)
                                    title = form.locator('[name="title"]').input_value()
                                    self.select_value(page, form, kind, 'existing selected input')
                                    form.locator(f'[data-open-thread-{kind}-selector]').click()
                                    self.fail_next_detail(page, kind, failure)
                                    page.locator(selector_qa.LIST + ' .ui-summary-item').first.click()
                                    detail = page.locator(selector_qa.DETAIL)
                                    expect(detail.locator('.ui-pane-error')).to_be_visible()
                                    expect(detail.locator('.interface-implementation-editor')).to_have_count(0)
                                    expect(form.locator('[name="title"]')).to_have_value(title)
                                    expect(self.selected_input(form, kind)).to_have_value('existing selected input')
                                    self.assert_origin_and_current(page, form, detail, size)
                                    self.assertEqual(page.evaluate('window.qaInjectedDetailFailure'),
                                                     {'kind': failure, 'sourceStatus': 200})
                                    detail.locator('.ui-pane-header button').click()
                                    page.locator(selector_qa.LIST + ' .ui-summary-item').first.click()
                                    editor = page.locator(selector_qa.DETAIL + ' .interface-implementation-editor input').first
                                    expect(editor).to_have_value('existing selected input')
                                    editor.fill('retried selected input')
                                    self.assert_origin_and_current(page, form, page.locator(selector_qa.DETAIL), size)
                                    page.locator(selector_qa.DETAIL + ' .interface-detail-actions button').click()
                                    expect(self.selected_input(form, kind)).to_have_value('retried selected input')
                                    expect(form.locator('[name="title"]')).to_have_value(title)
                                    expect(page.locator(selector_qa.SELECTOR)).to_have_count(0)
                                    target = '[data-selected-direct-field]' if kind == 'field' else '[data-selected-thread-interface]'
                                    expect(form.locator(target)).to_have_count(1)
                                    self.assertEqual(errors, [])
                                    record.update(errors=errors, title_preserved=True, selected_input_preserved=True,
                                                  retry_succeeded=True, source_http_status=200)
                                    self.record(page, record)
                                except Exception as error:
                                    self.record(page, record, error)
                                    raise
                                finally:
                                    context.close()
            finally:
                browser.close()
        self.assertEqual(counts, (Thread.objects.count(), ThreadPost.objects.count(), ThreadPlacement.objects.count()))

    def test_late_detail_after_origin_close_and_other_board(self):
        from playwright.sync_api import expect, sync_playwright
        counts = (Thread.objects.count(), ThreadPost.objects.count(), ThreadPlacement.objects.count())
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True)
            try:
                for viewport, size in selector_qa.VIEWPORTS:
                    for origin, kind in PATHS:
                        with self.subTest(viewport=viewport, origin=origin, kind=kind):
                            context, page, errors = self.context(browser, viewport, size)
                            record = dict(viewport=viewport, origin=origin, kind=kind, scenario='late-origin-close')
                            try:
                                form = self.open_origin(page, origin)
                                self.select_value(page, form, kind, 'old origin selected input')
                                form.locator(f'[data-open-thread-{kind}-selector]').click()
                                self.hold_detail(page, kind)
                                page.locator(selector_qa.LIST + ' .ui-summary-item').first.click()
                                page.wait_for_function('typeof window.qaReleaseDetail === "function"')
                                expect(page.locator(selector_qa.DETAIL + ' .ui-pane-loading')).to_be_visible()
                                page.evaluate('window.qaOldOriginForm = window.qaOriginForm')
                                if origin == 'workspace-board':
                                    page.locator('.ui-workspace-trail-pane').nth(2).locator(
                                        '.ui-workspace-trail-header button').evaluate('el => el.click()')
                                    boards = page.locator('.ui-workspace-trail-pane').nth(1)
                                else:
                                    page.locator('.niimap-room-thread-list-pane > .ui-pane-header button').evaluate('el => el.click()')
                                    boards = page.locator('.niimap-room-list-pane')
                                self.assertFalse(page.evaluate('window.qaOldOriginForm.isConnected'))
                                expect(page.locator(selector_qa.SELECTOR)).to_have_count(0)
                                boards.locator(f'[data-open-board="{self.other_board.pk}"]').click()
                                board = page.locator('.ui-workspace-trail-pane').nth(2) if origin == 'workspace-board' else page.locator('.niimap-room-thread-list-pane')
                                board.locator('[data-board-create-toggle]').click()
                                new_form = board.locator('[data-board-thread-create]')
                                new_form.locator('[name="title"]').fill('New Board unsaved title')
                                new_form.evaluate('el => {window.qaOriginForm = el;}')
                                self.select_value(page, new_form, kind, 'new origin selected input')
                                other_kind = 'field' if kind == 'interface' else 'interface'
                                new_form.locator(f'[data-open-thread-{other_kind}-selector]').click()
                                page.locator(selector_qa.LIST + ' .ui-summary-item').first.click()
                                detail = page.locator(selector_qa.DETAIL)
                                editor = detail.locator('.interface-implementation-editor input').first
                                editor.fill('new origin pending editor')
                                self.assert_origin_and_current(page, new_form, detail, size)
                                before_html = detail.inner_html()
                                before_url = page.url
                                self.release_detail(page)
                                self.assertEqual(detail.inner_html(), before_html)
                                self.assertEqual(page.url, before_url)
                                expect(page.locator(selector_qa.SELECTOR)).to_have_count(2)
                                expect(editor).to_have_value('new origin pending editor')
                                expect(new_form.locator('[name="title"]')).to_have_value('New Board unsaved title')
                                expect(self.selected_input(new_form, kind)).to_have_value('new origin selected input')
                                self.assert_origin_and_current(page, new_form, detail, size)
                                self.assertEqual(errors, [])
                                record.update(errors=errors, old_origin_detached=True, new_board_id=self.other_board.pk,
                                              stale_pane_resurrection=False, new_title_preserved=True,
                                              new_selected_input_preserved=True, new_editor_preserved=True)
                                self.record(page, record)
                            except Exception as error:
                                self.record(page, record, error)
                                raise
                            finally:
                                context.close()
            finally:
                browser.close()
        self.assertEqual(counts, (Thread.objects.count(), ThreadPost.objects.count(), ThreadPlacement.objects.count()))
