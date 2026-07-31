#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_ROOT=$(dirname "$SCRIPT_DIR")
ENV_FILE="$PROJECT_ROOT/.env.production"
BACKUP_DIR="$PROJECT_ROOT/backups"

cd "$PROJECT_ROOT"

if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is required but was not found." >&2
    exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
    echo "Docker Compose is required but was not found." >&2
    exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
    echo "Missing $ENV_FILE. Copy .env.production.example and configure it first." >&2
    exit 1
fi

read_env_value() {
    sed -n "s/^$1=//p" "$ENV_FILE" | tail -n 1 | tr -d '\r"'
}

database_name=$(read_env_value POSTGRES_DB)
database_user=$(read_env_value POSTGRES_USER)
database_password=$(read_env_value POSTGRES_PASSWORD)

if [ -z "$database_name" ] || [ -z "$database_user" ] || [ -z "$database_password" ]; then
    echo "POSTGRES_DB, POSTGRES_USER, and POSTGRES_PASSWORD are required." >&2
    exit 1
fi

safe_database_name=$(printf '%s' "$database_name" | tr -c 'A-Za-z0-9_.-' '_')
timestamp=$(date -u +%Y%m%dT%H%M%SZ)
backup_file="$BACKUP_DIR/${safe_database_name}_${timestamp}.sql"
partial_file="$backup_file.partial"

mkdir -p "$BACKUP_DIR"
trap 'rm -f "$partial_file"' EXIT

docker compose \
    --env-file "$ENV_FILE" \
    -f compose.production.yaml \
    exec -T database \
    sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
    > "$partial_file"

mv "$partial_file" "$backup_file"
trap - EXIT

echo "PostgreSQL backup written to $backup_file"
