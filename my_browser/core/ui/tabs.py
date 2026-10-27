"""The tab bar's three sections, «Возможности», «Мои» and «Настройки», as one page.

All three are built at once, and app.js switches between them in the browser: at once and with an animation,
keeping the address (/, /mine, /settings), «Назад» and each section's scroll position. A page per section cost
DEEper a round trip to the server and a whole new page at every tap, 0.6–0.9 s from Russia through the proxy.

Opening an address of a section (a link, a refresh, the installed app's start) builds the whole page with that
section shown. When a section is shown again, the server redraws what may have changed since (tab_shown): a status
set, the morning update, a source added. The page is async: it fetches the radar's list, the user's own ones and
the settings first, so every section has them at the first paint.
"""

import asyncio
import inspect

from nicegui import ui

from my_browser.core.ui import kit, opps, settings

SECTIONS = ("opps", "mine", "settings")
WAIT_SEC = 1.5  # NiceGUI gives an async page 3 s; without the radar by then the sections get it when shown


async def page(active: str) -> None:
    try:
        board, own, data = await asyncio.wait_for(asyncio.gather(opps.board(), opps.mine(), settings.load()), WAIT_SEC)
    except asyncio.TimeoutError:
        board, own, data = {}, [], {}
    kit.shell(kit.TAB_TITLES[active], active=active)
    builders = {**opps.sections(board, own), "settings": lambda: settings.settings_screen(data)}
    on_show = {}
    for key in SECTIONS:
        with ui.element("section").classes("tab-screen" + (" on" if key == active else "")).props(f'data-tab="{key}"'):
            on_show[key] = builders[key]()

    async def shown(e) -> None:
        if callback := on_show.get(e.args.get("tab")):
            result = callback()
            if inspect.isawaitable(result):
                await result

    ui.on("tab_shown", shown)


@ui.page("/")
async def opps_page() -> None:
    await page("opps")


@ui.page("/mine")
async def mine_page() -> None:
    await page("mine")


@ui.page("/settings")
async def settings_page() -> None:
    await page("settings")
