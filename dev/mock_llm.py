"""A fake OpenAI-compatible LLM for free end-to-end runs: the whole radar works, nothing is paid.

    uv run dev/mock_llm.py                          # http://127.0.0.1:8765/v1
    uv run dev/mock_llm.py --port 8766 --log calls.jsonl

Point a run at it with environment variables, which beat config.json:

    FAST_LLM=openai:mock SMART_LLM=openai:mock STRATEGIC_LLM=openai:mock \
    OPENAI_BASE_URL=http://127.0.0.1:8765/v1 OPENAI_API_KEY=mock uv run app.py

It answers the radar's prompts by a phrase of each (news/opps.py: cutting roundups and reading announcements;
news/discover.py: the week's web search queries) with answers of the shape the caller parses. If a prompt's wording
changes, it gets an empty list: a run still ends, but that step reads nothing. --log writes one JSON line per call:
which step it was, the model and the token cap it was sent.
"""

import argparse
import json
import re
import time
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

STEPS = {  # by a phrase of the prompt, as the callers write it
    "split": "Ты разбираешь посты-подборки о возможностях",
    "extract": "Ты разбираешь анонсы возможностей для студента",
    "queries": "поисковых запросов для веб-поиска",
}


def answer(prompt: str) -> str:
    if STEPS["split"] in prompt:  # two opportunities in each roundup
        posts = [int(n) for n in re.findall(r"^\[post (\d+)\]", prompt, re.M)]
        soon = (date.today() + timedelta(days=10)).isoformat()
        return json.dumps([{"post": n, "items": [{"title": f"Тестовый хакатон {n}.{k}", "text": f"Онлайн-хакатон по ИИ для "
                                                  f"студентов, регистрация до {soon}.", "url": None} for k in (1, 2)]}
                           for n in posts], ensure_ascii=False)
    if STEPS["extract"] in prompt:  # the first due soon, every fourth not one; the third big and five months ahead
        # (inside the app's longer window), the fifth four months (beyond it)
        ids = [int(n) for n in re.findall(r"^\[id (\d+)\]", prompt, re.M)]
        return json.dumps([{"id": n, "is_opportunity": False, "reason": "тестовая новость"} if n % 4 == 0 else
                           {"id": n, "is_opportunity": True, "reason": None, "opp_type": "hackathon" if n == 1 else "school",
                            "title_ru": f"Тестовая возможность {n}", "organizer": "Тестовый организатор",
                            "summary_ru": "Тестовая возможность: что это и что даёт.", "deadline_text": "тестовый дедлайн",
                            "deadline": (date.today() + timedelta(days={1: 5, 3: 150, 5: 120}.get(n, 30))).isoformat(),
                            "deadline_tz": None,
                            "deadline_kind": "exact", "starts": None, "ends": None, "format": "online", "location": None,
                            "eligibility": "студенты", "ru_access": "yes" if n == 1 else "unclear", "cost": "бесплатно",
                            "reward": None, "apply_url": "https://example.org/apply", "fit": 8 if n == 1 else 5,
                            "fit_reason": "тестовая причина", "major": n == 3, "same_as": None} for n in ids], ensure_ascii=False)
    if STEPS["queries"] in prompt:
        return json.dumps(["хакатон по искусственному интеллекту для студентов регистрация",
                           "machine learning summer school applications open"], ensure_ascii=False)
    return "[]"


class Handler(BaseHTTPRequestHandler):
    log_path = None

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path.endswith("/embeddings"):  # the radar embeds locally (fastembed); answered all the same
            inputs = body["input"] if isinstance(body["input"], list) else [body["input"]]
            data = [{"object": "embedding", "index": i, "embedding": [((hash(str(x)) >> k) % 100) / 100 for k in range(16)]}
                    for i, x in enumerate(inputs)]
            return self._json({"object": "list", "data": data, "model": "mock", "usage": {"prompt_tokens": 1, "total_tokens": 1}})
        prompt = "\n".join(str(m.get("content")) for m in body["messages"])
        text = answer(prompt)
        if self.log_path:
            step = next((name for name, phrase in STEPS.items() if phrase in prompt), None)
            cap = body.get("max_tokens") or body.get("max_completion_tokens")
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"t": round(time.time(), 2), "step": step, "model": body.get("model"), "max_tokens": cap},
                                   ensure_ascii=False) + "\n")
        self._json({"id": "mock", "object": "chat.completion", "created": 0, "model": body.get("model"),
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 1000, "completion_tokens": 100, "total_tokens": 1100}})

    def _json(self, data: dict) -> None:
        out = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--log", help="append one JSON line per chat call to this file")
    args = parser.parse_args()
    Handler.log_path = args.log
    print(f"Mock LLM: http://127.0.0.1:{args.port}/v1", flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
