"""«Радар» (/radar, a section of the tab bar's page, tabs.py): what to dig into next.

DEEper's «Радар» also had AI news and opportunities, from its news part; OnePath has only the research, so this
section lists the «Что исследовать дальше» topics of recent reports, minus the ones already researched: the newest
as the card, the rest as rows, each started in one tap like under a report.
"""

import json

from nicegui import ui

from my_browser.common.report import KINDS
from my_browser.core.library import Library
from my_browser.core.ui import kit


def feed(limit: int = 12) -> list[dict]:
    """Follow-up topics of the latest reports, newest report first, without the ones already continued."""
    library, topics, seen = Library(), [], set()
    for entry in library.recent(15):
        try:
            meta = json.loads(entry.base.with_suffix(".json").read_text("utf-8"))
        except (OSError, ValueError):
            continue
        done = {child.query.strip().lower() for child in library.children(entry)}
        for topic in meta.get("followups") or []:
            key = topic["query"].strip().lower()
            if key in seen or key in done:
                continue
            seen.add(key)
            topics.append({**topic, "report": entry})
    return topics[:limit]


def radar_screen():
    """The section «Радар» of the tab bar's page (tabs.py); returns what to call when it is shown again."""
    shown: dict[str, list] = {"topics": []}

    @ui.refreshable
    def topics_view() -> None:
        topics = feed()
        shown["topics"] = [t["query"] for t in topics]
        if not topics:
            with ui.element("div").classes("empty"):
                kit.mascot("sleep", 120)
                ui.label("Пока пусто. Здесь будут темы для исследований из твоих отчётов: что копнуть дальше.") \
                    .classes("sub-text")
            return
        top, rest = topics[0], topics[1:]
        with ui.element("div").classes("story-card"):
            ui.label(f"из отчёта #{top['report'].id} · {KINDS.get(top['kind'], top['kind']).lower()}").classes("story-label")
            ui.label(top["query"]).classes("story-title")
            if top.get("why"):
                ui.label(top["why"]).classes("story-why")
            kit.primary("Копнуть глубже", lambda: kit.start_followup(top["query"], top["report"].id))
        if rest:
            ui.label("Темы из твоих отчётов").classes("sheet-label")
            with ui.element("div").classes("list"):
                for t in rest:
                    kit.row(t["query"], kit.followup_sub(f"{KINDS.get(t['kind'], t['kind']).lower()} · отчёт #{t['report'].id}"),
                            on_click=lambda t=t: kit.start_followup(t["query"], t["report"].id), lines=3)

    with kit.screen():
        with ui.element("div").classes("title-row"):
            ui.label("Радар").classes("h1")
            kit.graffiti("cross", "title-cross")
        with ui.element("div").classes("radar-part"):
            topics_view()

    async def on_show() -> None:  # redrawn only when something changed, so the list does not blink
        if [t["query"] for t in feed()] != shown["topics"]:
            topics_view.refresh()

    return on_show
