"""The radar's LLM calls (DeepSeek Flash through gpt-researcher) and their budget, apart from what they ask.

Every call is metered (common/costs.py) into `opps_spend` by day in the settings' time zone; within_budget() stops the
calls at the day's limit (a tenth of `opps_budget_month_rub`, so the backlog after a deploy fits) or the month's. Each
call waits at most ASK_TIMEOUT_SEC and is asked once more: on 25.10.2026 a call through the Mac's VPN hung for 20
minutes, and the loop would have waited with it. The helpers for `same_as` (centroids(), same_as(), merge_into()) are
here too: the reading (opps.py) catches a story merging missed by naming an opportunity read before.

In DEEper this was the news lane's scoring module (news/scoring.py), which also scored the AI news.
"""

import asyncio
import logging
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import json_repair
import numpy as np

from my_browser.common import costs
from my_browser.common.settings import CONFIG_PATH
from my_browser.news import config, db, dedup

logger = logging.getLogger(__name__)

ASK_TIMEOUT_SEC = 300  # a call that hangs (a dropped connection) must not hold the loop for long


def _day(settings: config.Settings) -> str:
    return datetime.now(ZoneInfo(settings.timezone)).strftime("%Y-%m-%d")


def spent(settings: config.Settings) -> tuple[float, float]:
    """Rubles spent today and this month (days in the settings' time zone)."""
    day = _day(settings)
    with db.connect() as conn:
        today = conn.execute("SELECT COALESCE(SUM(rub), 0) FROM opps_spend WHERE day = ?", (day,)).fetchone()[0]
        month = conn.execute("SELECT COALESCE(SUM(rub), 0) FROM opps_spend WHERE day LIKE ?", (day[:7] + "%",)).fetchone()[0]
    return today, month


def within_budget(settings: config.Settings) -> bool:
    today, month = spent(settings)
    return today < settings.opps_daily_budget_rub and month < settings.opps_budget_month_rub


def _record(settings: config.Settings, rub: float) -> None:
    with db.transaction() as conn:
        conn.execute("INSERT INTO opps_spend (day, rub, calls) VALUES (?, ?, 1) ON CONFLICT (day) DO UPDATE SET "
                     "rub = rub + excluded.rub, calls = calls + 1", (_day(settings), rub))


async def ask(settings: config.Settings, prompt: str, max_tokens: int = 4000) -> list:
    """One metered call to the fast model; the JSON array of the answer, asked a second time when the first answer is
    broken."""
    from gpt_researcher.config import Config
    from gpt_researcher.utils.llm import create_chat_completion

    cfg = Config(str(CONFIG_PATH))
    for attempt in range(2):
        with costs.metered() as meter:
            try:
                answer = await asyncio.wait_for(create_chat_completion(
                    messages=[{"role": "user", "content": prompt}], model=cfg.fast_llm_model,
                    llm_provider=cfg.fast_llm_provider, temperature=0.2, max_tokens=max_tokens,
                    llm_kwargs=cfg.llm_kwargs), ASK_TIMEOUT_SEC)
            except asyncio.TimeoutError:
                answer = None
                logger.warning("LLM call timed out after %d s (attempt %d)", ASK_TIMEOUT_SEC, attempt + 1)
        _record(settings, meter.rub(fetch=True))
        match = re.search(r"\[.*\]", answer or "", re.S)
        data = json_repair.loads(match.group(0)) if match else None
        if isinstance(data, list) and data:
            return data
        logger.warning("LLM: unexpected answer (attempt %d): %r", attempt + 1, (answer or "")[:200])
    return []


def centroids(conn, story_ids: list[int]) -> dict[int, np.ndarray]:
    """Each story's mean post embedding, normalized (merging stored the posts' embeddings)."""
    if not story_ids:
        return {}
    marks = ",".join("?" * len(story_ids))
    sums: dict[int, np.ndarray] = {}
    for row in conn.execute(f"SELECT story_id, embedding FROM items WHERE story_id IN ({marks}) AND embedding IS NOT NULL",
                            story_ids):
        vector = np.frombuffer(row["embedding"], dtype=np.float32)
        sums[row["story_id"]] = sums.get(row["story_id"], 0) + vector
    return {sid: v / (np.linalg.norm(v) + 1e-9) for sid, v in sums.items()}


def same_as(value, refs: list[dict], targets: dict[int, int], number: int) -> int | None:
    """The story id the model's same_as names: one of the offered «S41», or an earlier story of the batch."""
    if isinstance(value, str) and value.upper().startswith("S") and value[1:].isdigit():
        story_id = int(value[1:])
        return story_id if any(r["id"] == story_id for r in refs) else None
    if isinstance(value, (int, str)) and str(value).isdigit() and int(value) < number:
        return targets.get(int(value))
    return None


def merge_into(conn, source: int, target: int) -> None:
    """Move a story's posts into another story about the same opportunity; the emptied one stays as «merged»."""
    conn.execute("UPDATE items SET story_id = ? WHERE story_id = ?", (target, source))
    conn.execute("UPDATE stories SET status = 'merged', drop_reason = ? WHERE id = ?", (f"тот же сюжет, что #{target}", source))
    dedup.refresh(conn, target)
