from fastapi.testclient import TestClient

from tests.helpers import (
    DEFAULT_PASSWORD,
    authorization_headers,
    login_user,
    register_user,
)


def test_registration_normalizes_email_and_rejects_duplicates(
    client: TestClient,
) -> None:
    user = register_user(client, "OWNER@Example.com", "Workspace Owner")

    assert user["email"] == "owner@example.com"
    assert user["full_name"] == "Workspace Owner"
    assert user["is_active"] is True
    assert "password" not in user
    assert "password_hash" not in user

    duplicate = client.post(
        "/api/v1/auth/register",
        json={
            "email": "owner@example.com",
            "full_name": "Duplicate",
            "password": DEFAULT_PASSWORD,
        },
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "email_already_registered"


def test_password_validation_uses_central_error_contract(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "weak@example.com",
            "full_name": "Weak Password",
            "password": "password",
        },
        headers={"X-Request-ID": "test-request-id"},
    )

    body = response.json()
    assert response.status_code == 422
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["details"]
    assert body["request_id"] == "test-request-id"


def test_login_current_user_refresh_rotation_and_logout(client: TestClient) -> None:
    user = register_user(client, "owner@example.com", "Workspace Owner")
    tokens = login_user(client, "owner@example.com")

    assert tokens["token_type"] == "bearer"
    assert tokens["expires_in"] == 900

    current_user = client.get(
        "/api/v1/users/me",
        headers=authorization_headers(tokens["access_token"]),
    )
    assert current_user.status_code == 200
    assert current_user.json()["id"] == user["id"]

    refreshed = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refreshed.status_code == 200
    refreshed_tokens = refreshed.json()
    assert refreshed_tokens["refresh_token"] != tokens["refresh_token"]

    reused = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert reused.status_code == 401
    assert reused.json()["error"]["code"] == "invalid_refresh_token"

    logout = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refreshed_tokens["refresh_token"]},
    )
    assert logout.status_code == 200

    after_logout = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refreshed_tokens["refresh_token"]},
    )
    assert after_logout.status_code == 401


def test_invalid_credentials_and_missing_token_are_rejected(client: TestClient) -> None:
    register_user(client, "owner@example.com")

    invalid_login = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "WrongPass123"},
    )
    missing_token = client.get("/api/v1/users/me")

    assert invalid_login.status_code == 401
    assert invalid_login.json()["error"]["code"] == "invalid_credentials"
    assert missing_token.status_code == 401
    assert missing_token.json()["error"]["code"] == "authentication_required"

    tokens = login_user(client, "owner@example.com")
    wrong_token_type = client.get(
        "/api/v1/users/me",
        headers=authorization_headers(tokens["refresh_token"]),
    )
    assert wrong_token_type.status_code == 401
    assert wrong_token_type.json()["error"]["code"] == "invalid_token"
