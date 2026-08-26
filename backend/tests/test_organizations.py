from fastapi.testclient import TestClient

from tests.helpers import (
    authorization_headers,
    create_organization,
    register_and_login,
)


def test_organization_crud_listing_and_isolation(client: TestClient) -> None:
    owner, owner_tokens = register_and_login(
        client, "owner@example.com", "Workspace Owner"
    )
    _, other_tokens = register_and_login(client, "other@example.com", "Other Owner")
    organization = create_organization(client, owner_tokens["access_token"])
    create_organization(client, other_tokens["access_token"], "Other Workspace")

    assert organization["slug"] == "acme-workspace"
    assert organization["created_by_id"] == owner["id"]
    assert organization["current_user_role"] == "owner"

    listing = client.get(
        "/api/v1/organizations?limit=1&offset=0",
        headers=authorization_headers(owner_tokens["access_token"]),
    )
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["id"] == organization["id"]

    updated = client.patch(
        f"/api/v1/organizations/{organization['id']}",
        json={"name": "Platform Team", "slug": "platform-team"},
        headers=authorization_headers(owner_tokens["access_token"]),
    )
    assert updated.status_code == 200
    assert updated.json()["slug"] == "platform-team"

    hidden = client.get(
        f"/api/v1/organizations/{organization['id']}",
        headers=authorization_headers(other_tokens["access_token"]),
    )
    assert hidden.status_code == 404


def test_duplicate_organization_slug_returns_conflict(client: TestClient) -> None:
    _, owner_tokens = register_and_login(client, "owner@example.com")
    create_organization(client, owner_tokens["access_token"], "Engineering Team")

    duplicate = client.post(
        "/api/v1/organizations",
        json={"name": "Different Name", "slug": "engineering-team"},
        headers=authorization_headers(owner_tokens["access_token"]),
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "slug_already_exists"


def test_request_models_reject_unknown_and_null_fields(client: TestClient) -> None:
    _, owner_tokens = register_and_login(client, "owner@example.com")
    organization = create_organization(client, owner_tokens["access_token"])
    headers = authorization_headers(owner_tokens["access_token"])

    unknown_field = client.post(
        "/api/v1/organizations",
        json={"name": "Valid Name", "unknown": "value"},
        headers=headers,
    )
    null_name = client.patch(
        f"/api/v1/organizations/{organization['id']}",
        json={"name": None},
        headers=headers,
    )

    assert unknown_field.status_code == 422
    assert null_name.status_code == 422


def test_membership_roles_and_last_owner_protection(client: TestClient) -> None:
    owner, owner_tokens = register_and_login(client, "owner@example.com", "Owner")
    member, member_tokens = register_and_login(client, "member@example.com", "Member")
    viewer, _ = register_and_login(client, "viewer@example.com", "Viewer")
    organization = create_organization(client, owner_tokens["access_token"])
    owner_headers = authorization_headers(owner_tokens["access_token"])
    member_headers = authorization_headers(member_tokens["access_token"])

    added = client.post(
        f"/api/v1/organizations/{organization['id']}/members",
        json={"email": member["email"], "role": "member"},
        headers=owner_headers,
    )
    assert added.status_code == 201
    assert added.json()["role"] == "member"

    forbidden = client.post(
        f"/api/v1/organizations/{organization['id']}/members",
        json={"email": viewer["email"], "role": "viewer"},
        headers=member_headers,
    )
    assert forbidden.status_code == 403

    promoted = client.patch(
        f"/api/v1/organizations/{organization['id']}/members/{member['id']}",
        json={"role": "admin"},
        headers=owner_headers,
    )
    assert promoted.status_code == 200
    assert promoted.json()["role"] == "admin"

    admin_adds_viewer = client.post(
        f"/api/v1/organizations/{organization['id']}/members",
        json={"email": viewer["email"], "role": "viewer"},
        headers=member_headers,
    )
    assert admin_adds_viewer.status_code == 201

    admin_cannot_assign_owner = client.patch(
        f"/api/v1/organizations/{organization['id']}/members/{viewer['id']}",
        json={"role": "owner"},
        headers=member_headers,
    )
    assert admin_cannot_assign_owner.status_code == 403

    last_owner = client.patch(
        f"/api/v1/organizations/{organization['id']}/members/{owner['id']}",
        json={"role": "admin"},
        headers=owner_headers,
    )
    assert last_owner.status_code == 409
    assert last_owner.json()["error"]["code"] == "last_owner"

    members = client.get(
        f"/api/v1/organizations/{organization['id']}/members",
        headers=owner_headers,
    )
    assert members.status_code == 200
    assert members.json()["total"] == 3


def test_only_owner_can_delete_organization(client: TestClient) -> None:
    _, owner_tokens = register_and_login(client, "owner@example.com")
    member, member_tokens = register_and_login(client, "member@example.com")
    organization = create_organization(client, owner_tokens["access_token"])
    owner_headers = authorization_headers(owner_tokens["access_token"])

    client.post(
        f"/api/v1/organizations/{organization['id']}/members",
        json={"email": member["email"], "role": "admin"},
        headers=owner_headers,
    )
    forbidden = client.delete(
        f"/api/v1/organizations/{organization['id']}",
        headers=authorization_headers(member_tokens["access_token"]),
    )
    deleted = client.delete(
        f"/api/v1/organizations/{organization['id']}",
        headers=owner_headers,
    )

    assert forbidden.status_code == 403
    assert deleted.status_code == 204
