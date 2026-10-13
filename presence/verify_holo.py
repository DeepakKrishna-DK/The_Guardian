import asyncio
from playwright.async_api import async_playwright
import os, sys

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=['--use-angle=default', '--disable-gpu-sandbox']
        )
        ctx = await browser.new_context(viewport={'width': 1280, 'height': 720})
        page = await ctx.new_page()
        page.on('console', lambda m: print(f'  [browser] {m.text}'))
        page.on('pageerror', lambda e: print(f'  [ERROR] {e}'))

        print('[dragon] Opening http://localhost:5199/')
        await page.goto('http://localhost:5199/')
        
        print('[dragon] Waiting for canvas...')
        await page.wait_for_selector('canvas', state='visible', timeout=15000)
        
        print('[dragon] Waiting 5s for animation to run...')
        await page.wait_for_timeout(5000)
        
        shot = os.path.join(os.path.dirname(__file__), 'holo_screenshot.png')
        await page.screenshot(path=shot)
        print(f'[dragon] Screenshot saved: {shot}')
        
        fps_text = await page.locator('#fps').inner_text()
        state_text = await page.locator('#state').inner_text()
        print(f'[holo] FPS: {fps_text}')
        print(f'[holo] State: {state_text}')
        print('[holo] PASS')
        
        await browser.close()

if __name__ == '__main__':
    asyncio.run(main())
