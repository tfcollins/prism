#!/usr/bin/env python3
"""Capture Prism UI screenshots for the documentation.

Runs against a live, seeded stack (see ``tutorials/getting-started``). Logs in,
walks the key pages, and writes PNGs into ``source/_static/img/screenshots/``.

    python3 docs/shots.py

Run-id discovery reuses the vetted ``PrismClient`` from ``scripts/`` so the
auth/CSRF/HTTP plumbing lives in exactly one place.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

# Reuse the stdlib-only API client that the other repo scripts share.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from _prism_client import PrismClient

BASE = os.environ.get("PRISM_WEB_URL", "http://localhost:8180")
API = os.environ.get("PRISM_URL", "http://localhost:8000")
EMAIL = os.environ.get("PRISM_EMAIL", "admin@example.com")
PASSWORD = os.environ.get("PRISM_PASSWORD", "prismdocs123")
PROJECT = os.environ.get("PRISM_PROJECT", "audio")
OUT = Path(__file__).parent / "source" / "_static" / "img" / "screenshots"

VIEWPORT = {"width": 1440, "height": 900}
CASE_SELECTORS = (
    "text=/sine|sweep|tone|chirp/i",
    "[role=button]:has-text('sweep')",
    "button:has-text('sweep')",
)


def shot(page: Page, name: str) -> None:
    path = OUT / f"{name}.png"
    page.screenshot(path=str(path))
    print(f"  wrote {path.relative_to(Path(__file__).parent)}")


def first_present(page: Page, selectors: tuple[str, ...]) -> object | None:
    """Return the first locator that matches at least one element, else None."""
    for sel in selectors:
        loc = page.locator(sel).first
        if loc.count() > 0:
            return loc
    return None


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    # Discover run ids via the API so we can deep-link to specific runs.
    client = PrismClient(API)
    client.login(EMAIL, PASSWORD)
    runs = client.list_runs(PROJECT)
    by_name = {str(r["name"]): str(r["id"]) for r in runs}
    dsp_runs = [str(r["id"]) for r in runs if str(r["name"]).startswith("dsp")]
    run_id = by_name.get("dsp-nightly-41") or (dsp_runs[0] if dsp_runs else str(runs[0]["id"]))
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

        # authenticate — login lands on the Overview landing page
        page.fill('input[type="email"]', EMAIL)
        page.fill('input[type="password"]', PASSWORD)
        page.click('button[type="submit"]')
        page.get_by_role("heading", name="Overview").wait_for(timeout=15000)
        page.wait_for_timeout(1000)
        shot(page, "overview")

        # --- projects list ---
        page.goto(f"{BASE}/projects", wait_until="networkidle")
        page.wait_for_timeout(800)
        shot(page, "projects")

        # --- project dashboard ---
        page.goto(f"{BASE}/projects/{PROJECT}", wait_until="networkidle")
        page.wait_for_timeout(1500)
        shot(page, "dashboard")

        # --- export actions: select two runs to reveal Export PDF / Compare ---
        rows = page.locator("tbody tr")
        if rows.count() >= 2:
            for i in (0, 1):
                box = rows.nth(i).locator('label[data-scope="checkbox"]')
                if box.count() > 0:
                    box.click()
            page.wait_for_timeout(600)
            shot(page, "export-actions")

        # --- run detail with waveform plot ---
        page.goto(f"{BASE}/runs/{run_id}", wait_until="networkidle")
        page.wait_for_timeout(1200)
        case = first_present(page, CASE_SELECTORS)
        if case is not None:
            case.click(timeout=2500)
        page.wait_for_timeout(2500)
        shot(page, "run-detail")

        # FFT tab if present
        fft = first_present(page, ("text=FFT",))
        if fft is not None:
            fft.click(timeout=2000)
            page.wait_for_timeout(2500)
            shot(page, "fft")

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
