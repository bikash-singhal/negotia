from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "negotia-api",
    }


def test_unversioned_health_does_not_exist() -> None:
    response = client.get("/health")

    assert response.status_code == 404
