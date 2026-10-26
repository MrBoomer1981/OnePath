"""Run core alone (web app + API): uv run python -m my_browser.core. The worker runs as its own process then."""

from my_browser.core import web

if __name__ in {"__main__", "__mp_main__"}:
    web.main()
