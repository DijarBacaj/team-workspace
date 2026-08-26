from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from team_workspace.database import get_db_session
from team_workspace.errors import AppError
from team_workspace.models import Membership, OrganizationRole, Project, Task, User
from team_workspace.security import decode_token, token_subject

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
bearer_scheme = HTTPBearer(auto_error=False)

ROLE_RANK = {
    OrganizationRole.VIEWER: 0,
    OrganizationRole.MEMBER: 1,
    OrganizationRole.ADMIN: 2,
    OrganizationRole.OWNER: 3,
}


async def get_current_user(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if credentials is None:
        raise AppError(401, "authentication_required", "Authentication is required.")
    payload = decode_token(credentials.credentials, "access")
    user = await session.get(User, token_subject(payload))
    if user is None or not user.is_active:
        raise AppError(401, "invalid_user", "The authenticated user is unavailable.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def membership_for(
    session: AsyncSession,
    organization_id: UUID,
    user_id: UUID,
) -> Membership:
    membership = await session.get(Membership, (organization_id, user_id))
    if membership is None:
        raise AppError(404, "organization_not_found", "Organization not found.")
    return membership


async def require_role(
    session: AsyncSession,
    organization_id: UUID,
    user_id: UUID,
    minimum_role: OrganizationRole,
) -> Membership:
    membership = await membership_for(session, organization_id, user_id)
    if ROLE_RANK[membership.role] < ROLE_RANK[minimum_role]:
        raise AppError(
            403,
            "insufficient_permissions",
            "You do not have permission to perform this action.",
        )
    return membership


async def project_for_user(
    session: AsyncSession,
    project_id: UUID,
    user_id: UUID,
    minimum_role: OrganizationRole = OrganizationRole.VIEWER,
) -> tuple[Project, Membership]:
    project = await session.get(Project, project_id)
    if project is None:
        raise AppError(404, "project_not_found", "Project not found.")
    membership = await require_role(
        session, project.organization_id, user_id, minimum_role
    )
    return project, membership


async def task_for_user(
    session: AsyncSession,
    task_id: UUID,
    user_id: UUID,
    minimum_role: OrganizationRole = OrganizationRole.VIEWER,
) -> tuple[Task, Project, Membership]:
    result = await session.execute(
        select(Task, Project)
        .join(Project, Project.id == Task.project_id)
        .where(Task.id == task_id)
    )
    row = result.one_or_none()
    if row is None:
        raise AppError(404, "task_not_found", "Task not found.")
    task, project = row
    membership = await require_role(
        session, project.organization_id, user_id, minimum_role
    )
    return task, project, membership
