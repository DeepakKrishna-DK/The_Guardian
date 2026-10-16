import asyncio
from playwright.async_api import async_playwright

async def check_webgl():
    async with async_playwright() as pw:
        # Test headless=False vs headless=True
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--use-angle=d3d11",
                "--enable-webgl",
                "--enable-webgl2",
                "--ignore-gpu-blocklist",
            ]
        )
        page = await browser.new_page()
        gl_info = await page.evaluate('''() => {
            const canvas = document.createElement('canvas');
            const gl = canvas.getContext('webgl2') || canvas.getContext('webgl');
            if (!gl) return { supported: false };
            const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
            return {
                supported: true,
                version: gl.getParameter(gl.VERSION),
                vendor: debugInfo ? gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL) : 'Unknown',
                renderer: debugInfo ? gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL) : 'Unknown'
            };
        }''')
        print("Headless WebGL Query Result:", gl_info)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(check_webgl())
