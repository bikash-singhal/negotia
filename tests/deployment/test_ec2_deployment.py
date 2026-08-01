from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]


def _read(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def _environment_values() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in _read(".env.production.example").splitlines():
        if line and not line.startswith("#"):
            key, value = line.split("=", maxsplit=1)
            values[key] = value
    return values


def test_production_compose_publishes_only_frontend() -> None:
    production_compose = _read("compose.production.yaml")
    database_config, remaining = production_compose.split("  api:", maxsplit=1)
    api_config, frontend_config = remaining.split("  frontend:", maxsplit=1)

    assert "ports: !reset []" in database_config
    assert "ports: !reset []" in api_config
    assert '- "${WEB_PORT:-80}:80"' in frontend_config
    assert "condition: service_healthy" in frontend_config
    assert "restart: unless-stopped" in database_config
    assert "restart: unless-stopped" in api_config
    assert "restart: unless-stopped" in frontend_config


def test_production_configuration_excludes_aws_credentials_and_profiles() -> None:
    production_configuration = _read("compose.production.yaml") + _read(
        ".env.production.example"
    )

    assert "AWS_ACCESS_KEY_ID" not in production_configuration
    assert "AWS_SECRET_ACCESS_KEY" not in production_configuration
    assert "AWS_PROFILE" not in production_configuration


def test_deployment_script_uses_safe_compose_operations() -> None:
    deployment_script = _read("scripts/deploy-ec2.sh")
    normalized_script = deployment_script.lower()

    assert "git pull --ff-only" in deployment_script
    assert "-f compose.yaml" in deployment_script
    assert "-f compose.production.yaml" in deployment_script
    assert "compose_command config --quiet" in deployment_script
    assert "compose_command build api frontend" in deployment_script
    assert "compose_command up -d --wait" in deployment_script
    assert "compose_command logs --tail=100 frontend api database" in deployment_script
    assert "Replace the placeholder POSTGRES_PASSWORD" in deployment_script
    assert "Replace the placeholder JWT_SECRET_KEY" in deployment_script
    assert "docker compose down -v" not in normalized_script
    assert "docker compose down --volumes" not in normalized_script
    assert "docker system prune" not in normalized_script


def test_backup_script_creates_a_timestamped_pg_dump() -> None:
    backup_script = _read("scripts/backup-postgres.sh")

    assert "pg_dump" in backup_script
    assert "date -u +%Y%m%dT%H%M%SZ" in backup_script
    assert 'BACKUP_DIR="$PROJECT_ROOT/backups"' in backup_script
    assert 'mv "$partial_file" "$backup_file"' in backup_script


def test_production_environment_uses_placeholders_without_credentials() -> None:
    values = _environment_values()

    assert values == {
        "APP_NAME": '"Negotia API"',
        "API_VERSION": "0.1.0",
        "DEBUG": "false",
        "WEB_PORT": "80",
        "VITE_API_BASE_URL": "/api/v1",
        "JWT_SECRET_KEY": "CHANGE_ME_TO_A_STRONG_RANDOM_SECRET",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "30",
        "POSTGRES_DB": "negotia",
        "POSTGRES_USER": "negotia",
        "POSTGRES_PASSWORD": "CHANGE_ME_TO_A_STRONG_RANDOM_PASSWORD",
        "DATABASE_URL": (
            "postgresql+psycopg://negotia:"
            "CHANGE_ME_TO_URL_ENCODED_PASSWORD@database:5432/negotia"
        ),
        "LLM_PROVIDER": "bedrock",
        "BEDROCK_MODEL_ID": "amazon.nova-lite-v1:0",
        "AWS_REGION": "us-east-1",
    }
    assert "local-development-password" not in values.values()


def test_shell_scripts_use_linux_line_endings() -> None:
    for relative_path in ("scripts/deploy-ec2.sh", "scripts/backup-postgres.sh"):
        assert b"\r\n" not in (PROJECT_ROOT / relative_path).read_bytes()


def test_production_frontend_dockerfile_builds_vite_and_serves_with_nginx() -> None:
    dockerfile = _read("frontend/Dockerfile")

    assert "FROM node:22-alpine AS build" in dockerfile
    assert "corepack prepare pnpm@11.9.0 --activate" in dockerfile
    assert "COPY package.json pnpm-lock.yaml ./" in dockerfile
    assert "pnpm install --frozen-lockfile" in dockerfile
    assert "ARG VITE_API_BASE_URL=/api/v1" in dockerfile
    assert "RUN pnpm build" in dockerfile
    assert "FROM nginx:1.29-alpine AS runtime" in dockerfile
    assert "COPY --from=build /app/dist /usr/share/nginx/html" in dockerfile
    assert "vite --host" not in dockerfile


def test_nginx_serves_spa_and_streams_same_origin_api() -> None:
    nginx_config = _read("frontend/nginx.conf")

    assert "location /api/" in nginx_config
    assert "proxy_pass http://api:8000;" in nginx_config
    assert "proxy_http_version 1.1;" in nginx_config
    assert "proxy_buffering off;" in nginx_config
    assert "proxy_cache off;" in nginx_config
    assert 'add_header Cache-Control "no-store" always;' in nginx_config
    assert "proxy_read_timeout 300s;" in nginx_config
    assert "proxy_send_timeout 300s;" in nginx_config
    assert "try_files $uri $uri/ /index.html;" in nginx_config
    assert 'add_header X-Content-Type-Options "nosniff" always;' in nginx_config
    assert 'add_header X-Frame-Options "DENY" always;' in nginx_config
    assert "add_header Referrer-Policy" in nginx_config


def test_frontend_build_receives_only_public_same_origin_configuration() -> None:
    production_compose = _read("compose.production.yaml")
    frontend_config = production_compose.split("  frontend:", maxsplit=1)[1]

    assert "VITE_API_BASE_URL: ${VITE_API_BASE_URL:-/api/v1}" in frontend_config
    assert "JWT_SECRET_KEY" not in frontend_config
    assert "POSTGRES_PASSWORD" not in frontend_config
    assert "AWS_" not in frontend_config


def test_frontend_local_development_keeps_localhost_api_configuration() -> None:
    assert _read("frontend/.env.example").strip() == (
        "VITE_API_BASE_URL=http://localhost:8000/api/v1"
    )


def test_frontend_healthcheck_does_not_require_javascript() -> None:
    production_compose = _read("compose.production.yaml")
    frontend_config = production_compose.split("  frontend:", maxsplit=1)[1]

    assert "wget -q -O /dev/null http://127.0.0.1/" in frontend_config
    assert "node" not in frontend_config.lower()
