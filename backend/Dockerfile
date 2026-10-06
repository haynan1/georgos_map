# syntax=docker/dockerfile:1.12

ARG PYTHON_VERSION=3.14

FROM ghcr.io/astral-sh/uv:0.12.23 AS uv

# ---------------------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app

# ---------------------------------------------------------------------------------------
# Resolves runtime dependencies from the lockfile only. Copying the lockfile before the
# source keeps this layer cached until dependencies actually change.
FROM base AS builder
COPY --from=uv /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock .python-version ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# ---------------------------------------------------------------------------------------
# Development image: adds test/lint tooling; source is bind-mounted by compose.
FROM builder AS dev
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project
USER app
EXPOSE 8000
CMD ["uvicorn", "--factory", "app.main:build_app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ---------------------------------------------------------------------------------------
# Production image: interpreter + virtualenv + source. No uv, no compilers, no tests.
FROM base AS runtime
COPY --from=builder /opt/venv /opt/venv
COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app
USER app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health/live', timeout=2)"]
# Workers scale with WEB_CONCURRENCY; trusted proxies come from FORWARDED_ALLOW_IPS.
CMD ["uvicorn", "--factory", "app.main:build_app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header", "--no-access-log"]
