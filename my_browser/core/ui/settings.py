"""«Настройки» (/settings): what DEEper's Telegram bot set for the radar, and how the radar is doing.

- «Профиль»: the text each opportunity's fit is read against (the radar's `opps_profile`; DEEper's /profile). A new
  one has the open opportunities read again within the budget (news/config.update()).
- «Что показывать»: the types the list shows (all are read; DEEper's /opptypes).
- «Поиск по вебу»: the weekly search for what the sources missed, on or off.
- «Источники»: the sources with their health, a new one added (a channel, a feed or a program's page; DEEper's
  /add opps), one switched off or back on (/remove).
- «Состояние»: when the list was updated and will be, the sources' health, the model's spend this month and what
  waits to be read (DEEper's /news).
- «Граффити» (per browser) and «Выйти».
All but the graffiti live in the radar (its settings table), through its API; the page fetches them before it is
built (tabs.page), and again each time the section is shown.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from nicegui import app, ui

from my_browser.common.clients import call
from my_browser.common.text import plural, rub_text
from my_browser.core.ui import kit

MONTHS = ("январе", "феврале", "марте", "апреле", "мае", "июне", "июле", "августе", "сентябре", "октябре", "ноябре",
          "декабре")


async def load() -> dict:
    """The radar's settings, status and sources; parts missing when it does not answer."""
    data = {}
    for key, path in (("settings", "/settings"), ("status", "/status"), ("sources", "/sources")):
        try:
            data[key] = (await call("news", "GET", path, timeout=10)).json()
        except Exception:
            data[key] = None
    return data


async def _put(changes: dict) -> str | None:
    """Store settings in the radar; None when done, else the message to show (the radar's own on a refused value)."""
    try:
        await call("news", "PUT", "/settings", json=changes, timeout=10)
        return None
    except Exception as e:
        response = getattr(e, "response", None)
        if response is not None and response.status_code == 422:
            return response.json().get("detail") or "Не подходит"
        return "Не получилось: радар не отвечает"


def logout() -> None:
    app.storage.user.clear()
    ui.navigate.to("/login")


def _source_note(source: dict) -> str:
    if not source["enabled"]:
        return "выключен"
    if source.get("last_error"):
        return f"ошибка: {source['last_error']}"
    if source.get("silent_days"):
        return f"молчит {source['silent_days']} {plural(source['silent_days'], 'день', 'дня', 'дней')}"
    if source.get("polled") is None:
        return "ещё не опрошен"
    week = source.get("week") or 0
    return f"{week} {plural(week, 'пост', 'поста', 'постов')} за неделю"


def settings_screen(first: dict | None = None):
    """The section «Настройки» of the tab bar's page (tabs.py); returns what to call when it is shown again."""
    state = {"data": first or {}}

    async def reload() -> None:
        state["data"] = await load()
        rows.refresh()
        status_view.refresh()

    def profile_sheet() -> None:
        settings = state["data"].get("settings") or {}
        dialog, body = kit.sheet("Профиль")

        async def save() -> None:
            if error := await _put({"opps_profile": text.value.strip()}):
                kit.toast(error, "error")
                return
            dialog.close()
            kit.toast("Профиль сохранён: открытые возможности перечитаю по нему за день-два", "ok")
            await reload()

        with body:
            ui.label("По нему модель решает, что тебе подходит: учёба, интересы, цели, что подходит и что нет. "
                     "Контакты и ссылки в запросы не уходят.").classes("sub-text")
            text = ui.textarea(value=settings.get("opps_profile", "")) \
                .props('borderless dense dark autogrow input-style="max-height: 40vh; line-height: 1.45"').classes("field")
            kit.primary("Сохранить", save)
        dialog.open()

    def types_sheet() -> None:
        settings = state["data"].get("settings") or {}
        names = settings.get("opp_type_names") or {}
        chosen = list(settings.get("opps_types") or [])
        dialog, body = kit.sheet("Что показывать")

        async def toggle(key: str, on: bool) -> None:
            types = [t for t in names if (t in chosen or t == key) and not (t == key and not on)]
            if error := await _put({"opps_types": types}):
                kit.toast(error, "error")
                return
            chosen[:] = types
            await reload()

        with body:
            ui.label("Модель читает все типы; в списке — только отмеченные. Твои «Мои» видны всегда.").classes("sub-text")
            with ui.element("div").classes("list"):
                for key, name in names.items():
                    with ui.element("div").classes("li compact"):
                        ui.label(name).classes("li-title lines-2")
                        ui.switch(value=key in chosen, on_change=lambda e, key=key: toggle(key, e.value)) \
                            .props(f'dense color=bordo keep-color aria-label="{name}"')
        dialog.open()

    def sources_sheet() -> None:
        dialog, body = kit.sheet("Источники")

        async def add() -> None:
            text = new.value.strip()
            if not text:
                return
            try:
                source = (await call("news", "POST", "/sources", json={"text": text}, timeout=60)).json()
            except Exception as e:
                response = getattr(e, "response", None)
                kit.toast(response.json().get("detail") if response is not None and response.status_code == 422
                          else "Не получилось: радар не отвечает", "error")
                return
            new.value = ""
            kit.toast(f"Добавлен: {source['name']}", "ok")
            await reload()
            listing.refresh()

        async def switch(source: dict) -> None:
            path = f"/sources/{source['id']}" + ("" if source["enabled"] else "/enable")
            try:
                await call("news", "DELETE" if source["enabled"] else "POST", path, timeout=10)
            except Exception:
                kit.toast("Не получилось: радар не отвечает", "error")
                return
            await reload()
            listing.refresh()

        @ui.refreshable
        def listing() -> None:
            found = state["data"].get("sources") or []
            groups = (("С ошибкой", [s for s in found if s["enabled"] and s.get("last_error")]),
                      ("Молчат", [s for s in found if s["enabled"] and not s.get("last_error") and s.get("silent_days")]),
                      ("Работают", [s for s in found if s["enabled"] and not s.get("last_error") and not s.get("silent_days")]),
                      ("Выключены", [s for s in found if not s["enabled"]]))
            for label, group in groups:
                if not group:
                    continue
                ui.label(f"{label} · {len(group)}").classes("sheet-label")
                with ui.element("div").classes("list"):
                    for source in group:
                        with ui.element("div").classes("li compact"):
                            with ui.element("div").classes("li-text"):
                                ui.label(source["name"]).classes("li-title lines-1")
                                ui.label(_source_note(source)).classes("li-sub lines-1")
                            if source["enabled"]:
                                kit.icon_button("close", f"Выключить {source['name']}", lambda s=source: switch(s))
                            else:
                                kit.icon_button("add", f"Включить {source['name']}", lambda s=source: switch(s))

        with body:
            ui.label("Канал Telegram (@name), RSS-лента или страница программы: проверю и буду читать.").classes("sub-text")
            with ui.element("div").classes("pill inline"):
                new = ui.input(placeholder="@channel или https://…").props("borderless dark dense").classes("pill-input mono") \
                    .on("keydown.enter", add)
                kit.icon_button("add", "Добавить", add).classes("send")
            listing()
        dialog.open()

    def set_graffiti(on: bool) -> None:
        kit.save_prefs(graffiti=on)
        ui.query("body").classes(remove="graffiti-off") if on else ui.query("body").classes("graffiti-off")

    async def set_search(on: bool) -> None:
        if error := await _put({"opps_search": on}):
            kit.toast(error, "error")
        await reload()

    @ui.refreshable
    def rows() -> None:
        data = state["data"]
        settings, found = data.get("settings") or {}, data.get("sources") or []
        names = settings.get("opp_type_names") or {}
        types = settings.get("opps_types") or []
        working = [s for s in found if s["enabled"]]
        trouble = sum(1 for s in working if s.get("last_error"))
        with ui.element("div").classes("list"):
            kit.row("Профиль", "по нему модель оценивает, что тебе подходит",
                    value="свой" if settings.get("custom_profile") else "общий", chevron=True, on_click=profile_sheet)
            kit.row("Что показывать", value="все" if len(types) == len(names) else f"{len(types)} из {len(names)}",
                    chevron=True, on_click=types_sheet)
            kit.row("Источники", f"{trouble} с ошибкой" if trouble else "", value=str(len(working)), chevron=True,
                    on_click=sources_sheet)
            with ui.element("div").classes("li"):
                with ui.element("div").classes("li-text"):
                    ui.label("Поиск по вебу").classes("li-title")
                    ui.label("раз в неделю ищет то, что пропустили источники").classes("li-sub")
                ui.switch(value=bool(settings.get("opps_search", True)), on_change=lambda e: set_search(e.value)) \
                    .props('dense color=bordo keep-color aria-label="Поиск по вебу"')
            with ui.element("div").classes("li"):
                with ui.element("div").classes("li-text"):
                    ui.label("Граффити").classes("li-title")
                    ui.label("маркерные росчерки и надписи").classes("li-sub")
                ui.switch(value=kit.prefs()["graffiti"], on_change=lambda e: set_graffiti(e.value)) \
                    .props('dense color=bordo keep-color aria-label="Граффити"')
            if kit.AUTH:
                kit.row("Выйти", on_click=logout)

    @ui.refreshable
    def status_view() -> None:
        status = state["data"].get("status")
        if not status:
            return
        spend, sources = status["spend"], status["sources"]
        month = MONTHS[datetime.now(ZoneInfo(status["settings"]["timezone"])).month - 1]
        ui.label("Состояние").classes("sheet-label")
        with ui.element("div").classes("list"):
            if status.get("updated"):
                kit.row(f"Список обновлён {status['updated']}", f"следующее обновление — {status['next_update']}")
            kit.row(f"Источники: {sources['ok']} из {sources['enabled']} работают", "; ".join(filter(None, (
                f"с ошибкой: {len(sources['failing'])}" if sources["failing"] else "",
                f"ждут первого опроса: {sources['pending']}" if sources["pending"] else ""))))
            kit.row(f"Модель: {rub_text(spend['month_rub'])} из {rub_text(spend['budget_month_rub'])} в {month}",
                    f"сегодня {rub_text(spend['today_rub'])} · ждут чтения: {status['unread']}")
            if not status.get("loop_alive"):
                kit.row("Радар стоит", "его цикл не отвечает уже несколько минут")

    with kit.screen():
        with ui.element("div").classes("title-row"):  # no marker: «Настройки» alone fills a 360 px screen
            ui.label("Настройки").classes("h1")
        rows()
        status_view()

    return reload
