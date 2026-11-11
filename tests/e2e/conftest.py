"""
The website in a real browser (Chromium, headless), against the offline demo: recorded
answers, no models. Starts `streamlit run app/streamlit_app.py` on a free port, or uses
E2E_BASE_URL (e.g. the Docker image). Marked e2e, so the normal test run skips them:

    python -m pytest tests/e2e -m e2e                # all browser tests
    E2E_SCREENSHOTS=docs/figures python -m pytest tests/e2e -m e2e   # + the README pictures
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

from rag import paths

try:
    from playwright import sync_api as playwright
except ImportError:                    # pip install -r requirements/e2e.txt
    playwright = None
    collect_ignore_glob = ["test_*.py"]

DELAY_S = "0.4"        # the offline demo reports stages slowly, so the progress box shows


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def base_url():
    if os.environ.get("E2E_BASE_URL"):
        yield os.environ["E2E_BASE_URL"].rstrip("/")
        return
    port = free_port()
    env = {**os.environ, "RAG_OFFLINE": "1", "RAG_OFFLINE_DELAY_S": DELAY_S}
    env.pop("RAG_ADMIN", None)
    server = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app/streamlit_app.py",
         "--server.port", str(port), "--server.headless", "true"],
        cwd=paths.ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 60
        while True:
            try:
                urllib.request.urlopen(f"{url}/_stcore/health", timeout=1)
                break
            except OSError:
                assert time.monotonic() < deadline, "streamlit did not start"
                time.sleep(0.2)
        yield url
    finally:
        server.terminate()
        server.wait(10)


@pytest.fixture(scope="session")
def browser():
    with playwright.sync_playwright() as p:
        chromium = p.chromium.launch()
        yield chromium
        chromium.close()


@pytest.fixture
def open_page(browser, base_url):
    """open_page(query="", width=1280, scheme="light") -> a loaded page."""
    pages = []

    def open_(query: str = "", width: int = 1280, scheme: str = "light", height: int = 900):
        page = browser.new_page(viewport={"width": width, "height": height}, color_scheme=scheme)
        pages.append(page)
        page.goto(f"{base_url}/{query}")
        page.locator("textarea").wait_for(timeout=30000)
        return page

    yield open_
    for page in pages:
        page.close()
