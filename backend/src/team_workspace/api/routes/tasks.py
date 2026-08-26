from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query, Response, status
from sqlalchemy import asc, delete, desc, func, or_, select

from team_workspace.dependencies import (
    ROLE_RANK,
    CurrentUser,
    SessionDep,
    project_for_user,
    task_for_user,
)
from team_workspace.errors import AppError
from team_workspace.models import (
    OrganizationRole,
    Task,
    TaskAssignee,
    TaskLabel,
    TaskPriority,
    TaskStatus,
)
from team_workspace.schemas import Page, TaskCreate, TaskPublic, TaskUpdate
from team_workspace.services import (
    replace_task_assignees,
    replace_task_labels,
    task_public,
    validate_member_ids,
)

router = APIRouter(tags=["tasks"])


@router.post(
    "/projects/{project_id}/tasks",
    response_model=TaskPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_task(
    project_id: UUID,
    payload: TaskCreate,
    session: SessionDep,
    user: CurrentUser,
) -> TaskPublic:
    project, _ = await project_for_user(
        session, project_id, user.id, OrganizationRole.MEMBER
    )
    task = Task(
        project_id=project.id,
        title=payload.title.strip(),
        description=payload.description,
        priority=payload.priority,
        due_at=payload.due_at,
        created_by_id=user.id,
    )
    session.add(task)
    await session.flush()
    await replace_task_assignees(
        session, task.id, project.organization_id, payload.assignee_ids
    )
    await replace_task_labels(
        session, task.id, project.organization_id, payload.label_ids
    )
    await session.commit()
    await session.refresh(task)
    return await task_public(session, task)


@router.get("/projects/{project_id}/tasks", response_model=Page[TaskPublic])
async def list_tasks(
    project_id: UUID,
    session: SessionDep,
    user: CurrentUser,
    search: str | None = Query(default=None, max_length=100),
    task_status: TaskStatus | None = Query(default=None, alias="status"),
    priority: TaskPriority | None = None,
    assignee_id: UUID | None = None,
    label_id: UUID | None = None,
    sort_by: Literal["title", "created_at", "updated_at", "due_at"] = "created_at",
    sort_direction: Literal["asc", "desc"] = "desc",
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Page[TaskPublic]:
    await project_for_user(session, project_id, user.id)
    query = select(Task).where(Task.project_id == project_id)
    if search:
        term = f"%{search.strip()}%"
        query = query.where(or_(Task.title.ilike(term), Task.description.ilike(term)))
    if task_status:
        query = query.where(Task.status == task_status)
    if priority:
        query = query.where(Task.priority == priority)
    if assignee_id:
        query = query.join(TaskAssignee).where(TaskAssignee.user_id == assignee_id)
    if label_id:
        query = query.join(TaskLabel).where(TaskLabel.label_id == label_id)
    query = query.distinct()
    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    sort_column = {
        "title": Task.title,
        "created_at": Task.created_at,
        "updated_at": Task.updated_at,
        "due_at": Task.due_at,
    }[sort_by]
    sort_expression = asc(sort_column) if sort_direction == "asc" else desc(sort_column)
    tasks = (
        await session.scalars(
            query.order_by(sort_expression, Task.id).limit(limit).offset(offset)
        )
    ).all()
    return Page(
        items=[await task_public(session, task) for task in tasks],
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@router.get("/tasks/{task_id}", response_model=TaskPublic)
async def get_task(
    task_id: UUID,
    session: SessionDep,
    user: CurrentUser,
) -> TaskPublic:
    task, _, _ = await task_for_user(session, task_id, user.id)
    return await task_public(session, task)


@router.patch("/tasks/{task_id}", response_model=TaskPublic)
async def update_task(
    task_id: UUID,
    payload: TaskUpdate,
    session: SessionDep,
    user: CurrentUser,
) -> TaskPublic:
    task, project, _ = await task_for_user(
        session, task_id, user.id, OrganizationRole.MEMBER
    )
    changes = payload.model_dump(exclude_unset=True)
    assignee_ids = changes.pop("assignee_ids", None)
    label_ids = changes.pop("label_ids", None)
    for field_name, value in changes.items():
        if field_name == "title" and value is not None:
            value = value.strip()
        setattr(task, field_name, value)
    if assignee_ids is not None:
        await replace_task_assignees(
            session, task.id, project.organization_id, assignee_ids
        )
    if label_ids is not None:
        await replace_task_labels(session, task.id, project.organization_id, label_ids)
    await session.commit()
    await session.refresh(task)
    return await task_public(session, task)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: UUID,
    session: SessionDep,
    user: CurrentUser,
) -> Response:
    task, _, membership = await task_for_user(
        session, task_id, user.id, OrganizationRole.MEMBER
    )
    if (
        ROLE_RANK[membership.role] < ROLE_RANK[OrganizationRole.ADMIN]
        and task.created_by_id != user.id
    ):
        raise AppError(
            403,
            "insufficient_permissions",
            "Only the creator or an admin can delete this task.",
        )
    await session.delete(task)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/tasks/{task_id}/assignees/{assignee_id}", response_model=TaskPublic)
async def assign_user(
    task_id: UUID,
    assignee_id: UUID,
    session: SessionDep,
    user: CurrentUser,
) -> TaskPublic:
    task, project, _ = await task_for_user(
        session, task_id, user.id, OrganizationRole.MEMBER
    )
    await validate_member_ids(session, project.organization_id, [assignee_id])
    if await session.get(TaskAssignee, (task.id, assignee_id)) is None:
        session.add(TaskAssignee(task_id=task.id, user_id=assignee_id))
        await session.commit()
    return await task_public(session, task)


@router.delete("/tasks/{task_id}/assignees/{assignee_id}", response_model=TaskPublic)
async def unassign_user(
    task_id: UUID,
    assignee_id: UUID,
    session: SessionDep,
    user: CurrentUser,
) -> TaskPublic:
    task, _, _ = await task_for_user(session, task_id, user.id, OrganizationRole.MEMBER)
    await session.execute(
        delete(TaskAssignee).where(
            TaskAssignee.task_id == task.id,
            TaskAssignee.user_id == assignee_id,
        )
    )
    await session.commit()
    return await task_public(session, task)
