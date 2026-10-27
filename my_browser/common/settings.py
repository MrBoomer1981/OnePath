"""Settings shared by every part: paths, the web search, and how the parts reach each other.

OnePath runs as two parts: core (the web UI) and news (the opportunities radar: sources, posts, reading them with
the LLM, the morning update, and its loop; the part keeps DEEper's name, see the root CLAUDE.md). Each can run as its
own process. An unset NEWS_URL means the all-in-one process (Railway, `uv run app.py`): core serves HTTP and calls
news in-process through its ASGI app.
"""

import logging
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config.json"

load_dotenv(ROOT / ".env")

REPORTS_DIR = Path(os.environ.get("REPORTS_DIR") or ROOT / "reports")  # the app's state: news.sqlite, logins

# The weekly web search for opportunities (news/discover.py): the local SearXNG when SEARX_URL is set; otherwise
# Tavily if its key is present (Railway has no SearXNG). WEB_RETRIEVER overrides the choice.
WEB_RETRIEVER = os.environ.get("WEB_RETRIEVER") or (
    "tavily" if os.environ.get("TAVILY_API_KEY") and not os.environ.get("SEARX_URL") else "searx"
)

# DEEper, the user's research app: «Исследовать» on an opportunity opens its search screen with the opportunity as
# the topic. Its address stays out of this public repository (a Railway variable); unset, the button is not shown.
RESEARCH_URL = os.environ.get("RESEARCH_URL", "").rstrip("/")

PORT = int(os.environ.get("PORT", 8501))  # 8080 is the local SearXNG
CORE_URL = os.environ.get("CORE_URL") or f"http://127.0.0.1:{PORT}"
NEWS_URL = os.environ.get("NEWS_URL")  # unset: in-process


def service_token() -> str:
    """Shared secret of the parts' APIs: SERVICE_TOKEN, else a file next to the app's state (one machine)."""
    if token := os.environ.get("SERVICE_TOKEN"):
        return token
    path = REPORTS_DIR / ".service_token"
    if not path.exists():
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(secrets.token_hex(24))
    return path.read_text().strip()


def configure_logging() -> None:
    """INFO for our parts; httpx logs every request at INFO, and the loop polls dozens of sources."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
