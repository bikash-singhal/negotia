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
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Not Found",
        }
    }


def test_health_does_not_allow_post() -> None:
    response = client.post("/api/v1/health")

    assert response.status_code == 405
    assert response.json() == {
        "error": {
            "code": "method_not_allowed",
            "message": "Method Not Allowed",
        }
    }
