# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:0.11.33 AS uv

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

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

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
