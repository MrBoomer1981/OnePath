# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

OnePath is the user's personal radar of opportunities with deadlines: hackathons, competitions, schools, internships, research programs, grants, conferences; and, since 27.10.2026, of events to come to, not always about studies (lectures, meetups, festivals: the user's request, after MedioModo's lectures were missing). It reads about 67 sources (public Telegram channels, feeds, programs' pages, Devpost, awesome-mlss, lecture halls and venues) and, once a week, the web; merges the posts about one opportunity into a story; has DeepSeek Flash read each story (is it an opportunity, its type, topic, region and city, deadline or date, conditions, access from Russia, how well it fits the user's profile); and shows the user, in a web app opened by direct link, what is due within three months (an especially big one within six), updated once a morning at 08:00, with filters by topic (ИИ, техническое, наука, прочее), area (the user's city, СНГ, мир) and type. There is no Telegram bot: everything, the deadlines of the user's own opportunities too, is in the app.

OnePath was split from DEEper (github.com/MrBoomer1981/DEEper, the user's research app with AI news) on 27.10.2026: DEEper's news part had grown a second lane, `opps`, and the user moved that «algorithm for finding opportunities» here; DEEper kept the news and the research. A first split the night before had copied DEEper's research instead, a misreading of the request («перенести часть с поиском»), replaced the next morning. The user writes in Russian; the app is in Russian. The roadmap is `plan.md` (Russian, checkboxes, open work only); `HANDOFF.md` tells how the split was made.

## Commands

```bash
uv run app.py                              # everything in one process: the web app at 127.0.0.1:8501 and the radar's loop
uv run python -m my_browser.core           # or each part on its own: core (the web app, PORT=8501),
uv run python -m my_browser.news           #   news (the radar: its API on NEWS_PORT=8504 + the loop); set NEWS_URL for core
uv run dev/mock_llm.py [--port N]          # a fake OpenAI-compatible LLM (default :8765) for free end-to-end runs; point any command at it:
FAST_LLM=openai:mock SMART_LLM=openai:mock STRATEGIC_LLM=openai:mock OPENAI_API_KEY=mock \
  OPENAI_BASE_URL=http://127.0.0.1:8765/v1 uv run app.py
uv run eval/opps/run_extract.py            # how well the model reads announcements, on labeled real posts (≈1.5 ₽;
                                           #   --only c02,c06 for a few cases)
uv run dev/icons.py                        # after the web app names a new icon: cuts static/fonts/icons.woff2 anew (--check only checks)
uv run --with playwright dev/app_icon.py   # after a change of static/icon.svg or favicon.svg: draws the app's icon PNGs
uv run dev/mascot.py                       # after a change of the mascot's drawing: writes static/mascot/hello.svg and sleep.svg
docker compose up -d                       # a local SearXNG on 127.0.0.1:8080 for the weekly web search (needs SEARXNG_SECRET in .env)
curl -X POST -H "Authorization: Bearer $(cat $REPORTS_DIR/.service_token)" http://127.0.0.1:$NEWS_PORT/opps/run
                                           # one step of the loop now, on a radar run as its own part: /collect, /dedup, /opps/run, /opps/update
```

The commands work from any folder of the repository: uv finds the project upward, and `my_browser` is installed into the environment as an editable package. Don't name a module after a stdlib one: `python -m` puts the current folder first on `sys.path`.

The app's state lives in `reports/` (the name kept from DEEper; `REPORTS_DIR` moves it, read when `my_browser.common.settings` is imported): `news.sqlite` (sources, posts, stories, opportunities, the settings, what the loop remembers, the LLM's spend), its daily copies in `backups/` (the last 7), `.models/` (the embedding model, 220 MB, downloaded at first use unless `NEWS_MODELS_DIR` points elsewhere), `.service_token`, `.storage_secret` and `.nicegui/` (logins).

There is deliberately no test suite (the user's call, as in DEEper). Verify with throwaway runs: the `check-project` skill (`.claude/skills/`, `/check-project`) imports everything and runs the radar end to end for free, with `dev/mock_llm.py` as the LLM. Web UI: `uv run --with playwright` driving the installed Chrome (`channel="chrome"`, headless), at 360 and 390 px wide first: the user opens the app on the phone. `uv run` wraps the Python process, so to stop a server kill the process listening on the port, not uv.

## Architecture: two parts

| Part | Package | Owns | Talks to |
|---|---|---|---|
| core | `core/` | the web app (NiceGUI): «Возможности», «Мои», «Настройки», login | news |
| news | `news/` | the radar: sources, posts, stories, opportunities, its settings (`news.sqlite`), the loop | — |

`my_browser/news` keeps DEEper's name, where the part read AI news as well: the same paths keep a fix portable between the two repositories (the collectors, merging, the Telegram selectors are the same code). Its tables still carry a `lane` column, `opps` on every row OnePath writes; a database brought over from DEEper keeps a few of its news sources switched off (`news/db.py`). Each of these folders, and `common/`, `eval/` and `proxy/`, has its own CLAUDE.md: what it does, how to run and check it alone, what the other part relies on. Read it before changing the folder.

- `common/clients.py`: `call("news", method, path)` reaches the radar's API at `NEWS_URL`, or, when unset, in-process through its FastAPI app (`httpx.ASGITransport`), behind the shared service token (`common/auth.py`).
- All-in-one (`app.py`, also what Railway runs): one process, one port. NiceGUI serves core's pages (`app.py` imports NiceGUI only through `core.web`, which first points NiceGUI's login storage at the volume); `start_parts()` starts the radar's loop in a thread (unless `NEWS_LOOP=0`).
- An opportunity's way:
  - The loop (`news/loop.py`, a thread ticking every minute) polls the due sources through `news/collectors/` into `items`, and once a week searches the web (`discover.py`: Tavily on Railway, SearXNG locally) for what the sources missed. Every 5 minutes it merges the new posts into stories (`dedup.py`: shared links, then embeddings computed in a child process), and the LLM cuts roundups into single announcements and reads the stories (`opps.py`), within its budget (`llm.py`: 40 ₽ a month, a tenth of it a day; 30 ₽ until the lectures of 27.10.2026).
  - Each morning at 08:00 (Moscow) `opps_delivery.py` releases what was read since into the app's list, within the window. `annual.py` names the big yearly events the radar awaits and has not found («Ждём»).
  - A lecture, meetup or festival held offline in another city than the user's («Настройки» → «Город», `opps_city`, empty in this public repository) is not shown (`opps_delivery.elsewhere()`).
  - The app reads `GET /opps/board` (with «Скоро», the user's tracked deadlines of the next two weeks and their lectures and meetups of the next week) and `GET /opps?status=tracked,applied` before its page is built, and sets statuses with `POST /opps/{id}/status`. «Настройки» reads and changes `/settings`, `/sources` and `/status`.
- The LLM: DeepSeek Flash through gpt-researcher's `create_chat_completion` with `Config(CONFIG_PATH)` (`config.json`: models, `LLM_KWARGS`); `common/costs.py` patches gpt-researcher's provider to meter every call in rubles. An environment variable or a `.env` line beats `config.json`: that is how the mock LLM takes over a run. gpt-researcher is only the LLM client here (its research is DEEper's).
- Dependencies: `[project]` holds what both parts need (httpx, python-dotenv), dependency groups `core`/`news` the rest, `dev` the icon cutter's fontTools; `tool.uv.default-groups` installs all three, the Dockerfile's `uv sync --no-dev` the first two.
- Other folders: `eval/opps/` measures the reading, `dev/` holds the mock LLM, the icon cutter and the drawers of the app's icon and mascot, `proxy/` is the Cloudflare Worker for access from Russia, `static/` the web app's assets, fonts and icons, `searxng/` the local SearXNG's settings.

## Working in one part

The user may start separate Claude Code sessions in one folder (`my_browser/core`, `news`, `common`, or `eval`, `proxy`). A session started in a folder loads this file and the folder's CLAUDE.md; through the folder's `.claude/settings.json` it reads the whole repository.

- Change files outside your folder only when your change needs it (the other side of a contract you change, in the same commit; your item in `plan.md`; your part's lines here and in `README.md`), and name them in your report.
- Keep contracts compatible: add fields and endpoints rather than rename or remove them.
- Stage and commit only your own files, by path; never `git add -A`, `git commit -a`, `git stash`, `git checkout`/`git restore` on files that are not yours, `git reset --hard` or `git clean`: another session may have uncommitted work in this checkout.
- **Local runs.** Use a throwaway `REPORTS_DIR` (in your scratchpad) and your own ports (`PORT=86xx PUBLIC=0`, `NEWS_PORT`): 8501, 8504 and 8765 may be someone else's. In a fresh `REPORTS_DIR` the loop's first tick polls every source (67 in about 100 s) and, with the real key, the LLM reads the backlog up to the day's budget (4 ₽). Use the mock LLM for checks, `NEWS_LOOP=0` when the radar is not what you are checking, and `NEWS_MODELS_DIR` pointing at one folder, so that each throwaway directory does not download the 220 MB embedding model again.
- Real runs spend the user's money on DeepSeek (shared with DEEper; models and services get about 300 ₽ a month in all): ask before `eval/opps/run_extract.py` or a reading of a real backlog.
- **Before committing**, run the `check-project` skill.
- **Pushing.** A push to `main` deploys to Railway at once (see Deployment). If the new code fails to start, the app is down: with the volume, the old deployment has already stopped. Revert rather than fix forward: `git revert <sha>`, then push.

## Design (AVEN's rules, OnePath's colors)

The UI follows the rules of the user's brandbook (`aven-brandbook.pdf`, kept locally and gitignored, shared with DEEper; `DESIGN_HANDOFF.md` has its screens and the graffiti layer, and DEEper's mascot, which OnePath no longer uses) in OnePath's own colors, taken on 27.10.2026 from a picture the user chose: a man in a hat stepping out of a lit door that stands in a stormy field (someone else's illustration: keep it out of the repository).
- The icon is that door, flat: `static/icon.svg` (the light from the doorway makes a path, «1» on the door's plate, a seagull), and `static/favicon.svg`, the same without its small details for a browser tab. `uv run --with playwright dev/app_icon.py` draws the PNGs from them.
- The mascot is Тропыч (27.10.2026), the picture's walker as a graffiti character: no face, only glasses glowing with the doorway's light and a handlebar moustache under a fedora, a spray can in hand. He is painted as a wall piece (a dark outline, a slate 3D block, a light outer line, fades with bubbles, drips, shines, overspray) in two poses: `static/mascot/hello.svg` on the sign-in screen (tips his hat; the arrow underfoot is sprayed anew in a loop) and `sleep.svg` in an empty list (snoring under his hat, Zs rising). `dev/mascot.py` draws both (`uv run dev/mascot.py`); app.css animates their `w-*` classes, and at rest (reduced motion) each is whole. His hat is also the graffiti on the logo's O.
- Dark only. The roles keep AVEN's names (the CSS variables, `kit.BRAND_COLORS`, props like `color=bordo`), so DEEper's styles still apply: background night `#111B20` (the storm), text paper `#E6ECEF` (the door's frame; never `#FFF`), bordo `#6E3F46` (the book under the walker's arm) only for fills (buttons, selected toggles, the circle of a registered opportunity), amber `#F4DE90` (the light in the doorway) the single accent per screen (one action, the tab underline, link underlines). No fifth color: no green (the picture's leaves stay out), neon or gradients; that is why an opportunity's caption says «из РФ: да», not a green mark. The graffiti layer may be pure white `#FFFFFF`, as decoration (`aria-hidden`, no pointer events) that the user can switch off in «Настройки».
- Fonts are self-hosted in `static/fonts` as WOFF2 subsets: Unbounded only for 2–4 word headings, Onest for text, JetBrains Mono for labels, chips, numbers and URLs; Permanent Marker and Amatic SC only for graffiti. Icons come from `static/fonts/icons.woff2`, NiceGUI's Material Icons cut by `dev/icons.py` to the icons the code names; a name missing from it shows as the word, so write icon names as literals and rerun the script when adding one.
- Styles and client scripts are `static/app.css` and `static/app.js`, linked with a content hash (`?v=`) so a deploy is never hidden by the browser cache. app.css still carries DEEper's styles of screens OnePath does not have (the report, the job page); they cost nothing and keep the shared ones identical.
- Brand colors are registered as Quasar colors (`ui.colors(**BRAND_COLORS)`: `bordo`, `paper`, `amber`, `night`), so props like `color=bordo text-color=paper` work. A color changes in three places: app.css's `:root`, `kit.BRAND_COLORS`, and the theme color in `core/web.py` and `static/manifest.webmanifest` (night); the mascot's colors are in `dev/mascot.py`.

## Deployment

- GitHub: public repo `MrBoomer1981/OnePath` (created by the user on 26.10.2026). Its history starts with the research copy of the night of 27.10.2026, replaced by the radar that morning; DEEper's own history (which holds a leaked `.env`) was never copied. Keep secrets, the user's profile and the app's addresses out of it: the addresses are in the local, gitignored `PRIVATE.md`.
- Railway: project «OnePath», one service built from this repo's `main` with the `Dockerfile` (it runs `app.py`, the Dockerfile's `CMD`), a volume at `/app/reports`, a `*.up.railway.app` domain, region Singapore (where Railway put it, as DEEper). Variables: `DEEPSEEK_API_KEY`, `TAVILY_API_KEY` (the weekly web search: no SearXNG on Railway; the same key as DEEper's, whose researches share its free 1 000 requests a month), `APP_PASSWORD` (the same as DEEper's), `RESEARCH_URL` (DEEper's phone address, for «Исследовать»); `PORT` comes from Railway and makes the app public, with the password. Settings in the dashboard are the user's to change; deploys come from pushes.
- Because of the volume, a redeploy stops the old deployment before the new one starts: a short downtime each time, and no fallback if the new one fails.
- From Russian networks Railway's address does not open without a VPN. The phone opens the app through `proxy/`, a Cloudflare Worker named `onepath` (its address is in `PRIVATE.md`); see `proxy/CLAUDE.md`. It does not open on mobile internet, where Russian providers let a connection to Cloudflare carry only its first ~16 KB. Behind the proxy the app must keep to relative redirects and links: an absolute URL built from the request's host names the Railway address. Per-IP logic (the login rate limit) sees a proxy's address, not the phone's.
- The radar's sources answered Railway's data-center address as they answer a browser in DEEper (25.10.2026); `/status` and «Настройки» → «Источники» name the failing ones.
- The container runs in UTC; the settings' time zone (Moscow) decides the morning update and the days of the budget.
- Memory: DEEper's whole process sat near 1 GB on Railway with the news part in it (25.10.2026); the embedding runs in a child process, so its few hundred megabytes go back after each run, and `common/memory.py` hands freed pages back after each collection. `railway metrics --since 12h` shows it.
- Build the image locally with `docker build -t onepath-check .`. To test it against the host's SearXNG and mock LLM, use `host.docker.internal`.

## The user

Carried over from DEEper's sessions, since a session in this folder starts without their memory:
- Writes in Russian: answer in Russian, in plain words. Use gender-neutral wording about the user and everyone else (no gendered past tense: «вы выбрали», not «выбрал»).
- Opens the app mostly on the phone (an iPhone, installed from Safari): check every screen change at 360 and 390 px wide first.
- Wants a plan before a bigger change, then its implementation without asking again when the plan is solid; for a short fix request («убери…», «поправь…»), the likeliest reading done at once, naming the interpretation in one line. Asks to be asked only about costly, irreversible or budget-spending choices.
- Wants deadlines never missed and time to register early (a missed MATS or summer school costs a year), and reads opportunities in the app, not in Telegram. A reported miss («нашёл X, а его нет») becomes an `eval/opps` case and a fix of its cause (a source, a rule or a prompt), as with the VI Congress of Young Scientists on 26.10.2026.
- No test suite for now (see Commands); verify with throwaway runs and the mock LLM.
- Before creating, pushing to or deleting a GitHub repository, confirm the target and its visibility, unless the user named them.
- Real DeepSeek spend only with the user's approval (the budget is shared with DEEper); routine pushes to `main` after the checks are fine.
- Railway's settings and region are the user's to change.
- The user's personal profile (studies, interests, goals) never goes into this public repository: the code keeps a neutral default, the real text is in the app's settings on the volume («Настройки» → «Профиль»). So does their city (`opps_city`, «Настройки» → «Город»).

## Non-obvious behavior

- DeepSeek through gpt-researcher's `deepseek` provider (ChatOpenAI pointed at api.deepseek.com):
  - Thinking mode is disabled via `LLM_KWARGS.extra_body.thinking`; otherwise every call reasons, which makes it slower and more expensive.
  - langchain-openai sends `max_completion_tokens`, but DeepSeek reads only `max_tokens` (default 8K in non-thinking mode). That is why `max_tokens` is duplicated inside `extra_body`.
  - gpt-researcher logs «Failed to import MCPRetriever» once at its first call: the research's MCP retriever is not installed here, and the radar does not need it.
- The radar embeds posts itself (fastembed in a child process, `news/embed.py`); the mock LLM's `/embeddings` is for any other caller.
- SearXNG (`searxng/settings.yml`) must keep the `json` format enabled. From the user's Mac, only `google cse` and `yahoo` answered relevantly in DEEper's checks; the others gave captchas, rate limits or off-topic junk for Cyrillic queries.
- `common/costs.py` counts the tokens DeepSeek reports at its prices (half price off-peak; 01–04 and 06–10 UTC on weekdays are peak), in rubles; the DeepSeek dashboard has the exact spend, shared with DEEper's key.
