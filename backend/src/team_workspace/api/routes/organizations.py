from uuid import UUID

from fastapi import APIRouter, Query, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from team_workspace.dependencies import (
    CurrentUser,
    SessionDep,
    membership_for,
    require_role,
)
from team_workspace.errors import AppError
from team_workspace.models import (
    Membership,
    Organization,
    OrganizationRole,
    Project,
    Task,
    TaskAssignee,
    User,
)
from team_workspace.schemas import (
    MembershipCreate,
    MembershipPublic,
    MembershipUpdate,
    OrganizationCreate,
    OrganizationPublic,
    OrganizationUpdate,
    Page,
    UserSummary,
)
from team_workspace.services import can_manage_role, slugify

router = APIRouter(prefix="/organizations", tags=["organizations"])


def organization_public(
    organization: Organization,
    role: OrganizationRole,
) -> OrganizationPublic:
    return OrganizationPublic(
        id=organization.id,
        name=organization.name,
        slug=organization.slug,
        created_by_id=organization.created_by_id,
        created_at=organization.created_at,
        updated_at=organization.updated_at,
        current_user_role=role,
    )


def membership_public(membership: Membership, user: User) -> MembershipPublic:
    return MembershipPublic(
        organization_id=membership.organization_id,
        user=UserSummary.model_validate(user),
        role=membership.role,
        created_at=membership.created_at,
    )


@router.post("", response_model=OrganizationPublic, status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: OrganizationCreate,
    session: SessionDep,
    user: CurrentUser,
) -> OrganizationPublic:
    organization = Organization(
        name=payload.name.strip(),
        slug=slugify(payload.slug or payload.name),
        created_by_id=user.id,
    )
    session.add(organization)
    try:
        await session.flush()
        session.add(
            Membership(
                organization_id=organization.id,
                user_id=user.id,
                role=OrganizationRole.OWNER,
            )
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(
            409, "slug_already_exists", "The organization slug is in use."
        ) from exc
    await session.refresh(organization)
    return organization_public(organization, OrganizationRole.OWNER)


@router.get("", response_model=Page[OrganizationPublic])
async def list_organizations(
    session: SessionDep,
    user: CurrentUser,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Page[OrganizationPublic]:
    base_query = (
        select(Organization, Membership.role)
        .join(Membership, Membership.organization_id == Organization.id)
        .where(Membership.user_id == user.id)
    )
    total = await session.scalar(
        select(func.count()).select_from(base_query.subquery())
    )
    rows = (
        await session.execute(
            base_query.order_by(Organization.name).limit(limit).offset(offset)
        )
    ).all()
    return Page(
        items=[organization_public(organization, role) for organization, role in rows],
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@router.get("/{organization_id}", response_model=OrganizationPublic)
async def get_organization(
    organization_id: UUID,
    session: SessionDep,
    user: CurrentUser,
) -> OrganizationPublic:
    membership = await membership_for(session, organization_id, user.id)
    organization = await session.get(Organization, organization_id)
    if organization is None:
        raise AppError(404, "organization_not_found", "Organization not found.")
    return organization_public(organization, membership.role)


@router.patch("/{organization_id}", response_model=OrganizationPublic)
async def update_organization(
    organization_id: UUID,
    payload: OrganizationUpdate,
    session: SessionDep,
    user: CurrentUser,
) -> OrganizationPublic:
    membership = await require_role(
        session, organization_id, user.id, OrganizationRole.ADMIN
    )
    organization = await session.get(Organization, organization_id)
    if organization is None:
        raise AppError(404, "organization_not_found", "Organization not found.")
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes:
        organization.name = changes["name"].strip()
    if "slug" in changes:
        organization.slug = slugify(changes["slug"])
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(
            409, "slug_already_exists", "The organization slug is in use."
        ) from exc
    await session.refresh(organization)
    return organization_public(organization, membership.role)


@router.delete("/{organization_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization(
    organization_id: UUID,
    session: SessionDep,
    user: CurrentUser,
) -> Response:
    await require_role(session, organization_id, user.id, OrganizationRole.OWNER)
    organization = await session.get(Organization, organization_id)
    if organization is None:
        raise AppError(404, "organization_not_found", "Organization not found.")
    await session.delete(organization)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{organization_id}/members", response_model=Page[MembershipPublic])
async def list_members(
    organization_id: UUID,
    session: SessionDep,
    user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Page[MembershipPublic]:
    await membership_for(session, organization_id, user.id)
    base_query = (
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.organization_id == organization_id)
    )
    total = await session.scalar(
        select(func.count()).select_from(base_query.subquery())
    )
    rows = (
        await session.execute(
            base_query.order_by(User.full_name).limit(limit).offset(offset)
        )
    ).all()
    return Page(
        items=[membership_public(membership, member) for membership, member in rows],
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/{organization_id}/members",
    response_model=MembershipPublic,
    status_code=status.HTTP_201_CREATED,
)
async def add_member(
    organization_id: UUID,
    payload: MembershipCreate,
    session: SessionDep,
    user: CurrentUser,
) -> MembershipPublic:
    actor = await require_role(
        session, organization_id, user.id, OrganizationRole.ADMIN
    )
    if not can_manage_role(actor.role, payload.role):
        raise AppError(403, "role_not_assignable", "You cannot assign this role.")
    member = await session.scalar(
        select(User).where(User.email == str(payload.email).lower())
    )
    if member is None:
        raise AppError(404, "user_not_found", "No registered user has this email.")
    if await session.get(Membership, (organization_id, member.id)) is not None:
        raise AppError(409, "membership_exists", "The user is already a member.")
    membership = Membership(
        organization_id=organization_id,
        user_id=member.id,
        role=payload.role,
    )
    session.add(membership)
    await session.commit()
    await session.refresh(membership)
    return membership_public(membership, member)


async def ensure_owner_remains(
    session: SessionDep,
    organization_id: UUID,
    membership: Membership,
    next_role: OrganizationRole | None,
) -> None:
    if membership.role != OrganizationRole.OWNER or next_role == OrganizationRole.OWNER:
        return
    owner_count = await session.scalar(
        select(func.count()).where(
            Membership.organization_id == organization_id,
            Membership.role == OrganizationRole.OWNER,
        )
    )
    if (owner_count or 0) <= 1:
        raise AppError(
            409, "last_owner", "An organization must keep at least one owner."
        )


@router.patch("/{organization_id}/members/{member_id}", response_model=MembershipPublic)
async def update_member(
    organization_id: UUID,
    member_id: UUID,
    payload: MembershipUpdate,
    session: SessionDep,
    user: CurrentUser,
) -> MembershipPublic:
    actor = await require_role(
        session, organization_id, user.id, OrganizationRole.ADMIN
    )
    membership = await session.get(Membership, (organization_id, member_id))
    member = await session.get(User, member_id)
    if membership is None or member is None:
        raise AppError(404, "membership_not_found", "Membership not found.")
    if not can_manage_role(actor.role, membership.role) or not can_manage_role(
        actor.role, payload.role
    ):
        raise AppError(403, "role_not_assignable", "You cannot manage this role.")
    await ensure_owner_remains(session, organization_id, membership, payload.role)
    membership.role = payload.role
    await session.commit()
    await session.refresh(membership)
    return membership_public(membership, member)


@router.delete(
    "/{organization_id}/members/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_member(
    organization_id: UUID,
    member_id: UUID,
    session: SessionDep,
    user: CurrentUser,
) -> Response:
    actor = await require_role(
        session, organization_id, user.id, OrganizationRole.ADMIN
    )
    membership = await session.get(Membership, (organization_id, member_id))
    if membership is None:
        raise AppError(404, "membership_not_found", "Membership not found.")
    if not can_manage_role(actor.role, membership.role):
        raise AppError(403, "role_not_assignable", "You cannot remove this role.")
    await ensure_owner_remains(session, organization_id, membership, None)
    organization_task_ids = (
        select(Task.id).join(Project).where(Project.organization_id == organization_id)
    )
    await session.execute(
        delete(TaskAssignee).where(
            TaskAssignee.user_id == member_id,
            TaskAssignee.task_id.in_(organization_task_ids),
        )
    )
    await session.delete(membership)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
