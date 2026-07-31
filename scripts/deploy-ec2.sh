#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_ROOT=$(dirname "$SCRIPT_DIR")
ENV_FILE="$PROJECT_ROOT/.env.production"
DEPLOY_BRANCH=${DEPLOY_BRANCH:-main}

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

if grep -q '^POSTGRES_PASSWORD=CHANGE_ME_TO_A_STRONG_RANDOM_PASSWORD$' "$ENV_FILE"; then
    echo "Replace the placeholder POSTGRES_PASSWORD in $ENV_FILE before deployment." >&2
    exit 1
fi

if grep -q 'CHANGE_ME_TO_URL_ENCODED_PASSWORD' "$ENV_FILE"; then
    echo "Replace the placeholder password in DATABASE_URL before deployment." >&2
    exit 1
fi

compose_command() {
    docker compose \
        --env-file "$ENV_FILE" \
        -f compose.production.yaml \
        "$@"
}

echo "Updating branch $DEPLOY_BRANCH..."
git fetch origin "$DEPLOY_BRANCH"
git switch "$DEPLOY_BRANCH"
git pull --ff-only origin "$DEPLOY_BRANCH"

echo "Validating the production Compose configuration..."
compose_command config --quiet

echo "Building the API image..."
compose_command build api

echo "Starting the production stack..."
if ! compose_command up -d --wait; then
    echo "Production stack did not become healthy. Recent API logs:" >&2
    compose_command ps >&2 || true
    compose_command logs --tail=100 api >&2 || true
    exit 1
fi

compose_command ps