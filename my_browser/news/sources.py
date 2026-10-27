"""Where the opportunities come from: the sources table and the starting list.

The list was checked in DEEper on 25.10.2026 (news/CLAUDE.md lists the ones refused) and grew on 26.10.2026:
aggregators of hackathons and competitions, companies' student programs, the university, research programs and
schools, conferences and grants; and on 27.10.2026 by lectures and events (a lecture hall, two venues). Pages without a feed (kind `page`) are read once a day. Sources the user adds in
«Настройки» go to the same table (manage.py).

Defaults are offered once: a source the user removed does not come back, and a source added to DEFAULTS later
reaches existing databases on the next start. Only sources of lane `opps` are polled, listed and managed: a database
brought over from DEEper keeps a few of its news sources switched off (db.py).
"""

import time
from dataclasses import dataclass

from my_browser.news import db

OPPS_INTERVALS = {"aggregator": 60, "company": 180, "university": 180, "program": 360, "conference": 360, "community": 60}
PAGE_INTERVAL = 1440  # a watched page: once a day
# Days without a new post after which a source counts as silent («Настройки» → «Источники» shows it): an
# aggregator posts every few days, a program's page may rightly stay the same for a season.
SILENT_DAYS = {"aggregator": 14, "page": 90}
SILENT_DAYS_OTHER = 45


@dataclass
class Source:
    name: str
    url: str
    category: str
    owner: str
    lang: str = "en"
    primary: bool = False
    ai_filter: bool = False  # DEEper's general news feeds: only posts about AI were kept
    kind: str = "rss"
    interval: int = 0  # 0: the category's interval
    lane: str = "opps"


def _opp(name, url, category, owner, kind="rss", **kw) -> Source:
    """A source; a page is read once a day, the rest by category (OPPS_INTERVALS)."""
    kw.setdefault("interval", PAGE_INTERVAL if kind == "page" else OPPS_INTERVALS[category])
    return Source(name, url, category, owner, kind=kind, lane="opps", **kw)


def _opp_tg(channel, title, category, owner="", **kw) -> Source:
    """A public channel read through t.me/s (collectors/telegram.py); several channels of one company share its owner."""
    return _opp(f"Telegram: {title}", channel, category, owner or f"tg:{channel}", kind="telegram", **{"lang": "ru", **kw})


DEFAULTS = [
    # Aggregators of hackathons and competitions, Russian and international.
    _opp_tg("hackathonsrus", "хакатоны.рус", "aggregator"),
    _opp_tg("hackathons", "Хакатоны || Hackathon list", "aggregator"),
    _opp_tg("codenrock", "Codenrock", "aggregator"),
    _opp_tg("changellenge", "Changellenge", "aggregator"),
    _opp_tg("datafest", "ODS Events", "community", owner="ods"),
    _opp("Хабр: хакатоны", "https://habr.com/ru/rss/hubs/hackathons/news/?fl=ru", "aggregator", "habr", lang="ru"),
    _opp("DirectLine: календарь хакатонов", "https://www.directline.pro/digital-events/it/hakatony/", "aggregator",
         "directline", kind="page", lang="ru"),
    _opp("Devpost: онлайн-хакатоны", "https://devpost.com/api/hackathons", "aggregator", "devpost", kind="devpost",
         interval=360),
    _opp("lablab.ai: хакатоны по ИИ", "https://lablab.ai/event", "aggregator", "lablab", kind="page"),
    _opp("Apart Research: спринты по AI safety", "https://apartresearch.com/sprints", "aggregator", "apart", kind="page"),
    _opp("DrivenData: соревнования", "https://www.drivendata.org/competitions/", "aggregator", "drivendata", kind="page"),
    _opp("AIcrowd: соревнования", "https://www.aicrowd.com/challenges", "aggregator", "aicrowd", kind="page"),
    # Programs, schools, fellowships and grants gathered by others.
    _opp("awesome-mlss: школы по ML", "https://raw.githubusercontent.com/awesome-mlss/awesome-mlss/master/site/_data/"
         "summerschools.yml", "aggregator", "awesome-mlss", kind="mlss", interval=720),
    _opp("AISafety.com: программы и обучение", "https://aisafety.com/newsletter/training/feed", "aggregator", "aisafety-com",
         interval=720),
    _opp("Opportunity Desk", "https://opportunitydesk.org/feed/", "aggregator", "opportunity-desk"),
    _opp("Opportunities for Youth", "https://opportunitiesforyouth.org/feed/", "aggregator", "opportunities-for-youth"),
    _opp("Scholars4Dev: стипендии", "https://www.scholars4dev.com/feed/", "aggregator", "scholars4dev", interval=720),
    _opp("WikiCFP: машинное обучение", "http://www.wikicfp.com/cfp/rss?cat=machine%20learning", "conference", "wikicfp"),
    _opp("WikiCFP: NLP", "http://www.wikicfp.com/cfp/rss?cat=NLP", "conference", "wikicfp"),
    # Companies' student programs: internships, schools, olympiads.
    _opp_tg("education_yandex", "Яндекс Образование", "company", owner="yandex"),
    _opp_tg("young_and_yandex", "Young&&Yandex", "company", owner="yandex"),
    _opp_tg("vse_v_shad", "Все в ШАД!", "company", owner="yandex"),
    _opp_tg("yandex_cup", "Yandex Cup", "company", owner="yandex"),
    _opp("Яндекс: стажировки", "https://yandex.ru/yaintern", "company", "yandex", kind="page", lang="ru"),
    _opp("ШАД: поступление", "https://shad.yandex.ru", "company", "yandex", kind="page", lang="ru"),
    _opp_tg("yaprofessional", "Олимпиада «Я — профессионал»", "program"),
    _opp_tg("tbank_education", "Т-Образование", "company", owner="tbank"),
    _opp_tg("sberstudent", "СберСтудент", "company", owner="sber"),
    _opp_tg("sberaiscience", "Sber AI", "company", owner="sber"),
    _opp_tg("vkeducation_about", "VK Education", "company", owner="vk"),
    _opp_tg("airi_research_institute", "Институт AIRI", "company", owner="airi"),
    _opp_tg("truetechcommunity", "МТС True Tech", "company", owner="mts"),
    _opp_tg("ozon_tech", "Ozon Tech", "company", owner="ozon"),
    _opp_tg("avitotech", "AvitoTech", "company", owner="avito"),
    _opp_tg("kaspersky_career", "Карьера в Kaspersky", "company", owner="kaspersky"),
    _opp_tg("case_in", "CASE-IN", "program"),
    # Universities and programs with admission.
    _opp_tg("itmoru", "Корень из ИТМО", "university", owner="itmo"),
    _opp_tg("itmo_students", "ITMO STUDENTS", "university", owner="itmo"),
    _opp_tg("aitalenthubnews", "AI Talent Hub", "university", owner="itmo"),
    _opp_tg("careercentreitmo", "Центр карьеры ИТМО", "university", owner="itmo"),
    _opp_tg("siyanie_itmo", "Сияние ИТМО", "university", owner="itmo"),  # the university's awards and scholarships
    _opp_tg("t_central_university", "Центральный университет", "university"),
    _opp_tg("deep_learning_school_news", "DLS — новости", "program"),
    _opp_tg("skoltech_smiles", "SMILES", "program"),
    # Research programs and schools (AI safety, ML), each its own owner.
    _opp("MATS", "https://www.matsprogram.org/apply", "program", "mats", kind="page"),
    _opp("SPAR", "https://sparai.org/", "program", "spar", kind="page"),
    _opp("ERA Fellowship", "https://erafellowship.org/", "program", "era", kind="page"),
    _opp("LASR Labs", "https://www.lasrlabs.org/", "program", "lasr", kind="page"),
    _opp("AI Safety Camp", "https://www.aisafety.camp/", "program", "ai-safety-camp", kind="page"),
    _opp("Constellation: Astra Fellowship", "https://www.constellation.org/programs/astra-fellowship", "program",
         "constellation", kind="page"),
    _opp("PIBBSS", "https://princint.ai/feed/", "program", "pibbss"),
    _opp("EEML: летняя школа", "https://www.eeml.eu/", "program", "eeml", kind="page"),
    _opp("M2L: летняя школа", "https://www.m2lschool.org/", "program", "m2l", kind="page"),
    _opp("ProbAI: летняя школа", "https://www.probabilistic.ai/", "program", "probai", kind="page"),
    _opp("Cooperative AI", "https://www.cooperativeai.com/", "program", "cooperative-ai", kind="page"),
    _opp("Outreachy: стажировки в open source", "https://www.outreachy.org/", "program", "outreachy", kind="page"),
    # Conferences, talks and grants.
    _opp_tg("dialog_21", "Dialogue Conference", "conference"),
    _opp_tg("scienceslamrussia", "Science Slam Russia", "community"),
    _opp_tg("fondpotanin", "Фонд Потанина", "program"),
    _opp_tg("rosmolodez", "Росмолодёжь", "program"),
    # Science and young scientists (26.10.2026, after the VI Congress of Young Scientists was found missing):
    # the Decade of Science's own channel announces the congress, the others conferences and grants.
    _opp_tg("npnauka", "Наука.рф", "program"),
    _opp_tg("confsci", "Научные конференции", "conference"),
    _opp_tg("rosmolodezgrants", "Росмолодёжь.Гранты", "program", owner="tg:rosmolodez"),
    _opp_tg("icpcnews", "ICPC News", "program", lang="en"),
    # Lectures, meetups and festivals (27.10.2026, the user's request: MedioModo's lectures were missing). A lecture
    # hall of several cities and two Petersburg venues; one offline in another city than the user's is not shown.
    _opp_tg("mediomodo", "Лекторий Medio Modo", "community"),
    _opp_tg("newhollandsp", "Новая Голландия", "community"),
    _opp_tg("planetarium1", "Планетарий 1", "community"),
]


def seed() -> int:
    """Add the defaults this database has not been offered yet; returns how many were added."""
    offered = set(db.get_state("offered_defaults", []))
    new = [s for s in DEFAULTS if s.url not in offered]
    if not new:
        return 0
    now = time.time()
    with db.transaction() as conn:
        for s in new:
            conn.execute(
                "INSERT OR IGNORE INTO sources (kind, url, name, lane, category, lang, owner, is_primary, ai_filter, interval, "
                "added) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (s.kind, s.url, s.name, s.lane, s.category, s.lang, s.owner, int(s.primary), int(s.ai_filter),
                 s.interval or OPPS_INTERVALS[s.category], now))
    db.set_state("offered_defaults", sorted(offered | {s.url for s in new}))
    return len(new)


def listing() -> list[dict]:
    """Every source with its health, how many fresh posts it gave in the last week and `silent_days` when an enabled
    one has been quiet longer than its kind usually is (SILENT_DAYS)."""
    now = time.time()
    with db.connect() as conn:
        rows = [{k: v for k, v in dict(row).items() if k != "page_text"} for row in conn.execute(  # a page's text stays here
            "SELECT s.*, (SELECT COUNT(*) FROM items i WHERE i.source_id = s.id AND i.backfill = 0 AND i.seen > ?) AS week, "
            "(SELECT MAX(i.seen) FROM items i WHERE i.source_id = s.id) AS last_post "
            "FROM sources s WHERE s.lane = 'opps' ORDER BY s.category, s.name", (now - 7 * 86400,))]
    for row in rows:
        row["silent_days"] = None
        if row["enabled"]:
            limit = SILENT_DAYS.get("page" if row["kind"] == "page" else row["category"], SILENT_DAYS_OTHER)
            quiet = (now - (row["last_post"] or row["added"] or now)) / 86400
            if quiet > limit:
                row["silent_days"] = int(quiet)
    return rows


def enabled() -> list[dict]:
    """Enabled sources to poll: the web search (kind `search`, discover.py) runs on its own schedule."""
    with db.connect() as conn:
        return [dict(row) for row in conn.execute("SELECT * FROM sources WHERE enabled = 1 AND lane = 'opps' AND kind != 'search'")]


def due(now: float | None = None) -> list[dict]:
    """Enabled sources whose interval has passed since their last poll. A failing source waits longer: twice its
    interval after one failure, four times after two, eight times after three or more."""
    now = now or time.time()
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT * FROM sources WHERE enabled = 1 AND lane = 'opps' AND kind != 'search' AND (polled IS NULL OR "
            "polled + interval * 60 * (CASE WHEN fails >= 3 THEN 8 WHEN fails = 2 THEN 4 WHEN fails = 1 THEN 2 ELSE 1 END) <= ?)",
            (now,)).fetchall()
    return [dict(row) for row in rows]


def mark_ok(source_id: int, etag: str | None = None, modified: str | None = None, page_hash: str | None = None,
            page_text: str | None = None) -> None:
    now = time.time()
    with db.transaction() as conn:
        conn.execute("UPDATE sources SET polled = ?, last_ok = ?, last_error = NULL, fails = 0, "
                     "etag = COALESCE(?, etag), modified = COALESCE(?, modified), page_hash = COALESCE(?, page_hash), "
                     "page_text = COALESCE(?, page_text) WHERE id = ?",
                     (now, now, etag, modified, page_hash, page_text, source_id))


def mark_failed(source_id: int, error: str) -> None:
    with db.transaction() as conn:
        conn.execute("UPDATE sources SET polled = ?, last_error = ?, fails = fails + 1 WHERE id = ?",
                     (time.time(), error[:300], source_id))
