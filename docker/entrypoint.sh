#!/bin/sh
set -eu

uv run alembic upgrade head

exec "$@"
