import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        page.on("console", lambda msg: print(f"Browser console: {msg.text}"))
        page.on("pageerror", lambda err: print(f"Browser error: {err}"))
        await page.goto("http://localhost:5199/")
        await page.wait_for_timeout(2000)
        await browser.close()

if __name__ == '__main__':
    asyncio.run(main())
