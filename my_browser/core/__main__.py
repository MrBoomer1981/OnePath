"""Run core alone (the web app): uv run python -m my_browser.core. The news part then runs as its own process (NEWS_URL)."""

from my_browser.core import web

if __name__ in {"__main__", "__mp_main__"}:
    web.main()
