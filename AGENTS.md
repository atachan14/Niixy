# Niixy Development Instructions

## Django development server

1. Before starting or restarting `runserver`, inspect port 8000 with `Get-NetTCPConnection -LocalPort 8000 -State Listen` and inspect each owning process with `Get-CimInstance Win32_Process`. Verify the PID, executable path, command line, and start time when available.
2. If exactly one verified Niixy `runserver` process is already listening on `127.0.0.1:8000`, reuse that server instead of starting another one unless a restart condition below applies.
3. A Python or Django template change requires an explicit restart. With `--noreload`, Django may retain parsed templates in memory, so this also includes changing a static asset cache version in a template.
4. A CSS or JavaScript file-content-only change does not require a server restart. Reuse the server and bypass the browser cache when verifying it. If its cache version is changed in a template, follow the template restart rule instead.
5. Documentation-only and test-only changes do not require a server restart.
6. When a restart is required, stop only the verified Niixy `runserver` process, confirm that port 8000 has no listener, and then start the replacement server. Never launch the replacement before the port is clear.
7. Start the server with `.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000 --noreload` and use `Start-Process -WindowStyle Hidden` when starting it in the background.
8. After starting the server, verify that exactly one process is listening on `127.0.0.1:8000`, request a representative page, and confirm that the response contains the expected updated asset version or markup.

Never stop an unverified process merely because it uses port 8000. Check its PID, executable path, and start time first. The absence of an available browser automation surface is unrelated to server availability and is not a reason to start another `runserver` process.
