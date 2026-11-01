import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from tests.e2e.seed import seed

APP = Path(__file__).resolve().parents[2] / "apps" / "vision" / "src" / "vision" / "development_app.py"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="session")
def app_url(tmp_path_factory):
    root = seed(tmp_path_factory.mktemp("e2e-data") / "CO-VISION-data")
    port = _free_port()
    env = dict(os.environ, CO_VISION_DATA_ROOT=str(root), PYTHONUTF8="1")
    env.pop("CO_VISION_PROOF_DB", None)
    env.pop("CO_VISION_PROOF_REFERENCE_DB", None)
    process = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run", str(APP),
            "--server.address", "127.0.0.1", "--server.port", str(port),
            "--server.headless", "true", "--browser.gatherUsageStats", "false",
        ],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(120):
            try:
                with urllib.request.urlopen(url + "/_stcore/health", timeout=1):
                    break
            except OSError:
                if process.poll() is not None:
                    raise RuntimeError("Streamlit exited before becoming healthy")
                time.sleep(0.5)
        else:
            raise RuntimeError("Streamlit did not become healthy")
        yield url
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
