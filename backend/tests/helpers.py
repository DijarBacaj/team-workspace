from typing import Any

from fastapi.testclient import TestClient

DEFAULT_PASSWORD = "StrongPass123"


def register_user(
    client: TestClient,
    email: str,
    full_name: str = "Test User",
    password: str = DEFAULT_PASSWORD,
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": full_name, "password": password},
    )
    assert response.status_code == 201, response.text
    return response.json()


def login_user(
    client: TestClient,
    email: str,
    password: str = DEFAULT_PASSWORD,
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()


def authorization_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def register_and_login(
    client: TestClient,
    email: str,
    full_name: str = "Test User",
) -> tuple[dict[str, Any], dict[str, Any]]:
    user = register_user(client, email, full_name)
    tokens = login_user(client, email)
    return user, tokens


def create_organization(
    client: TestClient,
    access_token: str,
    name: str = "Acme Workspace",
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/organizations",
        json={"name": name},
        headers=authorization_headers(access_token),
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_project(
    client: TestClient,
    access_token: str,
    organization_id: str,
    name: str = "API Project",
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/organizations/{organization_id}/projects",
        json={"name": name, "description": "Integration test project"},
        headers=authorization_headers(access_token),
    )
    assert response.status_code == 201, response.text
    return response.json()
