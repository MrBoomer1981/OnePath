"""The radar's API, for core's screens (and checks).

In the all-in-one process core calls this app in-process; on its own it runs with `uv run python -m my_browser.news`
(NEWS_PORT, default 8504) together with the loop.
"""

import time
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from my_browser.common.auth import require_token
from my_browser.news import config, db, dedup, items, llm, loop, manage, opps, opps_delivery, sources

_seeded = False


def seeded() -> None:
    """The starting sources are in the table even when the loop does not run in this process."""
    global _seeded
    if not _seeded:
        sources.seed()
        _seeded = True


app = FastAPI(title="OnePath radar", dependencies=[Depends(require_token), Depends(seeded)])


def _local(ts: float | None, tz: ZoneInfo) -> str | None:
    return datetime.fromtimestamp(ts, tz).isoformat(timespec="seconds") if ts else None


def _sources(conn) -> dict:
    counts = conn.execute(
        "SELECT COUNT(*) AS total, COALESCE(SUM(enabled), 0) AS enabled, "
        "COALESCE(SUM(enabled AND last_ok IS NOT NULL AND last_error IS NULL), 0) AS ok, "
        "COALESCE(SUM(enabled AND polled IS NULL), 0) AS pending FROM sources WHERE lane = 'opps'").fetchone()
    failing = [dict(row) for row in conn.execute(
        "SELECT name, last_error AS error, fails FROM sources WHERE lane = 'opps' AND enabled = 1 AND last_error IS NOT NULL "
        "ORDER BY fails DESC, name")]
    return {**dict(counts), "failing": failing}


def _deadline(conn, now: float, statuses: tuple[str, ...], zone: ZoneInfo) -> dict | None:
    """The nearest deadline ahead among opportunities of these statuses, with `when` («дедлайн 12 ноя (через 18 дней)»)."""
    row = conn.execute(
        f"SELECT story_id, title_ru, deadline, deadline_at, deadline_kind, starts, status FROM opportunities WHERE status IN "
        f"({','.join('?' * len(statuses))}) AND deadline_at > ? ORDER BY deadline_at LIMIT 1", (*statuses, now)).fetchone()
    return {**dict(row), "when": opps_delivery.when(dict(row), now, zone)} if row else None


def status() -> dict:
    """«Настройки» → «Состояние»: the sources and their health, what is open and tracked, the nearest deadlines, what
    the app shows (from board()), the LLM's spend, the last collection and whether the loop runs."""
    settings = config.load()
    tz = ZoneInfo(settings.timezone)
    now = time.time()
    with db.connect() as conn:
        counts = _sources(conn)
        open_count, tracked_count = conn.execute(
            "SELECT COALESCE(SUM(status IN ('open', 'tracked')), 0), COALESCE(SUM(status = 'tracked'), 0) "
            "FROM opportunities").fetchone()
        waiting = conn.execute(
            "SELECT COUNT(*) FROM stories s WHERE s.lane = 'opps' AND s.status != 'merged' AND NOT EXISTS "
            "(SELECT 1 FROM opportunities o WHERE o.story_id = s.id)").fetchone()[0]
        next_deadline, next_tracked = _deadline(conn, now, ("open", "tracked"), tz), _deadline(conn, now, ("tracked",), tz)
    today, month = llm.spent(settings)
    board = opps_delivery.board() if settings.opps_enabled else {}
    last = db.get_state("last_collect")
    tick = db.get_state("loop_tick")
    return {
        "enabled": settings.opps_enabled, "sources": counts, "open": open_count, "tracked": tracked_count,
        "unread": waiting,  # stories not read by the model yet: the backlog the budget leaves for later
        "next_deadline": next_deadline, "next_tracked": next_tracked,
        # what the app shows: in its list, of them new since the morning update, beyond the window; and when
        "shown": len(board.get("items", [])), "new": board.get("new", 0), "later": board.get("later", 0),
        "soon": len(board.get("soon", [])), "updated": board.get("updated"), "next_update": board.get("next"),
        "expected": [event["name"] for event in board.get("expected", [])],  # annual events not found yet
        "spend": {"today_rub": round(today, 2), "month_rub": round(month, 2), "budget_month_rub": settings.opps_budget_month_rub,
                  "daily_budget_rub": round(settings.opps_daily_budget_rub, 2)},
        "last_collect": {**last, "at": _local(last["at"], tz)} if last else None,
        "loop_alive": bool(tick and now - tick < 180),  # the loop marks every tick (a minute)
        "settings": settings.model_dump(),
    }


@app.get("/status")
async def get_status() -> dict:
    return status()


@app.get("/sources")
async def get_sources() -> list[dict]:
    return sources.listing()


class SourceRequest(BaseModel):
    text: str  # a Telegram channel (@name, t.me/name), a feed's address or a program's page


@app.post("/sources")
async def post_source(request: SourceRequest) -> dict:
    """Check and add a source (or switch an existing one back on); 422 with a message for the user when refused."""
    try:
        return await manage.add(request.text)
    except manage.SourceError as e:
        raise HTTPException(422, str(e)) from None


@app.get("/sources/find")
async def find_sources(q: str) -> list[dict]:
    """Sources matching a number, an address or a part of the name."""
    return manage.find(q)


@app.delete("/sources/{source_id}")
async def delete_source(source_id: int) -> dict:
    """Switch a source off (its posts stay in their stories)."""
    if found := manage.switch(source_id, False):
        return found
    raise HTTPException(404, "source not found")


@app.post("/sources/{source_id}/enable")
async def enable_source(source_id: int) -> dict:
    """Switch a source back on; it is polled at the next tick."""
    if found := manage.switch(source_id, True):
        return found
    raise HTTPException(404, "source not found")


@app.get("/items")
async def get_items(limit: int = 50) -> list[dict]:
    """The latest fresh posts, newest first."""
    return items.recent(limit)


@app.get("/stories")
async def get_stories(limit: int = 30, hours: int = 48) -> list[dict]:
    """Recent stories, the most independent sources first, each with its posts."""
    return dedup.stories(limit, hours)


@app.get("/opps")
async def get_opps(status: str = "", type: str = "", limit: int = 50) -> list[dict]:
    """Opportunities (open and tracked unless `status` lists others, comma-separated), the tracked first, then by how
    soon, then by fit; `type` one of config.OPP_TYPES. «Мои» reads `status=tracked,applied`."""
    return opps_delivery.dressed(opps_delivery.by_date(opps.listing(status or None, type or None, limit)))


@app.get("/opps/board")
async def get_board() -> dict:
    """«Возможности»: `soon` (tracked deadlines of the next two weeks), `items` (as /opps gives them, plus `new`), `new`,
    `later`, `updated`, `next`, `window_days`, `major_window_days`, `expected` (annual events not found yet: `key`,
    `name`, `opp_type`, `url`, `when`) (opps_delivery.board())."""
    return opps_delivery.board()


@app.post("/opps/run")
async def post_opps_run() -> dict:
    """Cut roundups and read the waiting opportunities now (LLM calls, within the budget)."""
    return await opps.run()


@app.post("/opps/update")
async def post_opps_update() -> dict:
    """The morning update now, as the loop makes it when it is due (checks)."""
    return opps_delivery.run()


@app.get("/opps/{story_id}")
async def get_opportunity(story_id: int) -> dict:
    """One opportunity; 404 when there is none."""
    if found := opps_delivery.opportunity(story_id):
        return found
    raise HTTPException(404, "opportunity not found")


class StatusRequest(BaseModel):
    status: str  # tracked | hidden | applied | open


@app.post("/opps/{story_id}/status")
async def post_opportunity_status(story_id: int, request: StatusRequest) -> dict:
    """The user's choice («В мои», «Не моё», «Регистрация есть», or back); 422 for another status, 404 when there is
    no such opportunity."""
    if request.status not in opps_delivery.STATUSES:
        raise HTTPException(422, "Статус — tracked, hidden, applied или open.")
    if found := opps_delivery.set_status(story_id, request.status):
        return found
    raise HTTPException(404, "opportunity not found")


@app.post("/collect")
async def post_collect(everything: bool = False) -> dict:
    """Poll the due sources now (every enabled one with everything=true); {"busy": true} while a poll runs."""
    return await loop.collect(everything)


@app.post("/dedup")
def post_dedup() -> dict:
    """Merge the waiting posts now (a plain def: FastAPI runs it in a thread, the embedding takes seconds)."""
    return dedup.run()


@app.get("/settings")
async def get_settings() -> dict:
    return {**config.load().model_dump(), "opp_type_names": config.OPP_TYPES, "weekday_names": config.WEEKDAYS,
            "custom_profile": config.is_set("opps_profile")}


@app.put("/settings")
async def put_settings(changes: dict) -> dict:
    """Changes some settings; 422 with a message for the user (in Russian) when a value is refused."""
    try:
        return config.update(changes).model_dump()
    except config.SettingsError as e:
        raise HTTPException(422, str(e)) from None


@app.get("/health")
async def health() -> dict:
    return {"ok": True}
