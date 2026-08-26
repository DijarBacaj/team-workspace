import re
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from team_workspace.errors import AppError
from team_workspace.models import (
    Label,
    Membership,
    OrganizationRole,
    Task,
    TaskAssignee,
    TaskLabel,
    User,
)
from team_workspace.schemas import LabelPublic, TaskPublic, UserSummary


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if len(slug) < 2:
        raise AppError(422, "invalid_slug", "The organization slug is invalid.")
    return slug[:80]


async def validate_member_ids(
    session: AsyncSession,
    organization_id: UUID,
    user_ids: Sequence[UUID],
) -> None:
    unique_ids = set(user_ids)
    if not unique_ids:
        return
    result = await session.scalars(
        select(Membership.user_id).where(
            Membership.organization_id == organization_id,
            Membership.user_id.in_(unique_ids),
        )
    )
    if set(result.all()) != unique_ids:
        raise AppError(
            422,
            "invalid_assignees",
            "Every assignee must be an organization member.",
        )


async def validate_label_ids(
    session: AsyncSession,
    organization_id: UUID,
    label_ids: Sequence[UUID],
) -> None:
    unique_ids = set(label_ids)
    if not unique_ids:
        return
    result = await session.scalars(
        select(Label.id).where(
            Label.organization_id == organization_id,
            Label.id.in_(unique_ids),
        )
    )
    if set(result.all()) != unique_ids:
        raise AppError(
            422,
            "invalid_labels",
            "Every label must belong to the task organization.",
        )


async def replace_task_assignees(
    session: AsyncSession,
    task_id: UUID,
    organization_id: UUID,
    user_ids: Sequence[UUID],
) -> None:
    await validate_member_ids(session, organization_id, user_ids)
    await session.execute(delete(TaskAssignee).where(TaskAssignee.task_id == task_id))
    for user_id in set(user_ids):
        session.add(TaskAssignee(task_id=task_id, user_id=user_id))


async def replace_task_labels(
    session: AsyncSession,
    task_id: UUID,
    organization_id: UUID,
    label_ids: Sequence[UUID],
) -> None:
    await validate_label_ids(session, organization_id, label_ids)
    await session.execute(delete(TaskLabel).where(TaskLabel.task_id == task_id))
    for label_id in set(label_ids):
        session.add(TaskLabel(task_id=task_id, label_id=label_id))


async def task_public(session: AsyncSession, task: Task) -> TaskPublic:
    users = (
        await session.scalars(
            select(User)
            .join(TaskAssignee, TaskAssignee.user_id == User.id)
            .where(TaskAssignee.task_id == task.id)
            .order_by(User.full_name)
        )
    ).all()
    labels = (
        await session.scalars(
            select(Label)
            .join(TaskLabel, TaskLabel.label_id == Label.id)
            .where(TaskLabel.task_id == task.id)
            .order_by(Label.name)
        )
    ).all()
    return TaskPublic(
        id=task.id,
        project_id=task.project_id,
        title=task.title,
        description=task.description,
        status=task.status,
        priority=task.priority,
        due_at=task.due_at,
        created_by_id=task.created_by_id,
        created_at=task.created_at,
        updated_at=task.updated_at,
        assignees=[UserSummary.model_validate(user) for user in users],
        labels=[LabelPublic.model_validate(label) for label in labels],
    )


def can_manage_role(actor: OrganizationRole, target: OrganizationRole) -> bool:
    if target == OrganizationRole.OWNER:
        return actor == OrganizationRole.OWNER
    return actor in {OrganizationRole.OWNER, OrganizationRole.ADMIN}
