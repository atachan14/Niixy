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

QA used **disposable** `.artifacts/feedback-dev.sqlite3` at port 8000. No test writes went to the shared DB. Dummy login `conversation_owner` / `niixy-feedback-local` belongs only to that disposable DB; it is not a normal-environment login.

After parent review, port 8000 was restored to the repository's existing normal `.env` configuration (PostgreSQL) by removing the temporary process DATABASE_URL override. `.env` and application settings were never edited; no connection value was inferred or changed. Current normal preview: `http://127.0.0.1:8000/`. Original process inherited environment is no longer inspectable, but its recorded command is identical to this normal startup and the unmodified repository/default configuration resolved PostgreSQL before QA.

AGENTS restart procedure was followed: verified original launcher PID 37728 and base-Python child 23144 with executable paths/command lines/start times; stopped only that pair; confirmed no runserver/no 8000 listener; started hidden `.venv/Scripts/python.exe manage.py runserver 127.0.0.1:8000 --noreload` with DATABASE_URL pointing to disposable SQLite. Replacement launcher PID 27544, child 32460, single listener 127.0.0.1:8000. Representative Thread GET returned HTTP 200 and `20261009-feedback-controls` asset version. Logs are `.artifacts/feedback-server.log` and `feedback-server-errors.log`.

Restoration followed AGENTS: verified QA launcher 27544 / child 32460 and their paths/start times; stopped only that pair; confirmed both no runserver and no listener; restarted hidden with the same command and no DATABASE_URL override. Restored launcher 12992 / child 20312 (2026-10-09 07:17:12), single 127.0.0.1:8000 listener. Normal-environment validation is read-only GET; no browser smoke or test writes were run against normal DB. Restore logs: `.artifacts/normal-server-restored.log`, `normal-server-restored-errors.log`.

No push/publication. No remaining implementation blockers. Full unrelated QA was not run.


## Follow-up: remove direct post sharing

User requested removal of the direct URL sharing shown under each ThreadPost. Removed only the compact sharing details from `templates/shared/content_feedback.html`; the same template is used by Thread and Response bodies in canonical, Account and Room/detail Pane views. Content-list Picker sharing, list sharing, canonical URLs, and direct Thread/Response viewing remain unchanged.

Validation: focused `scripts.feedback_controls_browser_tests` passed (24 PC/mobile Account/Guest combinations, absence of direct share controls, Picker copies the exact canonical URL for all six kinds). Existing `ConversationFeedbackBrowserTests.test_desktop_mobile_rating_picker_lists_history_and_guest_policy` passed, including canonical Response viewing and Account-origin detail. Target measurement tests now allow 0.01px floating-point rounding, because Workspace transforms can report 43.99997px for a 44px CSS target; no CSS change was made in this follow-up.

`browser_smoke.py --base-url http://127.0.0.1:8001 --output-dir .artifacts/post-share-smoke` passed on separate disposable SQLite QA process, with zero browser errors. Same fixture-only standalone Room Thread skip warning as above. PC/mobile direct-post screenshots in `.artifacts/feedback-controls/desktop-thread.png`, `mobile-thread.png`, and Account/Response evidence in `.artifacts/conversation-feedback/` were refreshed. Final Workspace renders `.artifacts/post-share-smoke/desktop-workspace.png` and `mobile-workspace.png` were visually reviewed.

QA launcher 16976 / child 38324 on 8001 were identity-checked and stopped, and the port/process absence verified. Normal launcher 12992 / child 20312 were identity-checked and restarted after confirming no runserver and no 8000 listener. Normal configuration stayed in unmodified `.env`; 8000 was never pointed to QA DB in this follow-up. Current launcher 37780 / child 19708 (2026-10-09 07:31:43) is the only server pair, with one 127.0.0.1:8000 listener. Read-only `GET http://127.0.0.1:8000/threads/1/pane/` returned HTTP 200, contained feedback controls and no direct `data-copy-list-url`. No shared-DB test writes, settings changes, push, or publication.
