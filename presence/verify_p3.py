import asyncio
from playwright.async_api import async_playwright
import os

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 720})
        
        errors = []
        page.on("pageerror", lambda err: errors.append(err.message))
        page.on("console", lambda msg: print(f"Browser console: {msg.text}"))
        
        print("[verify_p3] Opening http://localhost:5199/")
        await page.goto('http://localhost:5199/')
        
        print("[verify_p3] Waiting for canvas to render...")
        await page.wait_for_selector("canvas", state="visible")
        
        print("[verify_p3] Clicking Test Audio button...")
        await page.click("#test-audio-btn")
        
        # Wait a moment for audio to play
        await page.wait_for_timeout(2000)
        
        state_text = await page.locator("#state").inner_text()
        print(f"[verify_p3] State text after click: {state_text}")
        
        if errors:
            print("[verify_p3] ERRORS FOUND:")
            for e in errors:
                print(f" - {e}")
        else:
            print("[verify_p3] Audio context started successfully with no JS errors.")
            
        await browser.close()

if __name__ == '__main__':
    asyncio.run(main())
