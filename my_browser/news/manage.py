"""Sources the user adds and removes in «Настройки» → «Источники»: a feed's address, a Telegram channel or a page.

A new source is checked before it is stored: a feed must parse and have posts, a channel must have a public preview
with posts, an address without a feed may be a program's page, watched once a day (collectors/page.py) when it has
text without JavaScript. Its owner is the feed's site (tg:<channel> for a channel), so it counts as independent unless
that site is already among the sources. It is polled at the next tick. Removing only switches a source off: its posts
stay in their stories, and a starting source switched off is not offered again. A source switched back on joins the
lane `opps`, also one of DEEper's news sources kept switched off in a database brought over from it (db.py).
"""

import asyncio
import re
import time

import feedparser
import httpx

from my_browser.news import db, items, loop, sources
from my_browser.news.collectors import host, page, rss, telegram

CHANNEL = re.compile(r"^(?:@|https?://t\.me/(?:s/)?)([A-Za-z0-9_]{4,64})/?$")


class SourceError(ValueError):
    """A refused source; the message is for the user, in Russian."""


async def add(text: str) -> dict:
    """Check and store a source; an existing one switched off is switched back on. The stored source."""
    text = text.strip()
    category, interval = "aggregator", sources.OPPS_INTERVALS["aggregator"]
    async with httpx.AsyncClient(headers={"User-Agent": loop.USER_AGENT}, timeout=loop.TIMEOUT, follow_redirects=True) as client:
        if match := CHANNEL.match(text):
            name = match.group(1)
            if known := _channel(name):  # channel names are case-insensitive: @ITMO_Students is itmo_students
                return switch(known["id"], True)
            try:
                fetched = await telegram.fetch({"url": name}, client)
            except Exception:
                raise SourceError(f"Канал @{name} не открывается в веб-превью t.me/s: он закрытый или его нет.") from None
            if not fetched.posts:
                raise SourceError(f"У канала @{name} в превью нет постов с текстом.")
            kind, url, title, owner = "telegram", name, f"Telegram: @{name}", f"tg:{name.lower()}"
        elif text.startswith(("http://", "https://")):
            try:
                response = await client.get(text)
                response.raise_for_status()
            except Exception:
                raise SourceError("Адрес не открывается.") from None
            try:
                feed = await asyncio.to_thread(feedparser.parse, response.content)
                posts = await asyncio.to_thread(rss._parse, response.content)
            except Exception:
                feed, posts = None, []
            if posts:
                kind, url, owner = "rss", text, host(feed.feed.get("link") or text) or host(text)
                title = " ".join((feed.feed.get("title") or host(text)).split())[:80]
            else:  # a program's page without a feed: watched once a day
                title, body = await asyncio.to_thread(page.main_text, response.text)
                if len(body) < page.MIN_TEXT:
                    raise SourceError("По этому адресу нет ни ленты, ни текста без JavaScript: такую страницу не прочитать.")
                kind, url, owner, category, interval = "page", text, host(text), "program", sources.PAGE_INTERVAL
                title, posts = (title or host(text))[:80], []
            fetched = None
        else:
            raise SourceError("Нужен канал Telegram (@name), адрес RSS-ленты или страница программы (https://…).")
    lang = items.language(" ".join(p.title for p in (fetched.posts if fetched else posts)[:10]) or title)
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO sources (kind, url, name, lane, category, lang, owner, interval, added) VALUES (?, ?, ?, 'opps', ?, ?, ?, ?, ?) "
            "ON CONFLICT (kind, url) DO UPDATE SET enabled = 1, lane = 'opps'", (kind, url, title, category, lang, owner, interval,
                                                                                   time.time()))
        return dict(conn.execute("SELECT * FROM sources WHERE kind = ? AND url = ?", (kind, url)).fetchone())


def _channel(name: str) -> dict | None:
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM sources WHERE kind = 'telegram' AND lower(url) = lower(?)", (name,)).fetchone()
    return dict(row) if row else None


def find(text: str) -> list[dict]:
    """Sources matching a number, an address or a part of the name."""
    text = text.strip().removeprefix("@")
    with db.connect() as conn:
        if text.isdigit():
            rows = conn.execute("SELECT * FROM sources WHERE id = ? AND lane = 'opps'", (int(text),)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM sources WHERE lane = 'opps' AND (url = ? OR lower(name) LIKE ?) ORDER BY name",
                                (text, f"%{text.lower()}%")).fetchall()
    return [dict(row) for row in rows]


def switch(source_id: int, enabled: bool) -> dict | None:
    """Switch a source on (into the lane `opps`) or off; the source, or None when there is none."""
    with db.transaction() as conn:
        conn.execute("UPDATE sources SET enabled = ?, lane = CASE WHEN ? THEN 'opps' ELSE lane END WHERE id = ?",
                     (int(enabled), int(enabled), source_id))
        row = conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
    return dict(row) if row else None
