"""OnePath in one process: core's web app and the radar's loop (news, which reads the opportunities).

    uv run app.py   -> http://127.0.0.1:8501 (on Railway: PORT, public, APP_PASSWORD required)

The radar's API is called in-process (no NEWS_URL). Each part also runs on its own: python -m my_browser.<part>.
"""

import os
import threading

# NiceGUI comes only through core.web: it must first point NiceGUI's storage (logins) at the volume, and NiceGUI
# reads that path when it is imported.
from my_browser.core import web
from my_browser.news import loop as radar_loop


async def start_parts() -> None:
    if os.environ.get("NEWS_LOOP", "1") != "0":
        threading.Thread(target=radar_loop.run_forever, daemon=True, name="radar-loop").start()


web.app.on_startup(start_parts)

if __name__ in {"__main__", "__mp_main__"}:
    web.main()
