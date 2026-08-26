import asyncio
import os

from sqlalchemy import select

from team_workspace.database import session_factory
from team_workspace.models import (
    Label,
    Membership,
    Organization,
    OrganizationRole,
    Project,
    User,
)
from team_workspace.security import hash_password


async def seed_database() -> None:
    email = os.getenv("SEED_ADMIN_EMAIL", "admin@example.com").lower()
    password = os.getenv("SEED_ADMIN_PASSWORD")
    if not password:
        raise RuntimeError(
            "SEED_ADMIN_PASSWORD must be set before running the seed command."
        )

    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(
                email=email,
                full_name="Workspace Admin",
                password_hash=hash_password(password),
            )
            session.add(user)
            await session.flush()

        organization = await session.scalar(
            select(Organization).where(Organization.slug == "demo-workspace")
        )
        if organization is None:
            organization = Organization(
                name="Demo Workspace",
                slug="demo-workspace",
                created_by_id=user.id,
            )
            session.add(organization)
            await session.flush()
            session.add(
                Membership(
                    organization_id=organization.id,
                    user_id=user.id,
                    role=OrganizationRole.OWNER,
                )
            )
            session.add(
                Project(
                    organization_id=organization.id,
                    name="Launch Team Workspace",
                    description="Demo project created by the seed command.",
                    created_by_id=user.id,
                )
            )
            session.add_all(
                [
                    Label(
                        organization_id=organization.id,
                        name="Backend",
                        color="#2563EB",
                    ),
                    Label(
                        organization_id=organization.id,
                        name="Priority",
                        color="#DC2626",
                    ),
                ]
            )
        await session.commit()

    print(f"Seed completed for {email}.")


def main() -> None:
    asyncio.run(seed_database())


if __name__ == "__main__":
    main()
