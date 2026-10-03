# Niixy Development Instructions

## Django development server

1. Before starting `runserver`, check whether port 8000 already has a listening process with `netstat -ano | Select-String ':8000'`.
2. If exactly one process is already listening on `127.0.0.1:8000`, reuse that server instead of starting another one.
3. When a restart is required, stop only the verified Niixy `runserver` process, confirm that port 8000 has no listener, and then start the replacement server.
4. Start the server with `.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000 --noreload`.
5. After starting the server, verify that exactly one process is listening on `127.0.0.1:8000`.
6. Do not restart the server for template, CSS, or JavaScript-only changes. Update static asset cache versions when needed and reuse the existing server.
7. After Python code changes, explicitly restart the existing server instead of launching an additional server.

Never stop an unverified process merely because it uses port 8000. Check its PID, executable path, and start time first. The absence of an available browser automation surface is unrelated to server availability and is not a reason to start another `runserver` process.
