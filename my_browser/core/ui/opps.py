"""«Возможности» and «Мои» (/ and /mine, sections of the tab bar's page, tabs.py): the radar's opportunities.

- «Возможности»: first «Скоро дедлайн», the user's own (tracked) whose deadline is at most two weeks away, in place
  of DEEper's reminders in Telegram (OnePath has no bot); then the open ones as the morning update gives them
  (`/opps/board`): due within three months, an especially big one within six, «Новые» (this morning's) first, «Ждём»
  (big annual events not found yet), then the rest by how soon, with a filter by type, when the list was updated, and
  how many lie further ahead. Each with its caption as the radar writes it (`meta`: no colored marks, the brandbook
  has no green or red), why it fits, and an arrow to where to apply. A row opens its sheet: what the radar knows of it
  (`details`), where to apply, «В мои», «Регистрация есть», «Исследовать» (DEEper's search screen with it as a topic,
  when RESEARCH_URL is set) and «Не моё».
- «Мои»: the ones the user took: «Регистрации ещё нет» (tracked), «Регистрация есть» (applied), and the ones whose
  event is behind under «Прошли». The circle before a row marks the registration in one tap.
Both come from the radar's API (in-process unless NEWS_URL is set): the page fetches them before it is built
(tabs.page), so they are there at the first paint; a status set in one section redraws both.
"""

from nicegui import ui

from my_browser.common.clients import call
from my_browser.common.text import plural
from my_browser.core.ui import kit

MINE_LIMIT = 200
PAST_SHOWN = 10  # «Мои» → «Прошли»: the latest ones
TOGGLE = "no-caps rounded unelevated dense color=night text-color=paper toggle-color=bordo toggle-text-color=paper"
DONE = {"tracked": "Добавлено в «Мои»", "applied": "Отмечено: регистрация есть", "open": "Убрано из «Моих»",
        "hidden": "Скрыто: больше не покажу"}


async def board() -> dict:
    """The radar's list as its morning update left it (`/opps/board`: soon, items, new, later, updated, next,
    expected); the user's own are in mine(). Empty when it does not answer."""
    try:
        return (await call("news", "GET", "/opps/board", timeout=10)).json()
    except Exception:
        return {}


async def mine() -> list[dict]:
    """The user's own opportunities: tracked (no registration yet) and applied; empty when the radar does not answer."""
    try:
        return (await call("news", "GET", "/opps", params={"status": "tracked,applied", "limit": MINE_LIMIT}, timeout=10)).json()
    except Exception:
        return []


async def set_status(story_id: int, status: str) -> bool:
    """The user's choice (tracked, applied, open, hidden); False when it did not go through."""
    try:
        await call("news", "POST", f"/opps/{story_id}/status", json={"status": status}, timeout=10)
        return True
    except Exception:
        return False


def _title(opp: dict) -> str:
    return opp["title_ru"] or opp["title"] or ""


def _opp_row(opp: dict, on_open, on_mark=None) -> None:
    """An opportunity in a list: a tap opens its sheet, the arrow where to apply; in «Мои» the circle before it
    marks the registration (on_mark). A recent move of its deadline is its note."""
    title = _title(opp)
    with ui.element("div").classes("li news-row"):
        if on_mark:
            registered = opp["status"] == "applied"
            with ui.element("button").classes("mark" + (" on" if registered else "")) as mark:
                ui.icon("check")
            mark.props.update({"type": "button", "aria-pressed": "true" if registered else "false",
                               "aria-label": f"Регистрация есть: {title}"})
            mark.on("click", lambda: on_mark(opp))
        with ui.element("div").classes("li-text").props('role="button" tabindex="0"') as text:
            ui.label(title).classes("li-title lines-3")
            ui.label(opp["meta"]).classes("li-sub")
            note = opp.get("moved") or (f"Почему тебе: {opp['fit_reason']}" if opp.get("fit_reason") else opp.get("summary_ru"))
            if note:
                ui.label(note).classes("li-note")
        text.on("click", lambda: on_open(opp))
        if opp.get("apply"):
            with ui.link(target=opp["apply"], new_tab=True).classes("li-src").props('aria-label="Подача"'):
                ui.icon("open_in_new")


def _opp_sheet(opp: dict, act) -> None:
    """One opportunity: what the radar knows of it, where to apply, and the user's choices (act(opp, status))."""
    dialog, body = kit.sheet()
    title, status = _title(opp), opp["status"]

    async def choose(new_status: str) -> None:
        dialog.close()
        await act(opp, new_status)

    with body:
        ui.label(opp["meta"]).classes("li-sub")
        ui.label(title).classes("opp-title")
        if opp.get("summary_ru"):
            ui.label(opp["summary_ru"]).classes("opp-text")
        if opp.get("fit_reason"):
            ui.label(f"Почему тебе: {opp['fit_reason']}").classes("opp-why")
        if opp.get("apply"):  # a real link: a new tab opened from the server would be a blocked pop-up on a phone
            with ui.link(target=opp["apply"], new_tab=True).classes("link-btn"):
                ui.label("Страница подачи")
                ui.icon("open_in_new")
        with ui.element("div").classes("opp-actions"):  # above the facts: reachable without scrolling the sheet
            if status == "open":
                kit.secondary("В мои", lambda: choose("tracked"))
            if status == "applied":
                kit.secondary("Регистрации нет", lambda: choose("tracked"))
            else:
                kit.secondary("Регистрация есть", lambda: choose("applied"))
        with ui.element("div").classes("opp-facts"):
            for label, text in opp.get("details") or []:
                ui.label(label).classes("opp-key")
                ui.label(text).classes("opp-value")
        with ui.element("div").classes("opp-more"):
            if research := kit.research_url(f"{title}: условия участия, отбор и как подготовиться"):
                ui.link("Исследовать", research, new_tab=True).classes("more-link")
            if status in ("tracked", "applied"):
                _text_button("Убрать из «Моих»", lambda: choose("open"))
            if status != "applied":
                _text_button("Не моё", lambda: choose("hidden"))
    dialog.open()


def _text_button(text: str, on_click) -> None:
    with ui.element("button").classes("more-link").props('type="button"') as button:
        ui.label(text)
    button.on("click", on_click)


def _opps_view(board: dict, kind: str, on_kind, on_open) -> None:
    """«Скоро дедлайн», then the morning update's list: when it was made, the type filter, «Новые», the rest, and how
    many lie further."""
    _group("Скоро дедлайн", board.get("soon") or [], on_open)
    items = board.get("items") or []
    if not items:
        with ui.element("div").classes("empty"):
            kit.mascot("sleep", 170)
            ui.label("Новых возможностей пока нет. Список обновляется каждое утро"
                     + (f", следующий раз — {board['next']}." if board.get("next") else ".")).classes("sub-text")
        _awaited(board)
        _later(board)
        return
    if board.get("updated"):  # when the next one comes is said by the empty list: one line on a phone
        ui.label(f"обновлено {board['updated']}").classes("li-sub")
    counts: dict[str, list] = {}
    for item in items:
        counts.setdefault(item["opp_type"], [item.get("type_short") or item["type_name"], 0])[1] += 1
    options = {"": f"все {len(items)}", **{key: f"{name} {n}" for key, (name, n) in sorted(counts.items(), key=lambda kv: -kv[1][1])}}
    ui.toggle(options, value=kind if kind in options else "", on_change=lambda e: on_kind(e.value or "")) \
        .props(TOGGLE).classes("seg wrap")
    shown = [item for item in items if not kind or item["opp_type"] == kind]
    _group("Новые", [i for i in shown if i.get("new")], on_open)
    _awaited(board, kind)  # right after the new ones: a big event not found yet is a miss to notice
    _group("Открытые", [i for i in shown if not i.get("new")], on_open)
    _later(board)


def _group(label: str, items: list[dict], on_open) -> None:
    if items:
        ui.label(f"{label} · {len(items)}").classes("sheet-label")
        with ui.element("div").classes("list"):
            for item in items:
                _opp_row(item, on_open)


def _awaited(board: dict, kind: str = "") -> None:
    """Big annual events whose registration usually opens by now and which the radar has not found yet (of the type
    filtered, if any): a tap opens DEEper's search with the event as a topic (else its official page), the arrow its
    official page."""
    events = [e for e in board.get("expected") or [] if not kind or e["opp_type"] == kind]
    if not events:
        return
    ui.label(f"Ждём · {len(events)}").classes("sheet-label")
    with ui.element("div").classes("list"):
        for event in events:
            with ui.element("div").classes("li news-row"):
                target = kit.research_url(f"{event['name']}: сроки регистрации и условия участия") or event.get("url")
                with (ui.link(target=target, new_tab=True) if target else ui.element("div")).classes("li-text"):
                    ui.label(event["name"]).classes("li-title lines-3")
                    ui.label(f"{event['when']} · ещё не нашли").classes("li-sub")
                if event.get("url"):
                    with ui.link(target=event["url"], new_tab=True).classes("li-src").props('aria-label="Официальная страница"'):
                        ui.icon("open_in_new")


def _later(board: dict) -> None:
    """How many open ones are due beyond the window: they come into the list when their date draws near."""
    if later := board.get("later"):
        months = round(board.get("window_days", 92) / 30.4)
        ui.label(f"Ещё {later} — со сроком дальше {months} {plural(months, 'месяца', 'месяцев', 'месяцев')}: "
                 f"{plural(later, 'появится', 'появятся', 'появятся')} здесь, когда срок приблизится.").classes("sub-text")


def _event_day(opp: dict) -> str:
    return opp.get("starts") or ""


def _mine_view(items: list[dict], on_open, on_mark) -> None:
    if not items:
        with ui.element("div").classes("empty"):
            kit.mascot("sleep", 170)
            ui.label("Здесь будут возможности, которые ты выберешь: открой любую во «Возможностях» и нажми «В мои». "
                     "Зарегистрируешься — отметь кружком. За две недели до дедлайна она появится наверху "
                     "«Возможностей».").classes("sub-text")
        return
    current = [i for i in items if not i["over"]]
    past = sorted((i for i in items if i["over"]), key=lambda i: i.get("ends") or _event_day(i), reverse=True)
    groups = (("Регистрации ещё нет", [i for i in current if i["status"] == "tracked"]),  # by deadline, as /opps gives them
              ("Регистрация есть", sorted((i for i in current if i["status"] == "applied"),
                                          key=lambda i: (not _event_day(i), _event_day(i)))),
              ("Прошли", past[:PAST_SHOWN]))
    for label, group in groups:
        if group:
            ui.label(f"{label} · {len(group)}").classes("sheet-label")
            with ui.element("div").classes("list"):
                for item in group:
                    _opp_row(item, on_open, on_mark)


def sections(first_board: dict | None = None, own: list[dict] | None = None) -> dict:
    """The builders of «Возможности» and «Мои» for the tab bar's page (tabs.py), sharing their state: each builds its
    section and returns what to call when it is shown again."""
    state = {"kind": "", "board": first_board or {}, "mine": own or []}
    shown: dict[str, list] = {"board": [], "mine": []}

    def opps_key(items: list[dict]) -> list:
        return [(o["story_id"], o["status"], o["meta"], o.get("new"), o.get("moved")) for o in items]

    def board_key(board: dict) -> list:
        return [board.get("updated"), board.get("later"), [e["name"] for e in board.get("expected") or []],
                opps_key(board.get("soon") or []), *opps_key(board.get("items") or [])]

    async def act(opp: dict, status: str) -> None:
        """A status chosen in a sheet or with a circle: the radar stores it, both sections are drawn anew."""
        if not await set_status(opp["story_id"], status):
            kit.toast("Не получилось: радар не отвечает", "error")
            return
        kit.toast("Отметка снята" if (opp["status"], status) == ("applied", "tracked") else DONE[status])
        await refresh(force=True)

    def open_sheet(opp: dict) -> None:
        _opp_sheet(opp, act)

    async def mark(opp: dict) -> None:
        await act(opp, "tracked" if opp["status"] == "applied" else "applied")

    def pick_kind(kind: str) -> None:
        state["kind"] = kind
        opps_view.refresh()

    @ui.refreshable
    def opps_view() -> None:
        shown["board"] = board_key(state["board"])
        _opps_view(state["board"], state["kind"], pick_kind, open_sheet)

    @ui.refreshable
    def mine_view() -> None:
        shown["mine"] = opps_key(state["mine"])
        _mine_view(state["mine"], open_sheet, mark)

    async def refresh(force: bool = False) -> None:
        """Both sections fetched again and redrawn only when something changed, so the lists do not blink."""
        new_board, new_mine = await board(), await mine()
        if force or board_key(new_board) != shown["board"]:
            state["board"] = new_board
            opps_view.refresh()
        if force or opps_key(new_mine) != shown["mine"]:
            state["mine"] = new_mine
            mine_view.refresh()

    def build_opps():
        with kit.screen():
            with ui.element("div").classes("title-row"):
                ui.label("Возможности").classes("h1")
                kit.graffiti("cross", "title-cross")
            opps_view()
        return refresh

    def build_mine():
        with kit.screen():
            with ui.element("div").classes("title-row"):
                ui.label("Мои").classes("h1")
                kit.marker("MY PATH", "title-marker")
            mine_view()
        return refresh

    return {"opps": build_opps, "mine": build_mine}
