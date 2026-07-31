from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]


def _read(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def test_dockerfile_uses_locked_dependencies_and_non_root_runtime() -> None:
    dockerfile = _read("Dockerfile")

    assert "FROM python:3.12-slim" in dockerfile
    assert "COPY pyproject.toml uv.lock ./" in dockerfile
    assert "uv sync --frozen --no-dev --no-install-project" in dockerfile
    assert dockerfile.index("COPY pyproject.toml uv.lock ./") < dockerfile.index(
        "COPY app ./app"
    )
    assert "USER negotia" in dockerfile
    assert '"uvicorn", "app.main:app"' in dockerfile
    assert '"--host", "0.0.0.0"' in dockerfile
    assert "--reload" not in dockerfile


def test_dockerignore_excludes_local_environment_and_artifacts() -> None:
    ignored_paths = set(_read(".dockerignore").splitlines())

    assert {".git", ".venv", ".env", ".env.*", "tests"} <= ignored_paths
    assert "alembic" not in ignored_paths
    assert "uv.lock" not in ignored_paths


def test_compose_wires_api_to_healthy_database() -> None:
    compose = _read("compose.yaml")

    assert "  database:" in compose
    assert "  api:" in compose
    assert "condition: service_healthy" in compose
    assert "@database:5432/" in compose
    assert "${API_PORT:-8000}:8000" in compose
    assert "postgres_data:/var/lib/postgresql/data" in compose
    assert "restart: unless-stopped" in compose


def test_container_runs_migrations_before_uvicorn() -> None:
    entrypoint = _read("docker/entrypoint.sh")
    dockerfile = _read("Dockerfile")

    assert entrypoint.index("uv run alembic upgrade head") < entrypoint.index(
        'exec "$@"'
    )
    assert 'ENTRYPOINT ["/usr/local/bin/negotia-entrypoint"]' in dockerfile
    assert "--reload" not in entrypoint


def test_compose_healthcheck_uses_versioned_application_endpoint() -> None:
    compose = _read("compose.yaml")

    assert "http://127.0.0.1:8000/api/v1/health" in compose
    assert "curl" not in compose
