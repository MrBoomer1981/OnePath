# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

OnePath is a personal research app: after a search it writes a report for 5–7 minutes of reading (the default overview, `quick`; detailed and deep reports on request), and the follow-ups after it are the main way on: they start in one tap, know what the reader already read in the branch, and a branch's first report may lay out a route of next steps. It uses the `gpt-researcher` pip library for orchestration, a local SearXNG (or Tavily on Railway) plus arXiv/OpenAlex for search, and DeepSeek as the LLM (Flash for search and planning, V4 Pro writes the text by default). The user writes in Russian; reports default to Russian. It is a web app opened by a link (installable on the phone), with no Telegram bot. The roadmap is `plan.md` (Russian, checkboxes), open work only.

**Where it comes from.** OnePath is the research half of DEEper (github.com/MrBoomer1981/DEEper, the same user's), split off on 27.10.2026 at the user's request: the same search, overview, follow-ups, library and «Фокус», without DEEper's news radar, its opportunities lane and its Telegram bot. DEEper still has the same research code (the user chose to keep it there until OnePath is checked), so a fix made in one may be wanted in the other: say so to the user. `HANDOFF.md` (Russian) tells what was done at the split, what the user does next and which questions are open; read it first in a new session. The Python package is still `my_browser` and the prompt family `deeper`: renaming them is a later chore, not a bug.

## Commands

```bash
docker compose up -d                       # local SearXNG on 127.0.0.1:8080 (needs SEARXNG_SECRET in .env; .env.example lists every variable)
uv run app.py                              # everything in one process: web UI + API at 127.0.0.1:8501 and the job loop
uv run python -m my_browser.core           # or each part on its own: core (web UI + API, PORT=8501),
uv run python -m my_browser.worker         #   worker (API on WORKER_PORT=8502 + job loop), search (SEARCH_PORT=8503);
uv run python -m my_browser.search         #   set WORKER_URL / SEARCH_URL / CORE_URL so they find each other
uv run research.py "тема"                  # one research without any server -> reports/ (the 5–7 minute overview by default)
uv run research.py "тема" --mode deep --sources all --words 2500
uv run research.py "тема" --mode detailed --no-factcheck   # a long report without the fact-check (on by default in every mode)
uv run dev/mock_llm.py                     # a fake OpenAI-compatible LLM on :8765 for free end-to-end runs; point any command at it:
FAST_LLM=openai:mock SMART_LLM=openai:mock STRATEGIC_LLM=openai:mock OPENAI_API_KEY=mock \
  OPENAI_BASE_URL=http://127.0.0.1:8765/v1 uv run research.py "тема" --mode quick
uv add --group worker <pkg>                # uv, Python 3.12: shared deps in [project], each part's in its dependency group
uv run eval/run.py                         # quality measurement on eval/topics.txt -> eval/results/ (≈10 ₽); see eval/CLAUDE.md
uv run dev/icons.py                        # after the web app names a new icon: cuts static/fonts/icons.woff2 anew (--check only checks)
```

The commands work from any folder of the repository: uv finds the project upward, `my_browser` is installed into the environment as an editable package, and `docker compose` finds its file upward too. Root scripts take a path from elsewhere (`uv run ../../research.py` from a part's folder). Don't name a module after a stdlib one (core's job queue is `jobs.py`, not `queue.py`): `python -m` and `python -c` put the current folder first on `sys.path`, so a `queue.py` there shadowed the stdlib's and core did not start from its own folder.

Outputs land in `reports/` as `<date>_<time>_<slug>.{md,docx,pdf,json}`; the `.json` holds query, mode, writer, cost, duration, word count, source URLs, the fact-check, follow-ups and parent. `<name>.qa.json` (questions) and `<name>.short.md` (the short version) appear next to a report later. `reports/library.sqlite` numbers the reports, indexes them for search and holds the job queue; the report tables are rebuilt from the files (`Library.sync()` on start), the queue cannot be. The same directory keeps the rest of the app's state: `read_stats.json` (search), `blocked_domains.txt`, `bookmarks.json`, `.service_token`, `.storage_secret` and `.nicegui/` (logins and «Фокус» settings). The `REPORTS_DIR` env var moves all of that elsewhere; it is read when `my_browser.common.settings` is imported.

There is deliberately no test suite while the project is in active development (the user's call). Verify with throwaway runs: the `check-project` skill (`.claude/skills/`, `/check-project`) imports everything and runs one research end to end for free, with `dev/mock_llm.py` as the LLM; measure search and writing changes with `eval/run.py`. Web UI E2E: `uv run --with playwright` driving the installed Chrome (`channel="chrome"`, headless) against the app, at 360 and 390 px wide first, since the user mostly opens the app on the phone. `uv run` wraps the Python process, so to stop a server or simulate a crash kill the process listening on the port, not uv.

## Architecture: three parts

`my_browser/` has one package per part plus `common/`. The parts talk over HTTP with a shared service token (`SERVICE_TOKEN`, else `REPORTS_DIR/.service_token`; `common/auth.py`), so each can be improved and restarted alone:

| Part | Package | Owns | Talks to |
|---|---|---|---|
| core | `core/` | web UI (NiceGUI), API under `/api`, report library, job queue, blocklist | worker (questions, follow-ups, clarification, short versions) |
| worker | `worker/` | the research engine (gpt-researcher + our patches), LLM helpers, DOCX/PDF | core (jobs), search (sources, pages) |
| search | `search/` | source selection (`/select`) and page reading with fallbacks (`/read`), read stats | — |

Each of these folders, and `common/`, `eval/` and `proxy/`, has its own CLAUDE.md. It says what the folder does, how to run and check it alone, what other parts rely on (API fields, files, phase and log lines, gpt-researcher internals), and what else to update when one side changes. Read it before changing the folder; a session started in the folder loads it by itself. They came from DEEper and were cut to OnePath on 27.10.2026; a mention of DEEper's bot or news there is history, not code.

- `common/clients.py`: `call(part, method, path)`. Core is always reached at `CORE_URL` (default `http://127.0.0.1:PORT`). Worker and search are reached at `WORKER_URL` / `SEARCH_URL`, or, when unset, in-process through their FastAPI apps (`httpx.ASGITransport`): the same requests without a network hop. A client is opened per call because every research runs in its own event loop.
- All-in-one (`app.py`, also what Railway runs): one process, one port. NiceGUI serves core's pages and `/api` (`app.py` imports NiceGUI only through `core.web`, which first points NiceGUI's login storage at the volume); `start_parts()` starts the worker's job loop in a thread; worker and search are called in-process; the job loop calls core over localhost.
- A research's way through the parts:
  - The web page calls `core/service.submit()` directly (an API client would post `/api/jobs`); the job waits in the `jobs` table of `library.sqlite`.
  - The worker's job loop (`worker/runner.py`, one research at a time, in a thread) claims it at `/api/worker/claim`, together with the blocklist, and runs `pipeline.research()`. A job that continues a report comes with what the reader already read (`branch`: the nearest reports' key points), the route its branch follows and the reader's interests from «Фокус» (`core/service.claim()`): the writer starts from what is new, and the follow-ups do not repeat the branch. A follow-up started by one tap waits 5 s (`not_before`) for «Отменить». gpt-researcher searches; each batch of results goes to search's `/select`, and each page is read through search's `/read`.
  - Then come the fact-check (when the job has it), the follow-ups and `pipeline.render()`. The md, json, docx and pdf go back base64 to `/api/worker/jobs/{id}/result`, and `Library.store()` writes them into `REPORTS_DIR`.
  - All along, `/api/worker/jobs/{id}/progress` carries a phase line from `common/phases.py` and, while the report is written, its text so far (`draft`, `worker/draft.py`), which the job page shows; it is sent when it changes and at least every 30 s. It is also the heartbeat: a job silent for 5 minutes, or one left running by a worker that has since restarted (its hello at start), becomes interrupted and can be restarted.
- The research engine is gpt-researcher 0.16.1 (locked in `uv.lock`), patched at import:
  - `quick` is its `research_report` and `deep` its recursive `deep` report. `detailed` is `worker/detailed.py`, our port of upstream's `detailed_report`, which the pip package does not ship.
  - `worker/hooks.py` hands source selection and page reading to search and paces arXiv and SearXNG. `worker/prompts.py` registers the `deeper` prompt family: English-first queries, length caps, citation rules. `worker/stemming.py` makes the keyword ranking Russian-aware, and `common/costs.py` meters every LLM call.
  - `pipeline.research()` imports these modules; code that runs gpt-researcher another way must import them itself. `worker/CLAUDE.md` lists every upstream internal they touch: re-check it after an upgrade, for both the worker and search.
- Configuration: `config.json` holds gpt-researcher's settings (models, retrievers, prompt family, language, words, deep mode's breadth and depth).
  - Each research writes a temporary copy with its own sources, writer, words and language (`pipeline.run_settings()`, `config_file()`); the fact-check uses that copy too.
  - Q&A, short versions, follow-ups, clarification and search's rating read `config.json` itself through `Config(CONFIG_PATH)`, so the writer toggle does not reach them.
  - An environment variable or a `.env` line beats both, the writer toggle included. That is how the mock LLM takes over a run.
- Shared code in `common/` (details in its CLAUDE.md): `settings.py` (paths, `SOURCES`/`WRITERS`/`MODES`, URLs, token, logging), `clients.py`, `auth.py`, `costs.py` (the real cost in rubles), `text.py`, `report.py` (the sections appended to a report), `phases.py` (the worker's progress lines, which core parses), `gptr.py` (upstream's unpatched page fetch, for search), `memory.py` (freed memory handed back after a research).
- Dependencies: `[project]` holds what every part needs (httpx, python-dotenv), dependency groups `core`/`worker`/`search` hold the rest, and `tool.uv.default-groups` installs all of them (the Dockerfile's `uv sync --no-dev` too); an image for one part would use `uv sync --no-default-groups --group <part>`.
- Other folders: `eval/` measures quality, `dev/` holds the mock LLM (it still answers DEEper's news prompts too; harmless) and the icon-font cutter, `proxy/` is the Cloudflare Worker for access from Russia, `static/` the web app's assets, fonts and icons, `searxng/` the local SearXNG's settings.

## Working in one part

The user may start separate Claude Code sessions in one folder (`my_browser/core`, `worker`, `search`, `common`, or `eval`, `proxy`), sometimes several at once in this same checkout. A session started in a folder loads this file and the folder's CLAUDE.md. Through the folder's `.claude/settings.json` it reads the whole repository without prompts.

- **Where to edit.** Change files outside your folder only when your change needs it: the other side of a contract you change, in the same commit; your item in `plan.md`; your part's lines in this file and in `README.md`. Name those files in your report to the user.
- **Contracts.** Keep them compatible: add fields and endpoints rather than rename or remove them. Reports already on the volume keep their old shape. Your folder's «When you change…» table lists who else reads what you change.
- **`common/`** changes every part at once. Adding to it is fine. Before changing what existing code there does, check every user listed in `common/CLAUDE.md`.
- **Dependencies** go into your part's group: `uv add --group <part> <package>`.
  - gpt-researcher, fastapi and uvicorn sit in both the worker and the search groups, so upgrade them for both parts and run the whole check.
  - Never point `--no-default-groups` or `--group` at the shared `.venv`. Syncing it to one group uninstalls the other parts' packages under every running session. Check a single group in a throwaway environment: `UV_PROJECT_ENVIRONMENT=<scratch>/venv-<part> uv run --no-default-groups --group <part> …`.
- **Other sessions** may have uncommitted work in this checkout.
  - Stage and commit only your own files, by path: `git add <paths>`, `git commit -m "…" -- <paths>`.
  - Never run `git add -A`, `git commit -a`, `git stash`, `git checkout` or `git restore` on files that are not yours, `git reset --hard` or `git clean`: they take or destroy someone else's work.
- **Local runs.**
  - Use a throwaway `REPORTS_DIR` (in your scratchpad) and your own ports: `PORT=86xx PUBLIC=0`, `WORKER_PORT`, `SEARCH_PORT`. Ports 8501–8503 and 8765 may be someone else's (DEEper's local runs use the same defaults).
  - Run one `eval/run.py` at a time: runs share `eval/reports/`.
  - SearXNG is shared too (with DEEper's local runs), and parallel researches use up its engines' rate limits together.
  - Real runs spend the user's money on DeepSeek (DEEper and OnePath share about 300 ₽ a month for models and services): a quick Flash report ≈1 ₽, an overview on Pro with the fact-check ≈2,5 ₽, a detailed Pro one ≈11–12 ₽, twice that at DeepSeek's peak (01–04 and 06–10 UTC on weekdays). Checks use the mock LLM, and `eval/run.py` waits for the user's yes.
- **Before committing**, run the `check-project` skill.
- **Pushing.** A push to `main` deploys to Railway at once (see Deployment).
  - If the new code fails to start, the app is down: with the volume, the old deployment has already stopped.
  - Revert rather than fix forward: `git revert <sha>`, then push.
  - Deploy results: `railway logs --deployment --lines N` from this folder (linked to the OnePath project), or the deployment's status in the dashboard.

## Design (AVEN brandbook)

The UI and PDFs follow the user's brandbook (`aven-brandbook.pdf`, kept locally and gitignored because the repo is public; it lies in DEEper's folder, copy it here when needed).
- Dark only. Background is night `#14100E`, text is paper `#F2EBE1` (never `#FFF`), bordo `#7A2A35` is used only for fills such as buttons, selected toggles and 3/3 badges (never as text on dark), and amber `#E8A24A` is the single accent per screen (one label, the timer, the tab underline, link underlines).
- There is no fifth color and no blue, green, neon or gradients, apart from the brand's own subtle bordo glow.
- The mobile redesign follows `DESIGN_HANDOFF.md` (tokens, screens, the Дип-Диггер mascot in `static/mascot/`, the graffiti layer, stages and acceptance checklist). Its one exception to the rules here: the graffiti layer may be pure white `#FFFFFF`, as decoration (`aria-hidden`, no pointer events) that the user can switch off.
- Fonts are self-hosted in `static/fonts`: Unbounded only for 2–4 word headings, Onest for text (including long report titles), JetBrains Mono for labels, chips, numbers and URLs (all OFL); Permanent Marker (Apache 2.0, Latin only) and Amatic SC Bold (OFL, Cyrillic) only for graffiti. The web loads WOFF2 subsets (Latin, Cyrillic, punctuation; about 280 KB for all five against 1.4 MB of TTF), made with fontTools (`subset`, then for Unbounded `varLib.instancer` limiting `wght` to 700–900, the only weights the web uses) from the TTFs, which the PDF keeps using; regenerate the WOFF2 when a TTF changes. Icons come from `static/fonts/icons.woff2`, NiceGUI's Material Icons cut by `dev/icons.py` to the icons the code names (5 KB instead of 129 KB); a name missing from it shows as the word, so write icon names as literals and rerun the script when adding one.
- Styles and client scripts are `static/app.css` and `static/app.js`, linked with a content hash (`?v=`) so a deploy is never hidden by the browser cache.
- The app icon is still DEEper's «Корона + D» (`static/deeper-icon.svg`); the PNG icons (Dock/PWA/apple-touch/favicon, the favicon without the crown) are rendered from it with headless Chrome. OnePath's own icon is an open question (HANDOFF.md). The earlier black hole (`deeper-blackhole.svg`) and AVEN mark (`aven-mark.svg`) stay in the repo.
- Brand colors are registered as Quasar colors (`ui.colors(**BRAND_COLORS)`: `bordo`, `paper`, `amber`, `night`), so props like `color=bordo text-color=paper` work.
- WeasyPrint gotchas:
  - `@font-face` only works when a `FontConfiguration` is passed to both `CSS()` and `write_pdf()`.
  - `font-weight` ranges and non-100 steps such as 650 are rejected.

## Deployment

- GitHub: public repo `MrBoomer1981/OnePath` (created by the user on 26.10.2026; its first commit is the split from DEEper, without DEEper's history, which holds a leaked `.env`). Keep secrets, the user's profile and the app's addresses out of it: the addresses are in the local, gitignored `PRIVATE.md`.
- Railway: project «OnePath», one service built from this repo's `main` with the `Dockerfile` (it runs `app.py`, the Dockerfile's `CMD`), a volume at `/app/reports` (reports, the queue, logins), a `*.up.railway.app` domain. Variables: `DEEPSEEK_API_KEY`, `TAVILY_API_KEY` (web search: no SearXNG on Railway; the same key as DEEper's, so the free 1 000 requests a month are shared), `APP_PASSWORD` (the same as DEEper's); `PORT` comes from Railway and makes the app public, with the password. Settings in the dashboard are the user's to change; deploys come from pushes.
- Because of the volume, a redeploy stops the old deployment before the new one starts: a short downtime each time, and no fallback if the new one fails.
- From Russian networks Railway's address does not open without a VPN. The phone opens the app through `proxy/`, a Cloudflare Worker named `onepath` (its address is in `PRIVATE.md`); see `proxy/CLAUDE.md`. It does not open on mobile internet, where Russian providers let a connection to Cloudflare carry only its first ~16 KB. Behind the proxy the app must keep to relative redirects and links: an absolute URL built from the request's host names the Railway address. Per-IP logic (the login rate limit) sees a proxy's address, not the phone's.
- There is no SearXNG on Railway. `SOURCES["web"]` becomes `tavily` automatically when `TAVILY_API_KEY` is set and `SEARX_URL` is not; `WEB_RETRIEVER` overrides this.
- The container runs in UTC. PDFs need pango: the Dockerfile installs it, on macOS it is `brew install pango`. `worker/export.py` renders each PDF in a child process with `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`, because dyld reads that variable only at process start; on Linux WeasyPrint finds pango without it.
- Memory: DEEper's process sat near 1 GB on Railway with the news part in it; OnePath has no news loop and no embedding model, so it should need less (`railway metrics --since 12h` shows it; `common/memory.py` hands freed pages back after each research).
- Build the image locally with `docker build -t onepath-check .`. To test it against the host's SearXNG and mock LLM, use `host.docker.internal`.

## The user

Carried over from DEEper's sessions, since a session in this folder starts without their memory:
- Writes in Russian: answer in Russian, in plain words. Use gender-neutral wording about the user and everyone else (no gendered past tense: «вы выбрали», not «выбрал»).
- Opens the app mostly on the phone (an iPhone, installed from Safari): check every screen change at 360 and 390 px wide first.
- Wants a plan before a bigger change, then its implementation without asking again when the plan is solid; for a short fix request («убери…», «поправь…»), the likeliest reading done at once, naming the interpretation in one line. Asks to be asked only about costly, irreversible or budget-spending choices.
- No test suite for now (see Commands); verify with throwaway runs and the mock LLM.
- Before creating, pushing to or deleting a GitHub repository, confirm the target and its visibility, unless the user named them.
- Real DeepSeek spend only with the user's approval (the budget is shared with DEEper); routine pushes to `main` after the checks are fine.
- Railway's settings and region are the user's to change; the service runs where Railway put it (DEEper's is in Singapore, and a move to Europe would be faster from Russia: the user's call).
- The user's personal profile (studies, interests, goals) never goes into this public repository.

## Non-obvious behavior

- DeepSeek through gpt-researcher's `deepseek` provider (ChatOpenAI pointed at api.deepseek.com):
  - Thinking mode is disabled via `LLM_KWARGS.extra_body.thinking`; otherwise every call reasons, which makes it slower and more expensive.
  - langchain-openai sends `max_completion_tokens`, but DeepSeek reads only `max_tokens` (default 8K in non-thinking mode). That is why `max_tokens` is duplicated inside `extra_body`.
- Embeddings are intentionally not configured. With `CONTEXT_FILTER=keyword` and no `OPENAI_API_KEY`, gpt-researcher falls back to keyword ranking. If `OPENAI_API_KEY` is present in the environment, it silently switches to OpenAI embeddings (which is why the mock LLM answers `/embeddings`). Upstream's keyword filter is English-only; `worker/stemming.py` adds Russian morphology.
- Report-writing calls use `stream=True`. An OpenAI-compatible endpoint or mock without SSE streaming gets each call retried 10× with backoff, which looks like a hang.
- SearXNG (`searxng/settings.yml`) must keep the `json` format enabled. From this machine, only `google cse` and `yahoo` answer relevantly. bing returns off-topic junk for Cyrillic queries (Nickelodeon, Halloween stores, banks), and those pages also slow scraping. google, yandex, qwant, duckduckgo, brave and wikipedia return captcha or rate-limit errors. The `semantic_scholar` retriever gets 429 without a key and has no key support, so it is excluded from `--sources`.
- In quick and deep modes, gpt-researcher writes the references itself. Citation style varies between runs: sometimes inline markdown links, sometimes APA author-date with links only at the end.
- `GPTResearcher.get_costs()` prices unknown models at OpenAI defaults, so it is wrong for DeepSeek; don't use it. `common/costs.py` counts the tokens DeepSeek reports at its prices (half price off-peak), in rubles: the `cost` in each report's JSON. It misses calls that bypass `get_chat_response`, such as upstream's subtopic chain, so it runs slightly low; the DeepSeek dashboard has the exact spend.
