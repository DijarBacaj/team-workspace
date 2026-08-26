from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query, Response, status
from sqlalchemy import asc, desc, func, select
from sqlalchemy.exc import IntegrityError

from team_workspace.dependencies import (
    CurrentUser,
    SessionDep,
    project_for_user,
    require_role,
)
from team_workspace.errors import AppError
from team_workspace.models import OrganizationRole, Project, ProjectStatus
from team_workspace.schemas import Page, ProjectCreate, ProjectPublic, ProjectUpdate

router = APIRouter(tags=["projects"])


@router.post(
    "/organizations/{organization_id}/projects",
    response_model=ProjectPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    organization_id: UUID,
    payload: ProjectCreate,
    session: SessionDep,
    user: CurrentUser,
) -> Project:
    await require_role(session, organization_id, user.id, OrganizationRole.ADMIN)
    project = Project(
        organization_id=organization_id,
        name=payload.name.strip(),
        description=payload.description,
        created_by_id=user.id,
    )
    session.add(project)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(
            409,
            "project_name_exists",
            "A project with this name already exists in the organization.",
        ) from exc
    await session.refresh(project)
    return project


@router.get(
    "/organizations/{organization_id}/projects", response_model=Page[ProjectPublic]
)
async def list_projects(
    organization_id: UUID,
    session: SessionDep,
    user: CurrentUser,
    search: str | None = Query(default=None, max_length=100),
    project_status: ProjectStatus | None = Query(default=None, alias="status"),
    sort_by: Literal["name", "created_at", "updated_at"] = "created_at",
    sort_direction: Literal["asc", "desc"] = "desc",
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Page[ProjectPublic]:
    await require_role(session, organization_id, user.id, OrganizationRole.VIEWER)
    query = select(Project).where(Project.organization_id == organization_id)
    if search:
        query = query.where(Project.name.ilike(f"%{search.strip()}%"))
    if project_status:
        query = query.where(Project.status == project_status)
    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    sort_column = {
        "name": Project.name,
        "created_at": Project.created_at,
        "updated_at": Project.updated_at,
    }[sort_by]
    sort_expression = asc(sort_column) if sort_direction == "asc" else desc(sort_column)
    projects = (
        await session.scalars(
            query.order_by(sort_expression, Project.id).limit(limit).offset(offset)
        )
    ).all()
    return Page(
        items=[ProjectPublic.model_validate(project) for project in projects],
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@router.get("/projects/{project_id}", response_model=ProjectPublic)
async def get_project(
    project_id: UUID,
    session: SessionDep,
    user: CurrentUser,
) -> Project:
    project, _ = await project_for_user(session, project_id, user.id)
    return project


@router.patch("/projects/{project_id}", response_model=ProjectPublic)
async def update_project(
    project_id: UUID,
    payload: ProjectUpdate,
    session: SessionDep,
    user: CurrentUser,
) -> Project:
    project, _ = await project_for_user(
        session, project_id, user.id, OrganizationRole.ADMIN
    )
    for field_name, value in payload.model_dump(exclude_unset=True).items():
        if field_name == "name" and value is not None:
            value = value.strip()
        setattr(project, field_name, value)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(
            409,
            "project_name_exists",
            "A project with this name already exists in the organization.",
        ) from exc
    await session.refresh(project)
    return project


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    session: SessionDep,
    user: CurrentUser,
) -> Response:
    project, _ = await project_for_user(
        session, project_id, user.id, OrganizationRole.ADMIN
    )
    await session.delete(project)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
