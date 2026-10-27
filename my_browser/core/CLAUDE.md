# CLAUDE.md: core

Core is OnePath's web app (NiceGUI): the opportunities the radar found, the user's own ones, and the radar's settings. It owns no data of its own besides logins: everything it shows and changes goes through the radar's API (`my_browser/news`). This file covers what core does, how to run and check it alone, and what it expects from the radar. The repository's rules are in the root CLAUDE.md. Paths below are relative to `my_browser/` unless they are repo-root files. It is DEEper's core without the research (search, reports, the job queue, the library) and with the opportunities' screens of DEEper's «Радар» as its sections.

## What core does

- `core/web.py` (NiceGUI 3) sets the app up and imports the screens:
  - the head (manifest, iPhone meta with the title «OnePath», font preloads, `app.css`/`app.js` and the icon font with a `?v=` content hash of all three, `asset_version()`);
  - static files with a 7-day cache;
  - auth: `AuthMiddleware` is active when it listens publicly (`kit.PUBLIC`: `PORT` is set, as on Railway, unless `PUBLIC=0`) or when `APP_PASSWORD` is set;
  - `NICEGUI_STORAGE_PATH` and the storage secret in `reports/` (the volume), so logins survive redeploys;
  - the icons: `static/fonts/icons.woff2`, NiceGUI's Material Icons cut by `dev/icons.py` to the icons the code names plus Quasar's own set (82 of 2 229, 4 KB, 27.10.2026). The head declares it as «DEEper Icons» (the name kept from DEEper) with its `?v=`, and app.css points Quasar's `.material-icons` at it. An icon is a ligature: a name the cut font lacks shows up as the word itself;
  - `ui.run(tailwind=False, reconnect_timeout=60)`: every screen is styled by `static/app.css`, and a phone that switched apps for a minute comes back to the same page.
- `core/ui/`: one module per screen, mobile first (`DESIGN_HANDOFF.md`), with a bottom tab bar «Возможности · Мои · Настройки» (icons `radar`, `bookmark_border`, `tune`).
  - `tabs.py`: the three sections are **one page**, registered at `/`, `/mine` and `/settings`. Each address builds all three with its own one shown; the page first fetches the radar's board, the user's own opportunities and «Настройки»'s data (`WAIT_SEC`, 1.5 s, else the sections fill when shown).
    - app.js switches sections in the browser (`SECTIONS`): at once, with an entrance animation, keeping the address (`history.pushState`), «Назад» and each section's scroll position. A tap on the current section scrolls it to the top.
    - Showing a section again sends `tab_shown`; its `on_show` fetches anew and redraws only what changed, so lists do not blink.
  - `opps.py`: «Возможности» (`/`) and «Мои» (`/mine`), built by `sections()`, which share their state: a status set in one redraws both.
    - «Возможности»: the radar's list as its morning update left it (`GET /opps/board`). On top «Скоро дедлайн · N» (`soon`: the user's tracked opportunities whose deadline is at most two weeks away; in place of DEEper's reminders in Telegram, the user's choice on 27.10.2026). Then «обновлено сегодня в 08:00», a filter by type (`seg wrap`), «Новые · N» (this morning's), «Ждём · N» (`_awaited()`: big annual events whose registration usually opens by now and which the radar has not found, `expected`; a tap opens DEEper's search with the event as a topic when `RESEARCH_URL` is set, else its official page; the arrow its official page; the filter applies to them too), «Открытые · N», and under them how many lie beyond the window (`_later()`); an empty list says when the next update comes. The arrow of a row opens where to apply; the row opens the opportunity's sheet (`_opp_sheet()`): the caption, what it is, why it fits, «Страница подачи» (a real link: a new tab opened from the server is a blocked pop-up on a phone), «В мои» / «Регистрация есть» above the facts (`details`, label and text as the radar writes them), then «Исследовать» (DEEper's search screen with it as a quick research topic, `kit.research_url()`; not shown without `RESEARCH_URL`), «Убрать из «Моих»», «Не моё».
    - «Мои»: the user's own (`GET /opps?status=tracked,applied`): «Регистрации ещё нет», «Регистрация есть», and those whose event is behind (`over`) under «Прошли» (the latest `PAST_SHOWN`). The circle before a row (`.mark`, bordo when on) switches tracked ↔ applied in one tap.
    - A row's note is its moved deadline when the radar says one (`moved`: «Дедлайн перенесён: 15 ноя → 29 ноя»), else why it fits, else its summary.
    - Every choice goes to `POST /opps/{id}/status`; both sections are then fetched and redrawn.
  - `settings.py`: «Настройки» (`/settings`), what DEEper's Telegram bot set for the radar: «Профиль» (a sheet with the profile's text; a new one has the open opportunities read again, which the toast says), «Что показывать» (a switch per type), «Источники» (a sheet: a field to add a channel, a feed or a program's page, and the sources grouped «С ошибкой», «Молчат», «Работают», «Выключены», each switched off or on with its button), «Поиск по вебу» (on or off), «Граффити» (per browser, `kit.prefs()`), «Выйти»; under them «Состояние» (when the list was updated and will be, the sources' health, the model's spend this month and what waits to be read, and a warning when the loop has not ticked for three minutes). A refused value shows the radar's own message (422 `detail`).
  - `kit.py`: what the screens share: the shell with the tab bar (`NAV`, `TAB_TITLES`), bottom sheets, list rows, buttons, the mascot, the graffiti layer, `research_url()`, and the page's own settings per browser (`prefs()`: only the graffiti now).
  - `login.py` `/login`: the logo «One**Path**» under the crown, one shared password, rate-limited per IP.

## Run and check it alone

```bash
uv run python -m my_browser.core     # core alone: the web app at 127.0.0.1:8501 (PORT); the radar at NEWS_URL
uv run ../../app.py                  # core with the radar's loop in one process, as on Railway
```

- **Screens and flows.** Run the all-in-one app as the `check-project` skill does: a throwaway `REPORTS_DIR`, `PORT=86xx PUBLIC=0`. Without `PUBLIC=0`, any `PORT` makes the app public and sends every page to the login. For real data, copy a `news.sqlite` into the throwaway directory and run with `NEWS_LOOP=0`; `RESEARCH_URL=https://deeper.example` shows the «Исследовать» links.
- **Phone first.** Look at every screen change at 360 and 390 px wide first: playwright with the installed Chrome (`channel="chrome"`, headless). Check that nothing scrolls sideways (`document.documentElement.scrollWidth` equal to the width): «Настройки» with DEEper's marker «MY RULES» beside it was 19 px too wide at 360 (27.10.2026).
- **The whole project.** Before committing, run the `check-project` skill.

## What core relies on

- **The radar's API**, through `common.clients.call("news", ...)`, in-process unless `NEWS_URL` is set; the fields are in `news/CLAUDE.md` («What core relies on»). An opportunity's caption (`meta`), its sheet's facts (`details`), the moved deadline (`moved`) and the filter's short type names (`type_short`) are written there, so the screens format nothing. When the radar does not answer, the sections show empty lists and a toast says so on a choice.
- **`common`**: `settings` (`RESEARCH_URL`, `PORT`, `REPORTS_DIR`, `ROOT`), `clients`, `text`. Core imports no module of the radar.

## State core owns

- `REPORTS_DIR/.storage_secret` and `.nicegui/` (logins, and each browser's graffiti switch in `app.storage.user["prefs"]`).

## Constraints

- `web.py` sets `NICEGUI_STORAGE_PATH` before importing NiceGUI, which reads the variable at import. Import NiceGUI only through `core.web` (as `app.py` does), and the screens in `core/ui/` likewise only from `web.py`; otherwise logins live outside the volume and every redeploy logs everyone out.
- **Motion and the phone** (`static/app.css`, `static/app.js`, DEEper's):
  - The sections switch in the page (`tabs.py`) and enter with a short rise (`screen-in`). Transform only `.screen` and the elements inside it, never an ancestor of a fixed element (the tab bar): a transformed ancestor becomes the containing block of `position: fixed`.
  - A tap answers at once: `:active` dims rows, tabs and icon buttons (iOS applies `:active` only because app.js listens to `touchstart`). While the next screen loads, `html.nav-pending` draws an amber line at the top.
  - A tab section is a flex item of NiceGUI's column, so `.tab-screen.on` keeps `width: 100%; min-width: 0`: without it, a long line widens the whole section past the phone's width.
- **iOS 26 home-screen app** (WebKit bug 301108): with `viewport-fit=cover` and the translucent status bar, a page shorter than the screen gets a viewport shorter by the status bar's height. `@media (display-mode: standalone) { html { min-height: min(100lvh, calc(100% + env(safe-area-inset-top))) } }` in app.css gets the full viewport; it cannot be reproduced in Chrome or Playwright's WebKit, only on an iPhone.
- **NiceGUI gives every element an `id`** (`c123`): never select by `[id]`.
- **Closed sheets stay in the page** until the user leaves it: deleting one re-renders its siblings.
- The graffiti fonts (Permanent Marker, Amatic SC) are `font-display: block`: in a fallback script font a marker word overlapped its neighbours until the font arrived.
- Styles live in `static/app.css`. Quasar puts its own `!important` color classes in a CSS cascade layer, which beats `!important` outside it, so give a component's color through props (`color=accent text-color=night`), as `ui/kit.primary()` does. Avoid class names Quasar already uses (`.row`, `.column`, `.col`…).
- `PORT` also switches on public mode: bind to 0.0.0.0 and require `APP_PASSWORD` (Railway sets `PORT`). `PUBLIC=0` keeps a local copy on another port private.
- No module here may take a stdlib module's name: started from this folder, `python -m` puts the folder first on `sys.path`.

## When you change…

| Change | Also update |
|---|---|
| what a section shows of an opportunity, or a status it sets | the fields come from `news/opps_delivery.board()`, `soon()` and `dressed()` and `news/opps.listing()`; the statuses are `news/opps_delivery.STATUSES`, so a new one starts in the radar |
| what «Настройки» changes | the setting must exist in `news/config.Settings` (with its `LABELS`); a source's routes are the radar's `/sources` |
| a section or its address | `kit.NAV` and `TAB_TITLES`, `tabs.SECTIONS` and its pages, `SECTIONS` in `static/app.js` |
| an icon the app did not show before, or a NiceGUI upgrade | `uv run dev/icons.py` cuts `static/fonts/icons.woff2` anew (the `check-project` skill runs `dev/icons.py --check`); write icon names as literals |
