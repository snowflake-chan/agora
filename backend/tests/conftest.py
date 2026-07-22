"""Start the FastAPI server in the background for integration tests."""

import multiprocessing
import json
import os
import socket
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import uvicorn
from uvicorn.config import Config

os.environ["SUPER_ADMIN_EMAIL"] = "admin-test@example.com"
os.environ["AUTH_REGISTER_ATTEMPTS"] = "10000"
os.environ["APP_ENV"] = "test"
os.environ["GOVERNANCE_POLL_SECONDS"] = "1"
# Integration tests do not call a paid provider. Semantic fallback behavior is
# covered with deterministic provider/Redis doubles in focused unit tests.
os.environ["AI_FEATURES_ENABLED"] = "false"
os.environ["AI_MODERATION_PROVIDER_FALLBACK_ENABLED"] = "false"
os.environ["AI_POLITICAL_CLASSIFIER_URL"] = "http://127.0.0.1:18081/classify"
os.environ["AI_MODERATION_RATE_LIMIT_GLOBAL_QPS"] = "10000"
os.environ["AI_MODERATION_RATE_LIMIT_DAILY_GLOBAL_REQUESTS"] = "1000000"


class _SemanticClassifierHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("content-length", "0"))
        payload = json.loads(self.rfile.read(length))
        statuses = [
            "political" if "[test:political]" in text else "non_political"
            for text in payload["texts"]
        ]
        body = json.dumps({"statuses": statuses}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format, *_args):
        return


def run_semantic_classifier():
    server = ThreadingHTTPServer(("127.0.0.1", 18081), _SemanticClassifierHandler)
    server.serve_forever()


def run_server():
    """Run uvicorn in a subprocess."""
    config = Config("app.main:app", host="127.0.0.1", port=8000, log_level="error")
    server = uvicorn.Server(config)
    server.run()


@pytest.fixture(scope="session")
def semantic_classifier_server():
    proc = multiprocessing.Process(target=run_semantic_classifier, daemon=True)
    proc.start()
    for _ in range(50):
        try:
            with socket.create_connection(("127.0.0.1", 18081), timeout=1):
                break
        except OSError:
            time.sleep(0.1)
    else:
        proc.terminate()
        raise RuntimeError("Semantic classifier failed to start")
    yield
    proc.terminate()
    proc.join()


@pytest.fixture(scope="session")
def server(semantic_classifier_server):
    """Start the server once per test session."""
    proc = multiprocessing.Process(target=run_server, daemon=True)
    proc.start()
    # Wait for server to be ready
    for _ in range(50):
        try:
            urllib.request.urlopen("http://127.0.0.1:8000/docs", timeout=1)
            break
        except Exception:
            time.sleep(0.2)
    else:
        raise RuntimeError("Server failed to start")
    yield
    proc.terminate()
    proc.join()
