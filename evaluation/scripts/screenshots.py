"""Operate the real EventAI web app with Playwright (Microsoft Edge) and capture
screenshots for the paper. Starts the FastAPI backend (isolated demo database) and the
Vite dev server, registers an organiser, uploads a TED-LIUM talk through the UI and
captures the live pipeline, the Content Studio, the transcript and the review screen.

    python evaluation/scripts/screenshots.py --talk Brian_Cox
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

EVAL = Path(__file__).resolve().parents[1]
ROOT = EVAL.parent
SHOTS = EVAL / "figures" / "screenshots"
# Separate ports so a developer's own servers on 8000/5173 are left alone.
API = "http://127.0.0.1:8010"
WEB = "http://localhost:5180"


def wait_http(url: str, timeout: float = 120) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=3)
            return
        except Exception:
            time.sleep(1)
    raise TimeoutError(url)


def start_servers() -> list[subprocess.Popen]:
    work = EVAL / "work"
    work.mkdir(exist_ok=True)
    env = {**os.environ,
           "DATABASE_URL": f"sqlite+aiosqlite:///{(work / 'ui_demo.db').as_posix()}",
           "MEDIA_ROOT": str(work / "media_ui"), "STORAGE_BACKEND": "local",
           "USE_CELERY": "false", "RATE_LIMIT_ENABLED": "false", "DEBUG": "false",
           "CORS_ORIGINS": WEB, "VITE_API_PROXY": API}
    logs = EVAL / "results" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    api = subprocess.Popen(
        [str(ROOT / "server" / ".venv" / "Scripts" / "python.exe"), "-m", "uvicorn", "app.main:app",
         "--port", "8010"], cwd=ROOT / "server", env=env,
        stdout=open(logs / "ui_api.log", "w"), stderr=subprocess.STDOUT)
    web = subprocess.Popen(["node", str(ROOT / "client" / "node_modules" / "vite" / "bin" / "vite.js"),
                            "--port", "5180", "--strictPort"], cwd=ROOT / "client",
                           env=env, stdout=open(logs / "ui_web.log", "w"), stderr=subprocess.STDOUT)
    procs = [api, web]
    try:
        wait_http(f"{API}/health")
        wait_http(WEB)
    except Exception:
        stop(procs)
        raise
    return procs


def stop(procs) -> None:
    for proc in procs:
        subprocess.run(f"taskkill /F /T /PID {proc.pid}", shell=True, capture_output=True)


def shot(page, name: str, full: bool = False) -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.wait_for_timeout(800)
    page.screenshot(path=str(SHOTS / f"{name}.png"), full_page=full)
    print("screenshot", name, flush=True)


def click_text(page, pattern: str, role: str = "button") -> bool:
    loc = page.get_by_role(role, name=re.compile(pattern, re.I))
    if loc.count():
        loc.first.click()
        return True
    return False


def run(talk: str) -> None:
    from playwright.sync_api import sync_playwright

    audio = EVAL / "data" / "audio" / f"{talk}.wav"
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2,
                                  color_scheme="dark")
        page = ctx.new_page()

        page.goto(WEB + "/")
        shot(page, "01_landing")

        page.goto(WEB + "/register")
        email = f"organiser_{uuid.uuid4().hex[:6]}@example.com"
        page.fill('input[type="email"]', email)
        page.fill('input[type="password"]', "password123")
        page.select_option("select", "event_organizer")
        shot(page, "02_register")
        page.get_by_role("button", name=re.compile("Create account", re.I)).click()
        page.wait_for_url(re.compile(r"/organizer/dashboard|/dashboard"), timeout=30000)

        page.goto(WEB + "/settings")
        page.wait_for_load_state("networkidle")
        shot(page, "03_settings", full=True)
        token = page.evaluate("() => Object.entries(localStorage).map(([k,v]) => k + '=' + v).join('\\n')")
        m = re.search(r'"?access_token"?\s*[:=]\s*"?([A-Za-z0-9._-]{20,})', token or "")
        if m:  # same neutral profile as the evaluation runs, set through the API
            req = urllib.request.Request(
                f"{API}/api/v1/auth/profile", method="PUT",
                data=b'{"full_name": "EventAI Research Team", "organization": "EventAI", "job_title": "Content Team"}',
                headers={"Authorization": f"Bearer {m.group(1)}", "Content-Type": "application/json"})
            urllib.request.urlopen(req)

        page.goto(WEB + "/organizer/dashboard")
        page.wait_for_load_state("networkidle")
        shot(page, "04_dashboard", full=True)

        page.set_input_files('input[type="file"]', str(audio))
        click_text(page, r"^Select all$")
        click_text(page, r"Hindi")
        page.get_by_text("New recording").scroll_into_view_if_needed()
        shot(page, "05_upload_form")
        click_text(page, r"Generate \d+ drafts")
        page.wait_for_url(re.compile(r"/jobs/"), timeout=120000)
        job_url = page.url

        # Live pipeline view while the agents run, then the finished state.
        for i in range(1, 4):
            page.wait_for_timeout(6000)
            shot(page, f"06_pipeline_live_{i}")
        deadline = time.time() + 600
        while time.time() < deadline:
            body = page.inner_text("body")
            if re.search(r"pending.review|Ready to publish|needs.review|Approve", body, re.I):
                break
            page.wait_for_timeout(3000)
        page.reload()
        page.wait_for_load_state("networkidle")
        shot(page, "07_job_complete")
        shot(page, "07_job_complete_full", full=True)

        for name in ("Summary", "Blog", "LinkedIn", "Newsletter", "Instagram", "Flyer"):
            if click_text(page, rf"{name}"):
                shot(page, f"08_studio_{name.lower()}")
        if click_text(page, r"Hindi|हिंदी|HI\b"):
            shot(page, "09_studio_hindi")
        if click_text(page, r"Transcript"):
            shot(page, "10_transcript")

        page.goto(job_url)
        page.wait_for_load_state("networkidle")
        review = page.locator('a[href*="/review/"]')
        if review.count():
            review.first.click()
            page.wait_for_load_state("networkidle")
            shot(page, "11_review", full=True)
        browser.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--talk", default="Brian_Cox")
    args = ap.parse_args()
    procs = start_servers()
    try:
        run(args.talk)
    finally:
        stop(procs)


if __name__ == "__main__":
    sys.exit(main())
