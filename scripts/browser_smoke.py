from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / ".artifacts" / "browser-smoke"


@dataclass
class SmokeResult:
    viewport: str
    checks: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    browser_errors: list[str] = field(default_factory=list)

    def check(self, message: str) -> None:
        self.checks.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Niixy's browser smoke checks against an existing development server."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--headed", action="store_true", help="Show Microsoft Edge while testing.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--viewport",
        choices=("all", "desktop", "mobile"),
        default="all",
    )
    return parser.parse_args()


def require_server(base_url: str) -> None:
    try:
        with urlopen(base_url, timeout=20) as response:
            if response.status != 200:
                raise RuntimeError(f"Development server returned HTTP {response.status}.")
    except (OSError, TimeoutError, URLError) as error:
        raise RuntimeError(
            f"Development server is unavailable at {base_url}. Start the verified Niixy runserver first."
        ) from error


def wait_for_trail_count(page: Page, expected: int) -> None:
    page.wait_for_function(
        "expected => document.querySelectorAll('.ui-workspace-trail-pane').length === expected",
        arg=expected,
    )
    page.wait_for_timeout(350)
    if expected:
        box = page.locator(".ui-workspace-trail-pane").last.bounding_box()
        if box is None:
            raise AssertionError("Current Workspace Pane is not rendered.")
        viewport_width = page.viewport_size["width"]
        overlap = max(0, min(box["x"] + box["width"], viewport_width) - max(box["x"], 0))
        required = min(box["width"], viewport_width) * 0.8
        if overlap < required:
            raise AssertionError(
                f"Current Workspace Pane is outside the viewport: overlap={overlap}, required={required}."
            )


def close_current_trail(page: Page, expected_after_close: int) -> None:
    page.locator(".ui-workspace-trail-pane").last.locator(
        ".ui-workspace-trail-header .icon-button"
    ).click()
    wait_for_trail_count(page, expected_after_close)


def exercise_room_trail(page: Page, result: SmokeResult, screenshot_path: Path) -> None:
    room_link = page.locator("a.room-summary[href^='/rooms/']").first
    if room_link.count() == 0:
        result.warn("No visible Room was available; the Room Workspace flow was skipped.")
        return

    list_pane = page.locator(".thread-list-pane")
    # Click scrolls its target into view before the app snapshots the root.
    # Record that actionable position, including lists populated after DOM load.
    room_link.scroll_into_view_if_needed()
    original_scroll = list_pane.evaluate("el => el.scrollTop")
    room_link.click()
    page.wait_for_selector(".ui-workspace-trail-pane [data-room-fragment]")
    wait_for_trail_count(page, 1)

    full_pane_width = page.locator(".ui-workspace-trail-pane").last.evaluate(
        "el => el.getBoundingClientRect().width"
    )
    viewport_width = page.viewport_size["width"]
    if full_pane_width < viewport_width - 2:
        raise AssertionError(
            f"Room Pane is not full width: pane={full_pane_width}, viewport={viewport_width}."
        )
    result.check("NiiMap -> Room opened a full-width Workspace Pane.")

    captured_workspace = False
    boards_button = page.locator(".ui-workspace-trail-pane [data-open-room-boards]").last
    if boards_button.count() == 0 or boards_button.is_disabled():
        result.warn("The selected Room did not expose a usable Board list button.")
    else:
        boards_button.click()
        page.wait_for_selector(".ui-workspace-trail-pane .room-collection-browser")
        wait_for_trail_count(page, 2)
        result.check("Room -> Board list appended a second Pane.")

        board = page.locator(".ui-workspace-trail-pane [data-open-board]").last
        if board.count():
            board.click()
            page.wait_for_selector(".ui-workspace-trail-pane [data-board-name]")
            wait_for_trail_count(page, 3)
            result.check("Board list -> Board detail appended a third Pane.")
            page.screenshot(path=screenshot_path)
            captured_workspace = True
            close_current_trail(page, 2)
            result.check("Closing Board detail restored the Board list Pane.")
        else:
            result.warn("The selected Room had no visible Board to open.")

        if not captured_workspace:
            page.screenshot(path=screenshot_path)
            captured_workspace = True
        close_current_trail(page, 1)
    if not captured_workspace:
        page.screenshot(path=screenshot_path)

    close_current_trail(page, 0)
    page.wait_for_function(
        "() => !document.querySelector('.thread-workspace')?.classList.contains('is-workspace-trail-open')"
    )
    restored_scroll = list_pane.evaluate("el => el.scrollTop")
    if abs(restored_scroll - original_scroll) > 1:
        raise AssertionError(
            f"Spot list scroll was not preserved: before={original_scroll}, after={restored_scroll}."
        )
    result.check("Closing the Room Pane restored the original NiiMap DOM and scroll position.")


def exercise_account_to_room(page: Page, base_url: str, result: SmokeResult) -> None:
    account_source = page.locator(".room-item[data-owner-id]:not([data-owner-id=''])").first
    attribute = "data-owner-id"
    if account_source.count() == 0:
        account_source = page.locator(".thread-item[data-creator-id]:not([data-creator-id=''])").first
        attribute = "data-creator-id"
    if account_source.count() == 0:
        result.warn("No Account source was available; Account -> Room was skipped.")
        return

    username = account_source.get_attribute(attribute)
    page.goto(f"{base_url}/accounts/{username}/", wait_until="domcontentloaded")
    page.wait_for_selector(".account-page")
    rooms_button = page.locator("[data-open-account-rooms]")
    if rooms_button.count() == 0:
        result.warn(f"@{username} did not expose the Room list button.")
        return

    rooms_button.click()
    room_list_pane = page.locator(".account-room-list-pane")
    room_link = room_list_pane.locator("a[href^='/rooms/']").first
    room_link.wait_for()
    if room_link.count() == 0:
        result.warn(f"@{username} had no Room available for the nested Workspace check.")
        return

    room_link.click()
    page.wait_for_selector(".ui-workspace-trail-pane [data-room-fragment]")
    wait_for_trail_count(page, 1)
    result.check("Account -> Room used a Workspace transition.")
    close_current_trail(page, 0)
    result.check("Closing the nested Room restored the Account Room list.")


def assert_thread_layout(page: Page, detail, result: SmokeResult) -> None:
    detail.wait_for(state="visible")
    metrics = detail.evaluate("""el => {
        const row = el.querySelector('.ui-placement-row');
        return {rowHeight: row?.getBoundingClientRect().height || 0,
                overflow: el.scrollWidth - el.clientWidth,
                width: el.getBoundingClientRect().width,
                posts: el.querySelectorAll('.thread-post').length};
    }""")
    if metrics["rowHeight"] > 40 or metrics["overflow"] > 2 or metrics["width"] <= 0:
        raise AssertionError(f"Thread detail layout is broken: {metrics}")
    result.check("Thread detail has a compact placement row and no horizontal clipping.")


def exercise_account_features(page: Page, base_url: str, result: SmokeResult, output_dir: Path) -> None:
    source = page.locator(".thread-item[data-creator-id]:not([data-creator-id=''])").first
    attribute = "data-creator-id"
    if not source.count():
        source = page.locator(".room-item[data-owner-id]:not([data-owner-id=''])").first
        attribute = "data-owner-id"
    if not source.count():
        result.warn("No Account source was available; feature replacement was skipped.")
        return
    username = source.get_attribute(attribute)
    page.goto(f"{base_url}/accounts/{username}/", wait_until="domcontentloaded")
    root_threads = page.locator(".account-overview-pane [data-open-account-threads]")
    root_responses = page.locator(".account-overview-pane [data-open-account-responses]")
    root_threads.click()
    page.wait_for_selector("[data-thread-pane-container] .account-thread-column")
    thread = page.locator("[data-thread-pane-container] [data-thread-detail]").first
    if thread.count():
        thread.click()
        detail = page.locator(".account-thread-detail-pane .thread-detail:not([hidden])")
        assert_thread_layout(page, detail, result)
        page.wait_for_timeout(350)
        page.screenshot(path=output_dir / f"{result.viewport}-account-thread.png")
        page.evaluate("(username) => NiixyWorkspaceTrail.open('/accounts/' + username + '/')", username)
        page.wait_for_selector(".ui-workspace-trail-pane [data-account-fragment]")
        wait_for_trail_count(page, 1)
        account = page.locator(".ui-workspace-trail-pane [data-account-fragment]").first
        account.locator("[data-open-account-threads]").evaluate("el => el.click()")
        page.wait_for_selector(".ui-workspace-trail-pane .account-thread-column")
        wait_for_trail_count(page, 2)
        nested_thread = page.locator(".ui-workspace-trail-pane [data-thread-detail]").first
        nested_thread.click()
        page.wait_for_selector(".ui-workspace-trail-pane .thread-detail")
        wait_for_trail_count(page, 3)
        assert_thread_layout(page, page.locator(".ui-workspace-trail-pane .thread-detail").last, result)
        page.screenshot(path=output_dir / f"{result.viewport}-nested-thread.png")
        page.locator(".ui-workspace-trail-pane").nth(1).evaluate("el => el.dataset.smokeDiscard = 'true'")
        page.locator(".ui-workspace-trail-pane").nth(2).evaluate("el => el.dataset.smokeDiscard = 'true'")
        account.locator("[data-open-account-responses]").evaluate("el => el.click()")
        wait_for_trail_count(page, 2)
        if page.locator("[data-smoke-discard]").count():
            raise AssertionError("Account feature replacement retained an old descendant Pane.")
        for kind in ("threads", "responses", "threads", "responses"):
            account.locator(f"[data-open-account-{kind}]").evaluate("el => el.click()")
            wait_for_trail_count(page, 2)
        result.check("Nested Account Thread/Response switches replaced all descendants without accumulating Panes.")
        close_current_trail(page, 1)
        close_current_trail(page, 0)
        assert_thread_layout(page, detail, result)
    else:
        result.warn(f"@{username} has no visible Thread; Thread detail layout checks were skipped.")

    root_threads.evaluate("el => el.click()")
    page.wait_for_function("() => new URLSearchParams(location.search).get('pane') === 'thread'")
    root_responses.evaluate("el => el.click()")
    page.wait_for_function("() => new URLSearchParams(location.search).get('pane') === 'response'")
    page.go_back()
    page.wait_for_function("() => new URLSearchParams(location.search).get('pane') === 'thread' && document.querySelector('.account-track').dataset.uiWorkspaceStage === 'list'")
    page.go_forward()
    page.wait_for_function("() => new URLSearchParams(location.search).get('pane') === 'response' && document.querySelector('.account-track').dataset.uiWorkspaceStage === 'list'")
    page.reload(wait_until="domcontentloaded")
    page.wait_for_selector("[data-thread-pane-container] .response-history-item, [data-thread-pane-container] .empty")
    result.check("Account feature Back/Forward and reload restored the selected list.")

    page.evaluate("(username) => NiixyWorkspaceTrail.open('/accounts/' + username + '/')", username)
    page.wait_for_selector(".ui-workspace-trail-pane [data-account-fragment]")
    page.locator(".ui-workspace-trail-pane [data-open-account-threads]").evaluate("el => el.click()")
    wait_for_trail_count(page, 2)
    page.locator(".account-overview-pane [data-open-account-responses]").evaluate("el => el.click()")
    wait_for_trail_count(page, 0)
    page.wait_for_function("() => document.querySelector('.account-track').dataset.uiWorkspaceStage === 'list'")
    result.check("Root Account feature selection discarded the entire nested Workspace branch.")


def exercise_room_details(page: Page, base_url: str, result: SmokeResult, output_dir: Path) -> None:
    room = page.locator("a.room-summary[href^='/rooms/']").first
    if not room.count():
        result.warn("No Room was available for the standalone Room Thread check.")
        return
    room_url = room.get_attribute("href")
    page.goto(f"{base_url}{room_url}", wait_until="domcontentloaded")
    page.locator("[data-open-room-boards]").click()
    page.wait_for_selector("#room-list-content [data-open-board]")
    page.locator("#room-list-content [data-open-board]").last.click()
    page.wait_for_selector("#room-thread-list-content [data-board-name]")
    thread = page.locator("#room-thread-list-content [data-room-thread]").first
    if not thread.count():
        result.warn("The selected Board had no visible Thread for the standalone Room check.")
        return
    thread.click()
    detail = page.locator("#room-thread-detail-content .thread-detail")
    assert_thread_layout(page, detail, result)
    page.wait_for_timeout(350)
    page.screenshot(path=output_dir / f"{result.viewport}-room-thread.png")
    page.reload(wait_until="domcontentloaded")
    assert_thread_layout(page, page.locator("#room-thread-detail-content .thread-detail"), result)
    page.locator("#close-room-thread-detail").click()
    page.wait_for_function("() => document.querySelector('.room-track').dataset.uiWorkspaceStage === 'thread-list'")
    result.check("Standalone Room Thread detail rendered, restored on reload, and closed to its Board.")


def run_viewport(browser, base_url: str, output_dir: Path, name: str, size: dict[str, int]) -> SmokeResult:
    result = SmokeResult(name)
    output_dir.mkdir(parents=True, exist_ok=True)
    context = browser.new_context(viewport=size, device_scale_factor=1)
    page = context.new_page()
    page.set_default_timeout(10_000)
    def capture_console_error(message) -> None:
        if message.type != "error":
            return
        location = message.location.get("url", "")
        if location.endswith("/favicon.ico"):
            return
        result.browser_errors.append(
            f"console.{message.type}: {message.text}" + (f" ({location})" if location else "")
        )

    page.on("console", capture_console_error)
    page.on("pageerror", lambda error: result.browser_errors.append(f"pageerror: {error}"))

    try:
        page.goto(f"{base_url}/", wait_until="domcontentloaded")
        page.wait_for_selector(".thread-workspace")
        result.check("NiiMap rendered.")
        exercise_room_trail(page, result, output_dir / f"{name}-workspace.png")
        page.goto(f"{base_url}/", wait_until="domcontentloaded")
        exercise_account_to_room(page, base_url, result)
        page.goto(f"{base_url}/", wait_until="domcontentloaded")
        exercise_account_features(page, base_url, result, output_dir)
        page.goto(f"{base_url}/", wait_until="domcontentloaded")
        exercise_room_details(page, base_url, result, output_dir)
    except PlaywrightTimeoutError as error:
        raise AssertionError(f"Timed out while testing the {name} viewport: {error}") from error
    finally:
        page.wait_for_timeout(350)
        page.screenshot(path=output_dir / f"{name}.png", full_page=True)
        context.close()

    if result.browser_errors:
        raise AssertionError("Browser errors:\n" + "\n".join(result.browser_errors))
    return result


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    require_server(base_url)
    viewports = {
        "desktop": {"width": 1280, "height": 720},
        "mobile": {"width": 390, "height": 844},
    }
    selected = viewports if args.viewport == "all" else {args.viewport: viewports[args.viewport]}
    results: list[SmokeResult] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            channel="msedge",
            headless=not args.headed,
            args=["--no-first-run", "--disable-sync"],
        )
        try:
            for name, size in selected.items():
                results.append(run_viewport(browser, base_url, args.output_dir, name, size))
        finally:
            browser.close()

    print(json.dumps([result.__dict__ for result in results], ensure_ascii=False, indent=2))
    print(f"Screenshots: {args.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, RuntimeError) as error:
        print(f"Browser smoke failed: {error}", file=sys.stderr)
        raise SystemExit(1)
