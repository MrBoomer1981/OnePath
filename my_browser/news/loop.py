"""The radar's loop: a plain thread that wakes every minute and does what is due.

Each tick polls the sources whose interval has passed and stores their new posts, and once a week searches the web
for opportunities the sources missed (discover.py); every few minutes it merges the new posts into stories (dedup.py)
and has the LLM read them (opps.py); once a morning it updates the app's list (opps_delivery.py). One loop per
REPORTS_DIR: the all-in-one app.py starts it next to the web app (NEWS_LOOP=0 turns it off), `python -m
my_browser.news` next to its API. Every tick is marked in the state table, so /status can tell whether a loop runs.
"""

import asyncio
import logging
import threading
import time

import httpx

from my_browser.common import memory
from my_browser.news import collectors, config, db, dedup, discover, items, opps, opps_delivery, sources

logger = logging.getLogger(__name__)

TICK_SEC = 60
CONCURRENCY = 6
HOST_GAP_SEC = 2.0  # between two requests to one host: t.me serves a dozen channels
TIMEOUT = httpx.Timeout(25, connect=10)
# A browser's User-Agent: every starting source answered it on 25.10.2026, some refuse unknown clients.
USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) "
              "Version/17.0 Safari/605.1.15")
SLIM_EVERY_SEC = 86400
DEDUP_EVERY_SEC = 300  # an embedding run starts a child process and loads the model: a few seconds

_collecting = threading.Lock()  # the loop and POST /collect never poll at once


async def collect(everything: bool = False) -> dict:
    """Poll the due sources (every enabled one with `everything`) and store their posts; a summary of the run."""
    if not _collecting.acquire(blocking=False):
        return {"busy": True}
    try:
        return await _collect(everything)
    finally:
        _collecting.release()


async def _collect(everything: bool) -> dict:
    started = time.monotonic()
    todo = sources.enabled() if everything else sources.due()
    semaphore, host_locks = asyncio.Semaphore(CONCURRENCY), {}
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT, follow_redirects=True) as client:
        results = await asyncio.gather(*(
            _poll(source, client, semaphore, host_locks.setdefault(collectors.host(source["url"]), asyncio.Lock()))
            for source in todo))
    done = [r for r in results if r is not None]
    summary = {"at": time.time(), "polled": len(todo), "new": sum(r[0] for r in done),
               "inserted": sum(r[1] for r in done), "failed": len(results) - len(done),
               "seconds": round(time.monotonic() - started, 1)}
    if todo:
        db.set_state("last_collect", summary)
    return summary


async def _poll(source: dict, client: httpx.AsyncClient, semaphore: asyncio.Semaphore,
                host_lock: asyncio.Lock) -> tuple[int, int] | None:
    """(fresh, inserted) posts of one source, or None when it failed; one request per host at a time."""
    async with host_lock:
        async with semaphore:
            try:
                fetched = await collectors.fetch(source, client)
                result = items.store(source, fetched.posts)
                sources.mark_ok(source["id"], fetched.etag, fetched.modified, fetched.page_hash, fetched.page_text)
            except Exception as e:  # one broken source must not stop the others
                error = _describe(e)
                logger.warning("Source failed: %s (%s)", source["name"], error)
                sources.mark_failed(source["id"], error)
                result = None
        await asyncio.sleep(HOST_GAP_SEC)
    return result


def _describe(error: Exception) -> str:
    if isinstance(error, httpx.HTTPStatusError):
        return f"HTTP {error.response.status_code}"
    if isinstance(error, httpx.TimeoutException):
        return "timeout"
    return f"{type(error).__name__}: {error}"[:200]


def tick() -> None:
    now = time.time()
    db.set_state("loop_tick", now)
    if sources.due(now):
        summary = asyncio.run(collect())
        if summary.get("new") or summary.get("failed"):
            logger.info("Sources: %(polled)d polled, %(new)d new posts, %(failed)d failed, %(seconds)s s", summary)
        memory.trim()  # the parsed feeds and pages: free pages back to the system
    try:
        asyncio.run(discover.run())  # once a week; its new pages are merged below like any posts
    except Exception:  # one failing step must not stop the others
        logger.exception("Loop: web search for opportunities failed")
    if now - (db.get_state("dedup_at") or 0) >= DEDUP_EVERY_SEC:
        db.set_state("dedup_at", now)  # before the run: a failing model does not retry every minute
        try:
            dedup.run()
        except Exception:
            logger.exception("Loop: merging failed")
        try:
            asyncio.run(opps.run())  # stories merged before still get read when merging failed
        except Exception:
            logger.exception("Loop: reading opportunities failed")
        memory.release()  # every few minutes, the parse trees' cycles too (a collection holds the GIL a moment)
    try:
        opps_delivery.run()
    except Exception:
        logger.exception("Loop: the morning update failed")
    if now - (db.get_state("slimmed_at") or 0) > SLIM_EVERY_SEC:
        db.set_state("slimmed_at", now)
        items.slim()
        logger.info("Database copied to %s", db.backup().name)


def run_forever(stop: threading.Event | None = None) -> None:
    """Tick until stopped; meant for its own thread."""
    stop = stop or threading.Event()
    config.upgrade()
    if added := sources.seed():
        logger.info("Sources: %d starting sources added", added)
    if single := items.refresh_digests():
        logger.info("Opportunities: %d posts taken for roundups are single announcements after all", single)
    if widened := items.widen_opps_window():
        logger.info("Opportunities: %d sources polled again in full: posts of the last %d days get read",
                    widened, items.OPPS_FRESH_DAYS)
    logger.info("Radar loop ready")
    while not stop.is_set():
        try:
            tick()
        except Exception:
            logger.exception("Loop: tick failed")
        stop.wait(TICK_SEC)
