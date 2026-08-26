import re
from datetime import datetime
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from team_workspace.models import (
    OrganizationRole,
    ProjectStatus,
    TaskPriority,
    TaskStatus,
)

T = TypeVar("T")


class APIModel(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
        str_strip_whitespace=True,
    )


class Page(APIModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class MessageResponse(APIModel):
    message: str


class UserRegister(APIModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        if not re.search(r"[a-z]", value):
            raise ValueError("Password must contain a lowercase letter.")
        if not re.search(r"[A-Z]", value):
            raise ValueError("Password must contain an uppercase letter.")
        if not re.search(r"\d", value):
            raise ValueError("Password must contain a number.")
        return value


class LoginRequest(APIModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(APIModel):
    refresh_token: str


class LogoutRequest(APIModel):
    refresh_token: str


class UserPublic(APIModel):
    id: UUID
    email: EmailStr
    full_name: str
    is_active: bool
    created_at: datetime


class UserSummary(APIModel):
    id: UUID
    email: EmailStr
    full_name: str


class TokenPair(APIModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class OrganizationCreate(APIModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str | None = Field(default=None, min_length=2, max_length=80)


class OrganizationUpdate(APIModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    slug: str | None = Field(default=None, min_length=2, max_length=80)

    @field_validator("name", "slug")
    @classmethod
    def reject_null_text(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("This field cannot be null.")
        return value


class OrganizationPublic(APIModel):
    id: UUID
    name: str
    slug: str
    created_by_id: UUID
    created_at: datetime
    updated_at: datetime
    current_user_role: OrganizationRole


class MembershipCreate(APIModel):
    email: EmailStr
    role: OrganizationRole = OrganizationRole.MEMBER


class MembershipUpdate(APIModel):
    role: OrganizationRole


class MembershipPublic(APIModel):
    organization_id: UUID
    user: UserSummary
    role: OrganizationRole
    created_at: datetime


class ProjectCreate(APIModel):
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=5000)


class ProjectUpdate(APIModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=5000)
    status: ProjectStatus | None = None

    @field_validator("name")
    @classmethod
    def reject_null_name(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("Project name cannot be null.")
        return value

    @field_validator("status")
    @classmethod
    def reject_null_status(cls, value: ProjectStatus | None) -> ProjectStatus:
        if value is None:
            raise ValueError("Project status cannot be null.")
        return value


class ProjectPublic(APIModel):
    id: UUID
    organization_id: UUID
    name: str
    description: str | None
    status: ProjectStatus
    created_by_id: UUID
    created_at: datetime
    updated_at: datetime


class LabelCreate(APIModel):
    name: str = Field(min_length=1, max_length=50)
    color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")


class LabelUpdate(APIModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")

    @field_validator("name", "color")
    @classmethod
    def reject_null_label_fields(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("This field cannot be null.")
        return value


class LabelPublic(APIModel):
    id: UUID
    organization_id: UUID
    name: str
    color: str
    created_at: datetime
    updated_at: datetime


class TaskCreate(APIModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    priority: TaskPriority = TaskPriority.MEDIUM
    due_at: datetime | None = None
    assignee_ids: list[UUID] = Field(default_factory=list)
    label_ids: list[UUID] = Field(default_factory=list)

    @field_validator("due_at")
    @classmethod
    def require_due_at_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("due_at must include a timezone offset.")
        return value


class TaskUpdate(APIModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_at: datetime | None = None
    assignee_ids: list[UUID] | None = None
    label_ids: list[UUID] | None = None

    @field_validator("title")
    @classmethod
    def reject_null_title(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("Task title cannot be null.")
        return value

    @field_validator("status")
    @classmethod
    def reject_null_task_status(cls, value: TaskStatus | None) -> TaskStatus:
        if value is None:
            raise ValueError("Task status cannot be null.")
        return value

    @field_validator("priority")
    @classmethod
    def reject_null_priority(cls, value: TaskPriority | None) -> TaskPriority:
        if value is None:
            raise ValueError("Task priority cannot be null.")
        return value

    @field_validator("assignee_ids", "label_ids")
    @classmethod
    def reject_null_collections(cls, value: list[UUID] | None) -> list[UUID]:
        if value is None:
            raise ValueError(
                "This field cannot be null; use an empty list to clear it."
            )
        return value

    @field_validator("due_at")
    @classmethod
    def require_due_at_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("due_at must include a timezone offset.")
        return value


class TaskPublic(APIModel):
    id: UUID
    project_id: UUID
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    due_at: datetime | None
    created_by_id: UUID
    created_at: datetime
    updated_at: datetime
    assignees: list[UserSummary]
    labels: list[LabelPublic]


class CommentCreate(APIModel):
    body: str = Field(min_length=1, max_length=5000)


class CommentUpdate(APIModel):
    body: str = Field(min_length=1, max_length=5000)


class CommentPublic(APIModel):
    id: UUID
    task_id: UUID
    author: UserSummary
    body: str
    created_at: datetime
    updated_at: datetime
