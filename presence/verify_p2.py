"""
Guardian Presence — Phase P2 Verification Script
==================================================
Assumes Vite is ALREADY RUNNING on port 5199.

Verification steps:
  1. Open the Presence page in non-headless Chromium (GPU rendered)
  2. Wait for window.__presenceLoaded == true (GLB fully parsed)
  3. Wait a further SETTLE_SECS for FPS to stabilise with the real mesh
  4. Read: FPS, frame time, draw calls, triangle count
  5. Read: mesh info, animation names, morph target names
  6. Read: WebGL renderer, software flag
  7. Save screenshot
  8. Report all values — fail if software render, FPS < MIN_FPS, or GLB not loaded

Run from Guardian repo root (Vite must be running):
    .\\venv\\Scripts\\python.exe presence\\verify_p2.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

VITE_PORT   = 5199
LOAD_TIMEOUT = 20_000   # ms to wait for GLB to load
SETTLE_SECS  = 6        # seconds to stabilise FPS after load
MIN_FPS      = 30


async def main() -> int:
    from playwright.async_api import async_playwright

    url = f"http://localhost:{VITE_PORT}/"
    print(f"[verify_p2] Opening {url}")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=False,
            args=[
                "--use-angle=d3d11",
                "--enable-webgl",
                "--enable-webgl2",
                "--ignore-gpu-blocklist",
                "--disable-gpu-sandbox",
            ],
        )
        page = await browser.new_page(viewport={"width": 1280, "height": 720})

        # Forward browser console to our stdout
        page.on("console", lambda m: print(f"  [browser] {m.text}"))

        await page.goto(url, wait_until="domcontentloaded", timeout=15_000)

        # Wait for the GLB to finish loading (window.__presenceLoaded = true)
        print(f"[verify_p2] Waiting for GLB load (timeout {LOAD_TIMEOUT}ms)…")
        await page.wait_for_function("window.__presenceLoaded === true", timeout=LOAD_TIMEOUT)
        print(f"[verify_p2] GLB loaded. Waiting {SETTLE_SECS}s for FPS to stabilise…")
        await asyncio.sleep(SETTLE_SECS)

        # ── Read render measurements ─────────────────────────────────
        fps          = await page.evaluate("window.__presenceFPS")
        frame_ms     = await page.evaluate("window.__presenceFrameMs")
        renderer     = await page.evaluate("window.__presenceRenderer")
        vendor       = await page.evaluate("window.__presenceVendor")
        wgl_ver      = await page.evaluate("window.__presenceWebGLVersion")
        is_sw        = await page.evaluate("window.__presenceIsSoftware")

        # ── Read model info ──────────────────────────────────────────
        mesh_info    = await page.evaluate("window.__presenceMeshInfo")
        animations   = await page.evaluate("window.__presenceAnimations")
        morph_keys   = await page.evaluate("window.__presenceMorphTargets")

        # ── Read HUD text ────────────────────────────────────────────
        fps_text     = await page.inner_text("#fps")
        frame_text   = await page.inner_text("#frame-time")
        draw_text    = await page.inner_text("#drawcalls")
        tri_text     = await page.inner_text("#triangles")
        state_text   = await page.inner_text("#state")
        webgl_text   = await page.inner_text("#webgl-info")

        shot_path    = Path(__file__).parent / "p2_screenshot.png"
        await page.screenshot(path=str(shot_path))

        await browser.close()

    # ── Report ───────────────────────────────────────────────────────
    print()
    print("=" * 66)
    print("  GUARDIAN PRESENCE — P2 VERIFICATION RESULTS")
    print("=" * 66)
    print(f"  WebGL version   : {wgl_ver}")
    print(f"  GPU vendor      : {vendor}")
    print(f"  GPU renderer    : {renderer}")
    print(f"  Software render : {is_sw}  ({'⚠ WARNING' if is_sw else 'OK — hardware GPU'})")
    print()
    print(f"  FPS (1s avg)    : {fps}  (minimum: {MIN_FPS})")
    print(f"  Frame time      : {frame_ms}ms")
    print(f"  Draw calls/fr   : {draw_text}")
    print(f"  Triangles/fr    : {tri_text}")
    print(f"  State           : {state_text}")
    print()
    print(f"  Mesh count      : {len(mesh_info) if mesh_info else 'N/A'}")
    if mesh_info:
        for m in mesh_info:
            mt = m.get('morphTargetCount', 0)
            mkeys = m.get('morphTargetKeys', [])
            print(f"    • {m['name']:30s}  mat={m.get('matName','?'):20s}  morph={mt}  {mkeys}")
    print()
    print(f"  Animations      : {animations}")
    print(f"  Morph targets   : {morph_keys}")
    print()
    print(f"  WebGL DOM       : {webgl_text}")
    print(f"  Screenshot      : {shot_path}")
    print("=" * 66)

    # ── Pass / fail ──────────────────────────────────────────────────
    passed = True
    if not mesh_info:
        print("FAIL: GLB loaded but no meshes found.")
        passed = False
    if is_sw:
        print(f"FAIL: Software renderer ({renderer}).")
        passed = False
    if fps is None:
        print("FAIL: FPS counter never updated.")
        passed = False
    elif fps < MIN_FPS:
        print(f"FAIL: {fps} FPS < minimum {MIN_FPS}.")
        passed = False

    if passed:
        print(f"PASS: {fps} FPS | {len(mesh_info)} meshes | {len(morph_keys)} morph targets | {len(animations)} animations")

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
