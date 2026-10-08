# fav / bad / 追加 UI checkpoint

## Scope

Starting HEAD: `f4edb04586610147673d38352ba374f7a532a384`.
Shared feedback for Thread, Response, Board, and Module (Interface, Field, Layout) now reads as one row of paired `fav(count)` / `bad(count)` buttons plus 追加. Labels toggle/clear the exclusive personal rating; parenthesized counts open the public evaluator Pane. Both parts have separate hover/focus targets; selected labels retain their colored background and aria-pressed state. Mobile/coarse pointer targets have minimum CSS width 45px and height 44px (1px horizontal allowance for fractional Workspace transforms). Each pair remains together when the row wraps.

No data, authorization, rating semantics, migrations, or Account/Room Love/Hate changes. Root README and docs/memo/inbox.md were not edited or staged. Existing user changes in docs/memo/inbox.md, docs/qa-status-2026-10-06.md, scripts/module_selector_browser_tests.py and untracked docs/feature-status-2026-10-07.md are excluded.
Repository AGENTS.md was read; no .agents/skills directory exists in this checkout.

## Validation

- `manage.py test scripts.feedback_controls_browser_tests scripts.conversation_feedback_tests.ConversationFeedbackTests --verbosity 1`: 10 passed (9 existing backend contracts plus focused browser test).
- Final `manage.py test scripts.feedback_controls_browser_tests scripts.conversation_feedback_tests.ConversationFeedbackBrowserTests.test_desktop_mobile_rating_picker_lists_history_and_guest_policy --verbosity 1`: 2 passed.
- Focused browser test: 24 combinations of six content kinds, desktop/mobile, Account/Guest. Label selection/switch/clear, count-only action without rating POST, zero-count Pane, evaluator list, close/return, 追加 picker, keyboard Tab and focus outline, 44px+ mobile targets, same-row normal counts, large-count layout, 320px wrapping, no feedback horizontal overflow, no page/console errors.
- Existing Account browser test: Account-origin detail, Thread/Response switch, rating and saved lists, canonical Response target and Guest policy.
- `scripts/browser_smoke.py` on verified 127.0.0.1:8000: desktop/mobile passed with no browser errors. Workspace open/close/scroll and Back/Forward/reload passed. One warning per viewport: selected standalone Room Board contained no Thread, so that additional Room Thread check was skipped. Thread layout was verified through Account and direct Thread/Response tests.
- Scoped `git diff --check`: passed.

Initial smoke fixture was outside default map bounds; RoomPlacement and map Thread fixtures were corrected in disposable SQLite. An existing browser assertion also found a rendered 43.99997px target; CSS width was raised to 45px and both browser tests and smoke passed afterward.

## Evidence (untracked)

- `.artifacts/feedback-controls/results.json`: measured target boxes and 24 passing combinations.
- `.artifacts/feedback-controls/desktop-thread.png`, `mobile-thread.png`: normal one-row layout.
- `.artifacts/feedback-controls/desktop-thread-selected.png`, `mobile-thread-selected.png`: selected label beside independent count.
- `.artifacts/feedback-controls/{desktop,mobile}-{response,board,interface,field,layout}-selected.png`: common UI coverage.
- `.artifacts/feedback-controls/{desktop,mobile}-large-count.png`, `narrow-large-count.png`: large counts and narrow wrapping (synthetic text only; no large rating DB seed).
- `.artifacts/browser-smoke/desktop-workspace.png`, `mobile-workspace.png`: visually reviewed final Board Workspace; original Account/Room Love/Hate remains visible on desktop.
- `.artifacts/conversation-feedback/`: existing Account/browser flow evidence.

## Local preview

`http://127.0.0.1:8000/threads/1/` is running against **disposable** `.artifacts/feedback-dev.sqlite3`, not the shared PostgreSQL DB. No test writes went to the shared DB. Dummy login: `conversation_owner` / `niixy-feedback-local` (only this disposable DB).

AGENTS restart procedure was followed: verified original launcher PID 37728 and base-Python child 23144 with executable paths/command lines/start times; stopped only that pair; confirmed no runserver/no 8000 listener; started hidden `.venv/Scripts/python.exe manage.py runserver 127.0.0.1:8000 --noreload` with DATABASE_URL pointing to disposable SQLite. Replacement launcher PID 27544, child 32460, single listener 127.0.0.1:8000. Representative Thread GET returned HTTP 200 and `20261009-feedback-controls` asset version. Logs are `.artifacts/feedback-server.log` and `feedback-server-errors.log`.

No push/publication. No remaining implementation blockers. Full unrelated QA was not run.
