"""Cloud Run worker entrypoint.

Runs the arq worker alongside a minimal HTTP health server on $PORT
so Cloud Run's startup probe succeeds.
"""

import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        pass  # suppress request logs


def _run_health_server():
    port = int(os.environ.get("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    server.serve_forever()


def main():
    # Start health server in background thread
    t = threading.Thread(target=_run_health_server, daemon=True)
    t.start()

    # Run arq worker (blocks until stopped)
    subprocess.run(
        ["arq", "chronocanvas.worker.WorkerSettings"],
        check=True,
    )


if __name__ == "__main__":
    main()
