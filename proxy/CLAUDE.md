# CLAUDE.md: proxy

`proxy/` is a Cloudflare Worker: the address through which the user's phone opens OnePath from Russia without a VPN. It holds no state and shares no code with the Python parts, and it deploys with wrangler, not with a push. It is DEEper's proxy (github.com/MrBoomer1981/DEEper, `proxy/`) under its own Worker name, `onepath`. The repository's rules are in the root CLAUDE.md.

## Why it exists

From Russian networks Railway's edge address (69.46.46.46: every `*.up.railway.app` site and railway.com itself) does not open without a VPN, whatever the domain name, so a custom domain on Railway would not help. Cloudflare does open; checked 2026-10-20 for DEEper: `*.workers.dev` opens and `*.pages.dev` does not.

## What it does

- `worker.js` passes every request on to the app on Railway: phone → Cloudflare → Railway.
  - The incoming request is the init of the new one, so method, headers (a WebSocket upgrade too, for NiceGUI's pages) and body pass on as they are.
  - Redirects go back to the browser, not followed here. A `Location` that names the Railway address is rewritten to the Worker's own.
- `ORIGIN`, the app's Railway address, is a Worker secret. Keep it, and the Worker's own address, out of this public repository (the local `PRIVATE.md` has both). The phone opens `onepath.<account subdomain>.workers.dev`.
- `wrangler.toml`: the Worker's name (`onepath`), its entry point and `workers_dev = true`.

## Where it does not open: mobile internet

Since June 2025 Russian providers let a connection to many Cloudflare addresses carry only its first ~16 KB. The Worker's addresses are throttled this way on mobile internet (checked for DEEper's Worker on 2026-10-20: a page froze after ~3 KB); on home Wi-Fi and the ITMO network it loads. Nothing in the Worker or the app changes this. DEEper prepared a fix, a small server in Russia in front of Railway (its `proxy/ru/`, archived by the user on 2026-10-21); it would serve OnePath the same way.

## Deploy and check

```bash
npx wrangler deploy                   # from this folder; wrangler is logged in on the user's Mac (Workers-only scopes)
npx wrangler secret put ORIGIN        # only when the Railway address changes
```

- The first time on a machine, `npx wrangler login` opens a browser for the user's Cloudflare account. The user signs in; never type their credentials.
- **Check from a Russian network.** If the machine runs a VPN, `curl --interface en0` (the Wi-Fi interface on a Mac) goes around it: `curl --interface en0 -s -o /dev/null -w '%{http_code} %{time_total}\n' https://<the Worker's address>/login`. A fixed network passing says nothing about mobile internet.
- Some new connections to Cloudflare's addresses took about 19 s from a Russian home network (2026-10-20), so time a request more than once before blaming the Worker.

## What the app must keep for it

- Relative redirects and links. An absolute URL built from the request's host names the Railway address, which does not open in Russia; the Worker only rewrites `Location` headers.
- Per-IP logic sees a Cloudflare address, not the phone's. The login rate limit is the one such place.
