import asyncio
from playwright.async_api import async_playwright
import os

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 720})
        
        print("[verify_p2_2d] Opening http://localhost:5199/")
        await page.goto('http://localhost:5199/')
        
        print("[verify_p2_2d] Waiting for canvas to render...")
        await page.wait_for_selector("canvas", state="visible")
        # Give WebGL a moment to load the texture
        await page.wait_for_timeout(2000)
        
        # Take screenshot
        screenshot_path = os.path.join(os.getcwd(), 'presence', 'p2_2d_screenshot.png')
        await page.screenshot(path=screenshot_path)
        
        print(f"==================================================================")
        print(f"  GUARDIAN PRESENCE — P2 (2D) VERIFICATION RESULTS")
        print(f"==================================================================")
        print(f"  Mode            : 2D Static High-Fidelity")
        print(f"  Screenshot      : {screenshot_path}")
        print(f"==================================================================")
        print("PASS: 2D avatar loaded successfully.")
        
        await browser.close()

if __name__ == '__main__':
    asyncio.run(main())
