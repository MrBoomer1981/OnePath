---
name: check-project
description: Check the whole project before a commit — every module imports, the icon font has every icon, and the radar runs end to end for free (sources polled, posts merged, read by the mock LLM, the morning update), with the app's pages answering. Use before committing, after a change in any part.
---

# Whole-project check

A change in one part can break the other: at import (a renamed function), or only at run time (an API field the screens read, a setting). Run this before every commit; a push to `main` deploys to Railway. It costs nothing: the LLM is `dev/mock_llm.py`, the state goes to a throwaway directory, and the app gets its own port, so it does not meet another session's run or the user's own local app. The sources are real: the first tick polls all of them (about 100 s).

Work from any folder of the repository. Shell variables do not survive between commands, so note the paths and ports you pick.

## 1. Every module compiles and imports

```bash
R=$(git rev-parse --show-toplevel)
uv run python -m compileall -q "$R/my_browser" "$R/app.py" "$R/eval" "$R/dev" &&
REPORTS_DIR=$(mktemp -d) uv run python -c "import importlib, pkgutil, my_browser; [importlib.import_module(m.name) for m in pkgutil.walk_packages(my_browser.__path__, 'my_browser.') if not m.name.endswith('__main__')]; print('imports ok')" &&
uv run "$R/dev/icons.py" --check
```

The last line checks that the cut icon font (`static/fonts/icons.woff2`) has every icon the web app names; a missing one would show up on screen as its name. `uv run dev/icons.py` cuts it anew.

## 2. The radar end to end, free

Pick a throwaway directory `D` in your scratchpad and two free ports: the app's (from 8601 up) and the mock's (from 8765 up). Check a port with `lsof -ti :<port>`; another session may be running this check too. Start the mock and the app in the background:

```bash
R=$(git rev-parse --show-toplevel)
uv run "$R/dev/mock_llm.py" --port <mock> > "$D/mock.log" 2>&1 &
FAST_LLM=openai:mock SMART_LLM=openai:mock STRATEGIC_LLM=openai:mock OPENAI_API_KEY=mock \
OPENAI_BASE_URL=http://127.0.0.1:<mock>/v1 REPORTS_DIR="$D/reports" PORT=<port> PUBLIC=0 \
NEWS_MODELS_DIR=<a folder kept between checks> uv run "$R/app.py" > "$D/app.log" 2>&1 &
```

- `PUBLIC=0` keeps it on 127.0.0.1 without a password, whatever the port.
- The mock's address goes through environment variables, which beat `config.json`.
- `NEWS_MODELS_DIR`: the embedding model (220 MB) is downloaded once into that folder, not into every throwaway directory.

Then wait for the loop's first run (2–3 minutes) and read `app.log`. The check passes when:
- `Sources: 64 polled, N new posts, 0 failed` (a few failures are the sources' own; read which);
- `Opportunities: N posts merged into M stories`, then `Opportunities: … stories read: K open …` (the mock makes every fourth story «not an opportunity»), then `Opportunities: the app's list updated, J new` with J > 0 (a new database releases at once);
- the weekly web search ran: `Opportunities: web search, … queries` (without a local SearXNG every query fails, which is fine here: on Railway it is Tavily);
- every page answers 200: `for p in / /mine /settings /login; do curl -sL -o /dev/null -w "$p %{http_code}\n" "localhost:<port>$p"; done`;
- the board has items: `REPORTS_DIR="$D/reports" uv run python -c 'import asyncio; from my_browser.common.clients import call; b = asyncio.run(call("news", "GET", "/opps/board")).json(); print(len(b["items"]), b["new"], b["updated"])'`;
- `grep -c Traceback "$D/app.log"` is 0.

If a step fails, read the end of `app.log`.

## 3. Clean up

Stop what you started, by port: uv wraps Python, so killing the uv process leaves the server running.

```bash
lsof -t -i :<port> -i :<mock> | xargs kill
```

## Also, when the change calls for it

- **UI**: screenshots at 360 and 390 px wide with `uv run --with playwright`, driving the installed Chrome (`channel="chrome"`, headless): the three sections, an opportunity's sheet, «Источники» and «Профиль»; `document.documentElement.scrollWidth` must equal the width. Real data looks different from the mock's: copy a `news.sqlite` into a throwaway `REPORTS_DIR` and run with `NEWS_LOOP=0`.
- **The morning update, the window or «Скоро дедлайн»**: the simulated-clock check in `my_browser/news/CLAUDE.md` («When you change…»).
- **Reading quality**: `uv run eval/opps/run_extract.py`, about 1 ₽. Ask the user first.
- **Dependencies or the Dockerfile**: `docker build -t onepath-check .` (several minutes).
