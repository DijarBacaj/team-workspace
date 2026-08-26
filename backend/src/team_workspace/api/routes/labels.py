from uuid import UUID

from fastapi import APIRouter, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from team_workspace.dependencies import (
    CurrentUser,
    SessionDep,
    require_role,
    task_for_user,
)
from team_workspace.errors import AppError
from team_workspace.models import Label, OrganizationRole, TaskLabel
from team_workspace.schemas import LabelCreate, LabelPublic, LabelUpdate, TaskPublic
from team_workspace.services import task_public

router = APIRouter(tags=["labels"])


@router.post(
    "/organizations/{organization_id}/labels",
    response_model=LabelPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_label(
    organization_id: UUID,
    payload: LabelCreate,
    session: SessionDep,
    user: CurrentUser,
) -> Label:
    await require_role(session, organization_id, user.id, OrganizationRole.ADMIN)
    label = Label(
        organization_id=organization_id,
        name=payload.name.strip(),
        color=payload.color.upper(),
    )
    session.add(label)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(
            409,
            "label_name_exists",
            "A label with this name already exists in the organization.",
        ) from exc
    await session.refresh(label)
    return label


@router.get("/organizations/{organization_id}/labels", response_model=list[LabelPublic])
async def list_labels(
    organization_id: UUID,
    session: SessionDep,
    user: CurrentUser,
) -> list[Label]:
    await require_role(session, organization_id, user.id, OrganizationRole.VIEWER)
    return list(
        (
            await session.scalars(
                select(Label)
                .where(Label.organization_id == organization_id)
                .order_by(Label.name)
            )
        ).all()
    )


@router.patch("/labels/{label_id}", response_model=LabelPublic)
async def update_label(
    label_id: UUID,
    payload: LabelUpdate,
    session: SessionDep,
    user: CurrentUser,
) -> Label:
    label = await session.get(Label, label_id)
    if label is None:
        raise AppError(404, "label_not_found", "Label not found.")
    await require_role(session, label.organization_id, user.id, OrganizationRole.ADMIN)
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes:
        label.name = changes["name"].strip()
    if "color" in changes:
        label.color = changes["color"].upper()
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(
            409,
            "label_name_exists",
            "A label with this name already exists in the organization.",
        ) from exc
    await session.refresh(label)
    return label


@router.delete("/labels/{label_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_label(
    label_id: UUID,
    session: SessionDep,
    user: CurrentUser,
) -> Response:
    label = await session.get(Label, label_id)
    if label is None:
        raise AppError(404, "label_not_found", "Label not found.")
    await require_role(session, label.organization_id, user.id, OrganizationRole.ADMIN)
    await session.delete(label)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/tasks/{task_id}/labels/{label_id}", response_model=TaskPublic)
async def attach_label(
    task_id: UUID,
    label_id: UUID,
    session: SessionDep,
    user: CurrentUser,
) -> TaskPublic:
    task, project, _ = await task_for_user(
        session, task_id, user.id, OrganizationRole.MEMBER
    )
    label = await session.get(Label, label_id)
    if label is None or label.organization_id != project.organization_id:
        raise AppError(404, "label_not_found", "Label not found.")
    if await session.get(TaskLabel, (task.id, label.id)) is None:
        session.add(TaskLabel(task_id=task.id, label_id=label.id))
        await session.commit()
    return await task_public(session, task)


@router.delete("/tasks/{task_id}/labels/{label_id}", response_model=TaskPublic)
async def detach_label(
    task_id: UUID,
    label_id: UUID,
    session: SessionDep,
    user: CurrentUser,
) -> TaskPublic:
    task, _, _ = await task_for_user(session, task_id, user.id, OrganizationRole.MEMBER)
    task_label = await session.get(TaskLabel, (task.id, label_id))
    if task_label is not None:
        await session.delete(task_label)
        await session.commit()
    return await task_public(session, task)
