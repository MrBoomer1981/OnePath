# Image for the web app and the radar's loop on Railway (or any Docker host).
FROM python:3.12-slim

# libmagic for gpt-researcher's document loaders, which the radar's LLM calls import with it.
RUN apt-get update && apt-get install -y --no-install-recommends libmagic1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_CACHE=1 PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .

CMD ["uv", "run", "--no-sync", "app.py"]
