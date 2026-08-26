from typing import Any

from fastapi.testclient import TestClient

from tests.helpers import (
    authorization_headers,
    create_organization,
    create_project,
    register_and_login,
    register_user,
)


def setup_workspace(client: TestClient) -> dict[str, Any]:
    owner, owner_tokens = register_and_login(client, "owner@example.com", "Owner")
    member, member_tokens = register_and_login(client, "member@example.com", "Member")
    viewer, viewer_tokens = register_and_login(client, "viewer@example.com", "Viewer")
    outsider = register_user(client, "outsider@example.com", "Outsider")
    owner_headers = authorization_headers(owner_tokens["access_token"])
    organization = create_organization(client, owner_tokens["access_token"])
    for user, role in ((member, "member"), (viewer, "viewer")):
        response = client.post(
            f"/api/v1/organizations/{organization['id']}/members",
            json={"email": user["email"], "role": role},
            headers=owner_headers,
        )
        assert response.status_code == 201
    project = create_project(
        client,
        owner_tokens["access_token"],
        organization["id"],
    )
    label_response = client.post(
        f"/api/v1/organizations/{organization['id']}/labels",
        json={"name": "Backend", "color": "#2563eb"},
        headers=owner_headers,
    )
    assert label_response.status_code == 201
    return {
        "owner": owner,
        "owner_tokens": owner_tokens,
        "member": member,
        "member_tokens": member_tokens,
        "viewer": viewer,
        "viewer_tokens": viewer_tokens,
        "outsider": outsider,
        "organization": organization,
        "project": project,
        "label": label_response.json(),
    }


def test_project_crud_filtering_and_unique_name(client: TestClient) -> None:
    workspace = setup_workspace(client)
    organization = workspace["organization"]
    project = workspace["project"]
    owner_tokens = workspace["owner_tokens"]
    owner_headers = authorization_headers(owner_tokens["access_token"])

    duplicate = client.post(
        f"/api/v1/organizations/{organization['id']}/projects",
        json={"name": project["name"]},
        headers=owner_headers,
    )
    assert duplicate.status_code == 409

    listing = client.get(
        f"/api/v1/organizations/{organization['id']}/projects"
        "?search=API&status=active&sort_by=name&sort_direction=asc",
        headers=owner_headers,
    )
    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    archived = client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"status": "archived"},
        headers=owner_headers,
    )
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"

    retrieved = client.get(
        f"/api/v1/projects/{project['id']}",
        headers=owner_headers,
    )
    assert retrieved.status_code == 200
    assert retrieved.json()["id"] == project["id"]


def test_member_manages_task_with_assignments_labels_and_filters(
    client: TestClient,
) -> None:
    workspace = setup_workspace(client)
    member = workspace["member"]
    outsider = workspace["outsider"]
    member_tokens = workspace["member_tokens"]
    project = workspace["project"]
    label = workspace["label"]
    member_headers = authorization_headers(member_tokens["access_token"])

    created = client.post(
        f"/api/v1/projects/{project['id']}/tasks",
        json={
            "title": "Implement authentication",
            "description": "Add access and refresh tokens",
            "priority": "high",
            "assignee_ids": [member["id"]],
            "label_ids": [label["id"]],
        },
        headers=member_headers,
    )
    assert created.status_code == 201, created.text
    task = created.json()
    assert task["status"] == "todo"
    assert task["assignees"][0]["id"] == member["id"]
    assert task["labels"][0]["color"] == "#2563EB"

    invalid_assignee = client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={"assignee_ids": [outsider["id"]]},
        headers=member_headers,
    )
    assert invalid_assignee.status_code == 422
    assert invalid_assignee.json()["error"]["code"] == "invalid_assignees"

    updated = client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={"status": "in_progress", "priority": "urgent"},
        headers=member_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "in_progress"

    listing = client.get(
        f"/api/v1/projects/{project['id']}/tasks"
        f"?status=in_progress&priority=urgent&assignee_id={member['id']}"
        f"&label_id={label['id']}&limit=1",
        headers=member_headers,
    )
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["id"] == task["id"]

    naive_due_date = client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={"due_at": "2026-09-01T12:00:00"},
        headers=member_headers,
    )
    assert naive_due_date.status_code == 422


def test_explicit_assignment_and_label_endpoints_are_idempotent(
    client: TestClient,
) -> None:
    workspace = setup_workspace(client)
    member = workspace["member"]
    member_tokens = workspace["member_tokens"]
    project = workspace["project"]
    label = workspace["label"]
    headers = authorization_headers(member_tokens["access_token"])
    task = client.post(
        f"/api/v1/projects/{project['id']}/tasks",
        json={"title": "Write integration tests"},
        headers=headers,
    ).json()

    for _ in range(2):
        assigned = client.put(
            f"/api/v1/tasks/{task['id']}/assignees/{member['id']}",
            headers=headers,
        )
        attached = client.put(
            f"/api/v1/tasks/{task['id']}/labels/{label['id']}",
            headers=headers,
        )
        assert assigned.status_code == 200
        assert attached.status_code == 200
        assert len(assigned.json()["assignees"]) == 1
        assert len(attached.json()["labels"]) == 1

    unassigned = client.delete(
        f"/api/v1/tasks/{task['id']}/assignees/{member['id']}",
        headers=headers,
    )
    detached = client.delete(
        f"/api/v1/tasks/{task['id']}/labels/{label['id']}",
        headers=headers,
    )
    assert unassigned.json()["assignees"] == []
    assert detached.json()["labels"] == []


def test_comments_permissions_and_pagination(client: TestClient) -> None:
    workspace = setup_workspace(client)
    member_tokens = workspace["member_tokens"]
    viewer_tokens = workspace["viewer_tokens"]
    project = workspace["project"]
    member_headers = authorization_headers(member_tokens["access_token"])
    viewer_headers = authorization_headers(viewer_tokens["access_token"])
    task = client.post(
        f"/api/v1/projects/{project['id']}/tasks",
        json={"title": "Review comments"},
        headers=member_headers,
    ).json()

    comment = client.post(
        f"/api/v1/tasks/{task['id']}/comments",
        json={"body": "The endpoint is ready for review."},
        headers=member_headers,
    )
    assert comment.status_code == 201

    viewer_comment = client.post(
        f"/api/v1/tasks/{task['id']}/comments",
        json={"body": "Viewer cannot comment."},
        headers=viewer_headers,
    )
    assert viewer_comment.status_code == 403

    listing = client.get(
        f"/api/v1/tasks/{task['id']}/comments?limit=1&offset=0",
        headers=viewer_headers,
    )
    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    updated = client.patch(
        f"/api/v1/comments/{comment.json()['id']}",
        json={"body": "Updated review note."},
        headers=member_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["body"] == "Updated review note."

    deleted = client.delete(
        f"/api/v1/comments/{comment.json()['id']}",
        headers=member_headers,
    )
    assert deleted.status_code == 204


def test_viewer_cannot_create_tasks_or_projects(client: TestClient) -> None:
    workspace = setup_workspace(client)
    organization = workspace["organization"]
    project = workspace["project"]
    viewer_tokens = workspace["viewer_tokens"]
    headers = authorization_headers(viewer_tokens["access_token"])

    project_response = client.post(
        f"/api/v1/organizations/{organization['id']}/projects",
        json={"name": "Forbidden Project"},
        headers=headers,
    )
    task_response = client.post(
        f"/api/v1/projects/{project['id']}/tasks",
        json={"title": "Forbidden Task"},
        headers=headers,
    )

    assert project_response.status_code == 403
    assert task_response.status_code == 403


def test_removing_member_clears_organization_task_assignments(
    client: TestClient,
) -> None:
    workspace = setup_workspace(client)
    owner_tokens = workspace["owner_tokens"]
    member = workspace["member"]
    member_tokens = workspace["member_tokens"]
    organization = workspace["organization"]
    project = workspace["project"]
    member_headers = authorization_headers(member_tokens["access_token"])
    owner_headers = authorization_headers(owner_tokens["access_token"])
    task = client.post(
        f"/api/v1/projects/{project['id']}/tasks",
        json={"title": "Assigned task", "assignee_ids": [member["id"]]},
        headers=member_headers,
    ).json()

    removed = client.delete(
        f"/api/v1/organizations/{organization['id']}/members/{member['id']}",
        headers=owner_headers,
    )
    retrieved = client.get(
        f"/api/v1/tasks/{task['id']}",
        headers=owner_headers,
    )

    assert removed.status_code == 204
    assert retrieved.status_code == 200
    assert retrieved.json()["assignees"] == []


def test_label_crud_and_cross_organization_protection(client: TestClient) -> None:
    workspace = setup_workspace(client)
    owner_tokens = workspace["owner_tokens"]
    organization = workspace["organization"]
    project = workspace["project"]
    label = workspace["label"]
    headers = authorization_headers(owner_tokens["access_token"])

    listed = client.get(
        f"/api/v1/organizations/{organization['id']}/labels",
        headers=headers,
    )
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == label["id"]

    updated = client.patch(
        f"/api/v1/labels/{label['id']}",
        json={"name": "API", "color": "#112233"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "API"

    duplicate = client.post(
        f"/api/v1/organizations/{organization['id']}/labels",
        json={"name": "API", "color": "#445566"},
        headers=headers,
    )
    assert duplicate.status_code == 409

    other_organization = create_organization(
        client, owner_tokens["access_token"], "Other Organization"
    )
    other_label = client.post(
        f"/api/v1/organizations/{other_organization['id']}/labels",
        json={"name": "Other", "color": "#ABCDEF"},
        headers=headers,
    ).json()
    task = client.post(
        f"/api/v1/projects/{project['id']}/tasks",
        json={"title": "Cross-tenant label test"},
        headers=headers,
    ).json()
    cross_tenant = client.put(
        f"/api/v1/tasks/{task['id']}/labels/{other_label['id']}",
        headers=headers,
    )
    assert cross_tenant.status_code == 404

    deleted = client.delete(f"/api/v1/labels/{label['id']}", headers=headers)
    assert deleted.status_code == 204


def test_task_and_project_deletion_permissions(client: TestClient) -> None:
    workspace = setup_workspace(client)
    owner_tokens = workspace["owner_tokens"]
    member_tokens = workspace["member_tokens"]
    project = workspace["project"]
    owner_headers = authorization_headers(owner_tokens["access_token"])
    member_headers = authorization_headers(member_tokens["access_token"])
    task = client.post(
        f"/api/v1/projects/{project['id']}/tasks",
        json={"title": "Delete me"},
        headers=member_headers,
    ).json()

    member_project_delete = client.delete(
        f"/api/v1/projects/{project['id']}",
        headers=member_headers,
    )
    assert member_project_delete.status_code == 403

    task_delete = client.delete(
        f"/api/v1/tasks/{task['id']}",
        headers=member_headers,
    )
    assert task_delete.status_code == 204

    project_delete = client.delete(
        f"/api/v1/projects/{project['id']}",
        headers=owner_headers,
    )
    assert project_delete.status_code == 204
