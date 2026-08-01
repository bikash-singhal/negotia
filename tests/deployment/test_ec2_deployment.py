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


def test_production_compose_removes_database_port_and_publishes_api() -> None:
    production_compose = _read("compose.production.yaml")
    database_config, api_config = production_compose.split("  api:", maxsplit=1)

    assert "ports:" not in database_config
    assert '- "${API_PORT:-8000}:8000"' in api_config


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
    assert "compose_command config --quiet" in deployment_script
    assert "compose_command build api" in deployment_script
    assert "compose_command up -d --wait" in deployment_script
    assert "compose_command logs --tail=100 api" in deployment_script
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
        "API_PORT": "8000",
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
