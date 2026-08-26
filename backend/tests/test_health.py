from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_health_check_returns_healthy_status(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
    assert response.headers["X-Request-ID"]


def test_readiness_check_reaches_database(client: TestClient) -> None:
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "available"}


def test_unexpected_errors_use_central_error_contract(test_app: FastAPI) -> None:
    @test_app.get("/_test/unexpected-error")
    async def unexpected_error() -> None:
        raise RuntimeError("Test failure")

    with TestClient(test_app, raise_server_exceptions=False) as local_client:
        response = local_client.get(
            "/_test/unexpected-error",
            headers={"X-Request-ID": "unexpected-error-test"},
        )

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_server_error",
            "message": "An unexpected error occurred.",
        },
        "request_id": "unexpected-error-test",
    }
