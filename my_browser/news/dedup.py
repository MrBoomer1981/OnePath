"""Merging posts into stories: one opportunity announced by many sources becomes one story.

Every few minutes the loop takes the fresh posts without a story (roundups aside: opps.py cuts them first), embeds
them in a child process (embed.py) and, oldest first, puts each into the story it matches or opens a new one:
- a usable link (collectors.usable_key) shared with a post of an open story means the same story, as long as the
  two are not unrelated (LINK_FLOOR): a page that many posts link to would otherwise pull them all together;
- otherwise by meaning, and only posts of different owners: the open story whose first post and closest post are both
  as close as OPPS_THRESHOLD. Announcements are written to a template («Открыта регистрация на хакатон…», Devpost's
  facts): on 25.10.2026 aggregators' reposts of one announcement were 0.86-1.00 apart, while unrelated posts reached
  0.79, and 69 of Devpost's hackathons had become one story under the looser rules DEEper's AI news merge by. A
  retelling in other words (0.74) is left to the model's same_as (opps.py). Posts of one owner merge only by a link.
- A new version of a watched page joins the story of its previous one. A link a source puts under most of its posts
  (its chat, its community) merges nothing (_boilerplate()): ODS Events linked its Mattermost from 9 posts, which
  would have made them one story.
An opportunity lives for weeks: a post waits to be merged for items.OPPS_FRESH_DAYS, and a story stays open
OPPS_OPEN_DAYS after its last post, or as long as its opportunity is open, so a hackathon announced again a month
later joins its first announcement. When the model cannot run (not downloaded, out of memory), posts are merged by
shared links only and stored without an embedding, so the reading goes on. A story counts its independent sources
(distinct owners).
"""

import json
import logging
import time
from collections import Counter

import numpy as np

from my_browser.news import db, embed, items
from my_browser.news.collectors import host, link_key, usable_key

logger = logging.getLogger(__name__)

BATCH = 400  # posts embedded per run; the first run after a deploy takes the window's backlog
LINK_FLOOR = 0.35  # the least similarity for a merge by a shared link; true pairs in DEEper's eval had 0.48 and more
OPPS_OPEN_DAYS = 60
OPPS_THRESHOLD = 0.85
BOILERPLATE_POSTS = 4
# A part of a roundup (opps.split) without a link of its own carries the roundup's address: not its identity, so
# the parts of one roundup do not merge by it.
OWN_URL = ("CASE WHEN i.copied_from IS NOT NULL AND i.url = (SELECT p.url FROM items p WHERE p.id = i.copied_from "
           "AND p.digest = 1) THEN NULL ELSE i.url END AS url")
# A story is open while it got a post within OPPS_OPEN_DAYS or its opportunity is open; never once it expired.
OPEN_STORIES = ("(s.last_updated > ? OR s.id IN (SELECT story_id FROM opportunities WHERE status IN ('open', 'tracked', "
                "'applied'))) AND s.id NOT IN (SELECT story_id FROM opportunities WHERE status = 'expired')")


def _owner(row: dict) -> str:
    """Whose a post is, for merging: its source's owner; a page the web search found (discover.py) is its site's, so
    pages of one opportunity on different sites merge by meaning like posts of different sources."""
    return f"site:{host(row['url'])}" if row.get("kind") == "search" and row.get("url") else row["owner"]


def _keys(url: str, links: str | None) -> set[str]:
    return {k for k in {link_key(url) if url else ""} | set(json.loads(links or "[]")) if k and usable_key(k)}


def _boilerplate(rows: list[dict]) -> set[str]:
    """Links a source puts under its posts: in BOILERPLATE_POSTS or more of one source's posts and no other owner's."""
    per_source, owners_of = Counter(), {}
    for row in rows:
        for key in _keys(row["url"], row["links"]):
            per_source[(row["source_id"], key)] += 1
            owners_of.setdefault(key, set()).add(row["owner"])
    return {key for (_, key), n in per_source.items() if n >= BOILERPLATE_POSTS and len(owners_of[key]) == 1}


def run() -> dict:
    """Merge the waiting posts; returns how many posts were placed, how many stories they touched and opened."""
    now = time.time()
    with db.connect() as conn:
        waiting = [dict(row) for row in conn.execute(
            f"SELECT i.id, i.title, i.text, {OWN_URL}, i.links, i.source_id, i.copied_from, s.owner, s.kind FROM items i "
            "JOIN sources s ON s.id = i.source_id "
            "WHERE i.story_id IS NULL AND i.lane = 'opps' AND i.backfill = 0 AND i.digest = 0 AND i.text IS NOT NULL "
            "AND i.published > ? ORDER BY i.published LIMIT ?", (now - items.OPPS_FRESH_DAYS * 86400, BATCH))]
        if not waiting:
            return {"posts": 0, "stories": 0, "new": 0}
        placed = [dict(row) for row in conn.execute(
            f"SELECT i.story_id, {OWN_URL}, i.links, i.embedding, i.source_id, i.copied_from, src.owner, src.kind FROM items i "
            "JOIN stories s ON s.id = i.story_id "
            f"JOIN sources src ON src.id = i.source_id WHERE s.lane = 'opps' AND {OPEN_STORIES} AND i.embedding IS NOT NULL "
            "ORDER BY i.published", [now - OPPS_OPEN_DAYS * 86400])]
    for row in waiting + placed:
        row["owner"] = _owner(row)
    try:
        vectors = embed.vectors([embed.text(p["title"], p["text"]) for p in waiting])
    except Exception as e:
        logger.warning("Opportunities: embeddings unavailable (%s); merging by shared links only", str(e)[:300])
        vectors = None

    index_vectors = [np.frombuffer(p["embedding"], dtype=np.float32) for p in placed]
    index_story = [p["story_id"] for p in placed]
    seeds: dict[int, np.ndarray] = {}  # each story's first post
    owners: dict[int, set[str]] = {}
    for vector, story, p in zip(index_vectors, index_story, placed):
        seeds.setdefault(story, vector)
        owners.setdefault(story, set()).add(p["owner"])
    footer = _boilerplate(placed + waiting)
    key_story: dict[str, int] = {}
    source_story: dict[int, int] = {}  # each source's latest story: a watched page's next version joins it
    for p in placed:
        if p["copied_from"] is None:  # a page's own versions, not the parts of its list
            source_story[p["source_id"]] = p["story_id"]
        for key in _keys(p["url"], p["links"]) - footer:
            key_story.setdefault(key, p["story_id"])

    assignments: list[tuple[int, int | None, bytes]] = []  # (item, story or None for a new one, embedding)
    new_stories = 0
    for n, post in enumerate(waiting):
        vector = vectors[n] if vectors is not None else None
        similarity = np.vstack(index_vectors) @ vector if vector is not None and index_vectors else None
        version = post["kind"] == "page" and post["copied_from"] is None
        story = source_story.get(post["source_id"]) if version else None
        linked = Counter(key_story[k] for k in _keys(post["url"], post["links"]) - footer if k in key_story) \
            if story is None else {}
        nearest = {candidate: _nearest(similarity, index_story, candidate) for candidate in linked}
        # The most shared links first, then the closest: an order that does not hang on the hash seed of the process.
        for candidate in sorted(linked, key=lambda c: (-linked[c], -nearest[c], c)):
            if nearest[candidate] >= LINK_FLOOR:
                story = candidate
                break
        if story is None and similarity is not None:
            same_owner = {sid for sid, names in owners.items() if post["owner"] in names}
            story = _closest(similarity, index_story, seeds, vector, same_owner)
        if story is None:
            new_stories += 1
            story = -new_stories  # a placeholder until the story row exists
            if vector is not None:
                seeds[story] = vector
        owners.setdefault(story, set()).add(post["owner"])
        if post["copied_from"] is None:
            source_story[post["source_id"]] = story
        assignments.append((post["id"], story, vector.tobytes() if vector is not None else None))
        if vector is not None:
            index_vectors.append(vector)
            index_story.append(story)
        for key in _keys(post["url"], post["links"]) - footer:
            key_story.setdefault(key, story)

    with db.transaction() as conn:
        real: dict[int, int] = {}
        for _, story, _ in assignments:
            if story < 0 and story not in real:
                real[story] = conn.execute("INSERT INTO stories (lane, first_seen, last_updated) VALUES ('opps', ?, ?)",
                                           (now, now)).lastrowid
        touched = set()
        for item, story, vector in assignments:
            story = real.get(story, story)
            touched.add(story)
            conn.execute("UPDATE items SET story_id = ?, embedding = ? WHERE id = ?", (story, vector, item))
        for story in touched:
            refresh(conn, story)
    logger.info("Opportunities: %d posts merged into %d stories, %d of them new", len(assignments), len(touched), new_stories)
    return {"posts": len(assignments), "stories": len(touched), "new": new_stories}


def _nearest(similarity: np.ndarray | None, index_story: list[int], story: int) -> float:
    """A post's similarity to the closest post of a story; without embeddings a shared link is all there is."""
    if similarity is None:
        return LINK_FLOOR
    return max((float(s) for s, sid in zip(similarity, index_story) if sid == story), default=0.0)


def _closest(similarity: np.ndarray, index_story: list[int], seeds: dict, vector: np.ndarray,
             same_owner: set[int]) -> int | None:
    """The story a post joins by meaning: its closest post and its first post both from OPPS_THRESHOLD, and no post of
    the same owner in it yet; the closest such."""
    nearest: dict[int, float] = {}
    for score, story in zip(similarity, index_story):
        if score > nearest.get(story, -1.0):
            nearest[story] = float(score)
    best, best_score = None, 0.0
    for story, score in nearest.items():
        close = score >= OPPS_THRESHOLD and float(seeds[story] @ vector) >= OPPS_THRESHOLD and story not in same_owner
        if close and score > best_score:
            best, best_score = story, score
    return best


def refresh(conn, story: int) -> None:
    """A story's counts and its provisional title (the earliest post's) until the model writes the opportunity's."""
    rows = conn.execute(
        "SELECT i.title, i.published, i.seen, s.owner, s.is_primary FROM items i "
        "JOIN sources s ON s.id = i.source_id WHERE i.story_id = ?", (story,)).fetchall()
    best = min(rows, key=lambda r: r["published"])
    conn.execute(
        "UPDATE stories SET first_seen = ?, last_updated = ?, source_count = ?, title = ?, "
        "has_primary = MAX(?, primary_url IS NOT NULL) WHERE id = ?",  # a first-hand link the model found stays
        (min(r["published"] for r in rows), max(r["seen"] for r in rows), len({r["owner"] for r in rows}), best["title"],
         int(any(r["is_primary"] for r in rows)), story))


def stories(limit: int = 30, hours: int = 48) -> list[dict]:
    """Recent stories, the most independent sources first, with their posts."""
    since = time.time() - hours * 3600
    with db.connect() as conn:
        rows = [dict(row) for row in conn.execute(
            "SELECT * FROM stories WHERE lane = 'opps' AND last_updated > ? AND status != 'merged' "
            "ORDER BY source_count DESC, last_updated DESC LIMIT ?",
            (since, limit))]
        for story in rows:
            story["posts"] = [dict(p) for p in conn.execute(
                "SELECT i.title, i.url, i.published, s.name AS source, s.owner, s.is_primary FROM items i "
                "JOIN sources s ON s.id = i.source_id WHERE i.story_id = ? ORDER BY s.is_primary DESC, i.published",
                (story["id"],))]
    return rows
