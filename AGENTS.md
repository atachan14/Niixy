# Niixy Development Instructions

## Django development server

1. Before starting or restarting `runserver`, inspect both port 8000 and every Python `Win32_Process` whose command line contains `manage.py runserver`. Filter by a Python executable path as well as the command line so the inspection command itself is not counted. Verify the PID, parent PID, executable path, command line, and start time when available. Treat the virtual-environment launcher and its base-Python child as one server pair.
2. Reuse the server only when exactly one verified Niixy `runserver` parent-child pair exists and exactly one process is listening on `127.0.0.1:8000`. Do not rely on the listener result alone: on Windows, multiple `runserver` pairs can coexist even when `Get-NetTCPConnection` exposes only one owning process.
3. A Python or Django template change requires an explicit restart. With `--noreload`, Django may retain parsed templates in memory, so this also includes changing a static asset cache version in a template.
4. A CSS or JavaScript file-content-only change does not require a server restart. Reuse the server and bypass the browser cache when verifying it. If its cache version is changed in a template, follow the template restart rule instead.
5. Documentation-only and test-only changes do not require a server restart.
6. When a restart is required, stop only every process in the verified Niixy `runserver` parent-child pair. Then confirm both that port 8000 has no listener and that no Niixy `manage.py runserver` process remains before starting the replacement. Never launch the replacement before both checks are clear.
7. Start the server with `.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000 --noreload` and use `Start-Process -WindowStyle Hidden` when starting it in the background.
8. After starting the server, verify that exactly one Niixy `runserver` parent-child pair exists and exactly one process is listening on `127.0.0.1:8000`. Request a representative page and confirm that the response contains the expected updated asset version or markup.

Never stop an unverified process merely because it uses port 8000. Check its PID, executable path, and start time first. The absence of an available browser automation surface is unrelated to server availability and is not a reason to start another `runserver` process.

## Browser verification

1. Install development-only dependencies with `.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt`. The smoke test uses the locally installed Microsoft Edge channel and does not require a separate Playwright browser download.
2. After changing Workspace navigation, client-side interaction, shared Pane behavior, or responsive layout, run `.\.venv\Scripts\python.exe scripts\browser_smoke.py` against the verified development server.
3. Treat a JavaScript page error, console error, failed Workspace assertion, or missing desktop/mobile render as a failed verification. Do not report the UI task complete until the failure is fixed or explicitly documented.
4. Review `.artifacts/browser-smoke/desktop-workspace.png` and `.artifacts/browser-smoke/mobile-workspace.png` when the change can affect Workspace layout. The accompanying `desktop.png` and `mobile.png` capture the final Account Page state. These generated artifacts stay untracked.
5. Use `--headed` only when an interactive browser is useful. Headless mode is the default and must remain sufficient for repeatable smoke checks.
