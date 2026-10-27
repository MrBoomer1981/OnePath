"""HTTP calls between the parts.

News is reached at NEWS_URL when it runs as its own process, otherwise in-process through its ASGI app: the same
requests and the same API, without a network hop. A client is opened per call: core's pages and the checks call
from different event loops.
"""

import functools
import importlib

import httpx

from my_browser.common.settings import CORE_URL, NEWS_URL, service_token

_APPS = {"news": "my_browser.news.api"}


@functools.cache
def _app(part: str):
    return importlib.import_module(_APPS[part]).app


def _options(part: str, timeout: float) -> dict:
    options = {"headers": {"Authorization": f"Bearer {service_token()}"}, "timeout": timeout}
    url = {"core": CORE_URL, "news": NEWS_URL}[part]
    if url:
        return {**options, "base_url": url.rstrip("/")}
    return {**options, "base_url": f"http://{part}", "transport": httpx.ASGITransport(app=_app(part))}


async def call(part: str, method: str, path: str, timeout: float = 120, **kwargs) -> httpx.Response:
    async with httpx.AsyncClient(**_options(part, timeout)) as client:
        response = await client.request(method, path, **kwargs)
    response.raise_for_status()
    return response
