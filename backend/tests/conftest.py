"""Start the FastAPI server in the background for integration tests."""

import multiprocessing
import time
import urllib.request

import pytest
import uvicorn
from uvicorn.config import Config


def run_server():
    """Run uvicorn in a subprocess."""
    config = Config("app.main:app", host="127.0.0.1", port=8000, log_level="error")
    server = uvicorn.Server(config)
    server.run()


@pytest.fixture(scope="session")
def server():
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
