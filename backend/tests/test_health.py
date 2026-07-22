from fastapi.testclient import TestClient
from team_workspace.main import app

client = TestClient(app)


def test_health_check_returns_healthy_status() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
