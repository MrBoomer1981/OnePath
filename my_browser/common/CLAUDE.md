# CLAUDE.md: common

`my_browser/common/` is the code both parts share, so a change here changes core and the radar at once. This file covers what lives here, who relies on what, and how to check a change. The repository's rules are in the root CLAUDE.md. Paths below are relative to `my_browser/` unless they are repo-root files. Most of it is DEEper's `common/` without what only the research used (report sections, phases, page fetching).

## What lives here

- `settings.py`:
  - paths: `ROOT`, `CONFIG_PATH`, `REPORTS_DIR` (the app's state; the name is DEEper's);
  - `WEB_RETRIEVER`: the engine of the radar's weekly web search (`news/discover.py`): `tavily` when `TAVILY_API_KEY` is set and `SEARX_URL` is not (Railway), else `searx`;
  - `RESEARCH_URL`: DEEper's address, for «Исследовать» on an opportunity (`core/ui/kit.research_url()`); empty, the button is not shown. A Railway variable, never in the repository;
  - how the parts find each other: `PORT`, `CORE_URL`, `NEWS_URL`, `service_token()`;
  - `configure_logging()`, which quiets httpx: the loop polls dozens of sources.
- `clients.py`: `call("news", method, path)`, in-process or over HTTP (see the root CLAUDE.md).
- `auth.py`: `require_token`, the service token check of the radar's API.
- `costs.py` meters real cost.
  - It wraps `GenericLLMProvider.get_chat_response` and adds usage tokens to the `Meter` in the `costs.current` ContextVar; `costs.metered()` gives each of the radar's calls its own (`news/llm.py`), whose rubles go into `opps_spend`.
  - DeepSeek prices (peak 01–04 and 06–10 UTC on weekdays, half price otherwise) and the CBR USD/RUB rate (cached 12 h; `USD_RUB` overrides).
  - `finish_reason == "length"` is logged and counted as `truncated_calls`.
- `text.py`: `rub_text` («0,87 ₽», with a no-break space) and `plural` (Russian word forms).
- `memory.py`: hands freed memory back to the system after heavy work. `trim()` calls glibc's `malloc_trim(0)` (a no-op without glibc, so on macOS); `release()` collects cyclic garbage first. On Railway DEEper's process climbed to about 1 GB within hours of a deploy and stayed there: glibc keeps freed pages. On Linux, threads that read page-sized texts and dropped them left a process at 1.2 GB, and `malloc_trim(0)` brought it to 15 MB.

## Run and check

Nothing here runs on its own. Check a change through the parts: the `check-project` skill imports every module and runs the radar end to end, and its pages. Adding a function, a constant or an optional argument is safe. Renaming or removing one, or changing what it returns, changes every part that uses it: update them in the same commit.

## Who relies on what

- **`settings.py`**: both parts and `eval/`. Values are computed at import: `.env` is loaded, but real environment variables win; eval sets its own `REPORTS_DIR` before importing anything from `my_browser`. Each entry point calls `configure_logging()`. `PORT` also makes core public (`core/ui/kit.PUBLIC`, unless `PUBLIC=0`).
- **`clients.py`**: core's screens (`core/ui/opps.py`, `settings.py`) and the checks. `call()` raises on 4xx and 5xx, and callers rely on it: «Настройки» shows a 422's `detail` as the radar wrote it. An in-process call imports the radar's API module into the caller's process, with all its dependencies. It opens a new client per call; a shared one would bind to the first event loop.
- **`auth.py`**: the radar's API checks a bearer service token: `SERVICE_TOKEN`, or else the `REPORTS_DIR/.service_token` file. Processes on different machines, or with different `REPORTS_DIR`, need `SERVICE_TOKEN`.
- **`costs.py`**: `news/llm.py` and `eval/opps`. Importing it patches `GenericLLMProvider.get_chat_response` in that process. `PRICES` is keyed by model name; a model missing from it is counted in `unpriced_calls`, not in rubles.
- **`text.py`**: `plural` in the radar's captions and core's screens, `rub_text` in «Настройки».
- **`memory.py`**: the radar's loop, after each collection (`trim()`) and each merging and reading run (`release()`).
