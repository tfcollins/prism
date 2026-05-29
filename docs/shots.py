#!/usr/bin/env python3
"""Capture Prism UI screenshots for the documentation.

Runs against a live, seeded stack (see docs how-to). Logs in, walks the
key pages, and writes PNGs into source/_static/img/screenshots/.

    python3 docs/shots.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.environ.get("PRISM_WEB_URL", "http://localhost:8180")
API = os.environ.get("PRISM_URL", "http://localhost:8000")
EMAIL = os.environ.get("PRISM_EMAIL", "admin@example.com")
PASSWORD = os.environ.get("PRISM_PASSWORD", "prismdocs123")
PROJECT = os.environ.get("PRISM_PROJECT", "audio")
OUT = Path(__file__).parent / "source" / "_static" / "img" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)

VIEWPORT = {"width": 1440, "height": 900}


def shot(page, name: str, full: bool = False) -> None:
    path = OUT / f"{name}.png"
    page.screenshot(path=str(path), full_page=full)
    print(f"  wrote {path.relative_to(Path(__file__).parent)}")


def main() -> int:
    import urllib.request
    import json

    # Find run ids via the API so we can deep-link.
    cj = "/tmp/shots_cookies.txt"
    import http.cookiejar

    jar = http.cookiejar.MozillaCookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    req = urllib.request.Request(
        f"{API}/api/v1/auth/login",
        data=json.dumps({"email": EMAIL, "password": PASSWORD}).encode(),
        headers={"Content-Type": "application/json"},
    )
    opener.open(req)
    runs = json.loads(opener.open(f"{API}/api/v1/runs?project={PROJECT}&limit=50").read())
    items = runs if isinstance(runs, list) else runs.get("items", [])
    by_name = {r["name"]: r["id"] for r in items}
    dsp_runs = [r["id"] for r in items if r["name"].startswith("dsp")]
    run_id = by_name.get("dsp-nightly-41") or (dsp_runs[0] if dsp_runs else items[0]["id"])
    compare_pair = ",".join(dsp_runs[:2]) if len(dsp_runs) >= 2 else ""
    print(f"run_id={run_id} compare_pair={compare_pair}")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport=VIEWPORT, color_scheme="dark", device_scale_factor=2)
        page = ctx.new_page()

        # --- login ---
        page.goto(f"{BASE}/login", wait_until="networkidle")
        page.wait_for_timeout(500)
        shot(page, "login")

        # authenticate
        page.fill('input[type="email"]', EMAIL)
        page.fill('input[type="password"]', PASSWORD)
        page.click('button[type="submit"]')
        page.wait_for_url("**/projects", timeout=15000)
        page.wait_for_timeout(800)
        shot(page, "projects")

        # --- project dashboard ---
        page.goto(f"{BASE}/projects/{PROJECT}", wait_until="networkidle")
        page.wait_for_timeout(1500)
        shot(page, "dashboard")

        # --- run detail with waveform plot ---
        page.goto(f"{BASE}/runs/{run_id}", wait_until="networkidle")
        page.wait_for_timeout(1200)
        # click first test case that has a plot
        for sel in [
            "text=/sine|sweep|tone|chirp/i",
            "[role=button]:has-text('sweep')",
            "button:has-text('sweep')",
        ]:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0:
                    loc.click(timeout=2500)
                    break
            except Exception:
                continue
        page.wait_for_timeout(2500)
        shot(page, "run-detail")

        # FFT tab if present
        try:
            fft = page.locator("text=FFT").first
            if fft.count() > 0:
                fft.click(timeout=2000)
                page.wait_for_timeout(2500)
                shot(page, "fft")
        except Exception:
            pass

        # --- compare ---
        if compare_pair:
            page.goto(f"{BASE}/compare?runs={compare_pair}", wait_until="networkidle")
            page.wait_for_timeout(3000)
            shot(page, "compare")

        ctx.close()
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
