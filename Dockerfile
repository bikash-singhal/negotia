# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:0.11.33 AS uv

FROM python:3.12-slim-bookworm AS hermes-build

COPY --from=uv /uv /bin/uv
# Official source install, release v2026.9.14 (Hermes 0.21.3).
# Keep Hermes' pinned dependencies separate from the API's uv.lock.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/hermes
RUN git init . \
    && git remote add origin https://github.com/NousResearch/hermes-agent.git \
    && git fetch --depth 1 origin 345cd2b057a452236de401d3534b8502a7465e8d \
    && git checkout --detach FETCH_HEAD \
    && test "$(git rev-parse HEAD)" = 345cd2b057a452236de401d3534b8502a7465e8d \
    && rm -rf .git
RUN UV_PYTHON_DOWNLOADS=never uv sync --frozen --no-dev --python /usr/local/bin/python3.12 \
        --extra bedrock --extra mcp --no-cache \
    && .venv/bin/python -c "from importlib.metadata import version; assert version('hermes-agent') == '0.21.3'"
# Development/desktop documentation and tests are not used by the headless CLI.
RUN rm -rf tests website apps contributors .github \
    && printf 'docker\n' > .install_method

FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_SYNC=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY --from=uv /uv /uvx /bin/
COPY --from=hermes-build /opt/hermes /opt/hermes
RUN ln -s /opt/hermes/.venv/bin/hermes /usr/local/bin/hermes

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --no-cache

RUN groupadd --system negotia \
    && useradd --system --gid negotia --create-home negotia

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY docker/entrypoint.sh /usr/local/bin/negotia-entrypoint
RUN sed -i 's/\r$//' /usr/local/bin/negotia-entrypoint \
    && chmod 0755 /usr/local/bin/negotia-entrypoint

USER negotia

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/negotia-entrypoint"]
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
