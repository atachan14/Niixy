"""Browser-test handler for Django's shared in-memory SQLite connection.

LiveServerTestCase passes one SQLite connection to all request threads. Serialize
application calls so concurrent pane/list requests cannot misuse that connection.
Browser fetches remain asynchronous; delayed callbacks are still tested separately.
Production WSGI and runserver are unaffected.
"""
import threading
from django.contrib.staticfiles.handlers import StaticFilesHandler


class SharedSQLiteStaticFilesHandler(StaticFilesHandler):
    request_lock = threading.RLock()

    def __call__(self, environ, start_response):
        with self.request_lock:
            return super().__call__(environ, start_response)
