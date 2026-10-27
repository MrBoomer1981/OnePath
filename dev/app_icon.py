"""Draw the app's icon PNGs from their SVGs with the installed Chrome: static/icon.svg and static/favicon.svg.

    uv run --with playwright dev/app_icon.py    # after a change of either SVG

icon.svg gives the manifest's icons (1024, 512, 192) and the iPhone's apple-touch-icon (180: opaque, iOS rounds the
corners itself); favicon.svg, the same door without its small details, the browser tab's favicon.png (64). The
512 one is also the manifest's maskable icon: keep the door within the middle 80% circle of icon.svg.
"""

import asyncio
import base64
from pathlib import Path

from playwright.async_api import async_playwright

STATIC = Path(__file__).resolve().parents[1] / "static"
PNGS = {
    "icon.svg": {"icon-1024.png": 1024, "icon-512.png": 512, "icon-192.png": 192, "apple-touch-icon.png": 180},
    "favicon.svg": {"favicon.png": 64},
}


async def main() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome", headless=True)
        for svg, outputs in PNGS.items():
            src = "data:image/svg+xml;base64," + base64.b64encode((STATIC / svg).read_bytes()).decode()
            for name, size in outputs.items():
                page = await browser.new_page(viewport={"width": size, "height": size})
                await page.set_content(f'<body style="margin:0"><img src="{src}" style="display:block;width:{size}px;height:{size}px">')
                await page.wait_for_function("document.images[0].complete")
                if not await page.evaluate("document.images[0].naturalWidth"):  # a broken SVG draws a white square
                    raise SystemExit(f"{svg} does not load: not valid XML? (a comment may not contain «--»)")
                await page.screenshot(path=STATIC / name)
                await page.close()
                print(f"{name}: {size}×{size}")
        await browser.close()


asyncio.run(main())
