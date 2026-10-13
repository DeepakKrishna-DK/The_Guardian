"""
Guardian Presence — Phase P1 Verification Script (Windows fix)
===============================================================
Assumes Vite is ALREADY RUNNING on port 5199.
Uses Playwright to open the render page, read FPS + WebGL info, report.

Run from Guardian repo root with Vite already started:
    .\\venv\\Scripts\\python.exe presence\\verify_p1.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

VITE_PORT = 5199
SETTLE_SECS = 6     # seconds to render before reading FPS
MIN_FPS = 30


async def main() -> int:
    from playwright.async_api import async_playwright

    url = f"http://localhost:{VITE_PORT}/"
    print(f"[verify_p1] Connecting to Vite at {url}")
    print(f"[verify_p1] Waiting {SETTLE_SECS}s for FPS to stabilise...")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=False,  # MUST be False to use real GPU
            args=[
                "--use-angle=d3d11",
                "--enable-webgl",
                "--enable-webgl2",
                "--ignore-gpu-blocklist",
                "--disable-gpu-sandbox",
            ],
        )
        page = await browser.new_page(viewport={"width": 1280, "height": 720})

        await page.goto(url, wait_until="domcontentloaded", timeout=15_000)
        await page.wait_for_selector("#webgl-info", timeout=10_000)

        # Wait for FPS counter to tick (render loop must stabilise)
        await asyncio.sleep(SETTLE_SECS)

        # Read measured values from window globals (set by render loop)
        fps      = await page.evaluate("window.__presenceFPS")
        frame_ms = await page.evaluate("window.__presenceFrameMs")
        renderer = await page.evaluate("window.__presenceRenderer")
        vendor   = await page.evaluate("window.__presenceVendor")
        wgl_ver  = await page.evaluate("window.__presenceWebGLVersion")
        is_sw    = await page.evaluate("window.__presenceIsSoftware")

        webgl_text = await page.inner_text("#webgl-info")
        fps_text   = await page.inner_text("#fps")
        frame_text = await page.inner_text("#frame-time")
        draw_text  = await page.inner_text("#drawcalls")

        shot_path = Path(__file__).parent / "p1_screenshot.png"
        await page.screenshot(path=str(shot_path))

        await browser.close()

    # ── Report ──────────────────────────────────────────────────────
    print()
    print("=" * 62)
    print("  GUARDIAN PRESENCE — P1 VERIFICATION RESULTS")
    print("=" * 62)
    print(f"  WebGL version   : {wgl_ver}")
    print(f"  GPU vendor      : {vendor}")
    print(f"  GPU renderer    : {renderer}")
    print(f"  Software render : {is_sw}  ({'⚠ WARNING: GPU NOT USED' if is_sw else 'OK — hardware GPU'})")
    print(f"  FPS (1s avg)    : {fps}  (minimum required: {MIN_FPS})")
    print(f"  Frame time      : {frame_ms}ms")
    print(f"  Draw calls/fr   : {draw_text}")
    print(f"  WebGL DOM text  : {webgl_text}")
    print(f"  Screenshot      : {shot_path}")
    print("=" * 62)

    if fps is None:
        print("RESULT: FAIL — FPS counter never updated (render loop issue)")
        return 1
    if is_sw:
        print(f"RESULT: FAIL — Software renderer ({renderer}). GPU not used.")
        return 1
    if fps < MIN_FPS:
        print(f"RESULT: FAIL — {fps} FPS < minimum {MIN_FPS}")
        return 1

    print(f"RESULT: PASS — {fps} FPS on {renderer}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
