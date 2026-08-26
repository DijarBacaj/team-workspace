from uuid import UUID

from fastapi import APIRouter, Query, Response, status
from sqlalchemy import func, select

from team_workspace.dependencies import (
    ROLE_RANK,
    CurrentUser,
    SessionDep,
    task_for_user,
)
from team_workspace.errors import AppError
from team_workspace.models import Comment, OrganizationRole, User
from team_workspace.schemas import (
    CommentCreate,
    CommentPublic,
    CommentUpdate,
    Page,
    UserSummary,
)

router = APIRouter(tags=["comments"])


def comment_public(comment: Comment, author: User) -> CommentPublic:
    return CommentPublic(
        id=comment.id,
        task_id=comment.task_id,
        author=UserSummary.model_validate(author),
        body=comment.body,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )


@router.post(
    "/tasks/{task_id}/comments",
    response_model=CommentPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_comment(
    task_id: UUID,
    payload: CommentCreate,
    session: SessionDep,
    user: CurrentUser,
) -> CommentPublic:
    await task_for_user(session, task_id, user.id, OrganizationRole.MEMBER)
    comment = Comment(task_id=task_id, author_id=user.id, body=payload.body.strip())
    session.add(comment)
    await session.commit()
    await session.refresh(comment)
    return comment_public(comment, user)


@router.get("/tasks/{task_id}/comments", response_model=Page[CommentPublic])
async def list_comments(
    task_id: UUID,
    session: SessionDep,
    user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Page[CommentPublic]:
    await task_for_user(session, task_id, user.id)
    total = await session.scalar(
        select(func.count()).select_from(Comment).where(Comment.task_id == task_id)
    )
    rows = (
        await session.execute(
            select(Comment, User)
            .join(User, User.id == Comment.author_id)
            .where(Comment.task_id == task_id)
            .order_by(Comment.created_at, Comment.id)
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return Page(
        items=[comment_public(comment, author) for comment, author in rows],
        total=total or 0,
        limit=limit,
        offset=offset,
    )


async def comment_context(
    session: SessionDep,
    comment_id: UUID,
    user: CurrentUser,
) -> tuple[Comment, User, OrganizationRole]:
    row = (
        await session.execute(
            select(Comment, User)
            .join(User, User.id == Comment.author_id)
            .where(Comment.id == comment_id)
        )
    ).one_or_none()
    if row is None:
        raise AppError(404, "comment_not_found", "Comment not found.")
    comment, author = row
    _, _, membership = await task_for_user(session, comment.task_id, user.id)
    return comment, author, membership.role


@router.patch("/comments/{comment_id}", response_model=CommentPublic)
async def update_comment(
    comment_id: UUID,
    payload: CommentUpdate,
    session: SessionDep,
    user: CurrentUser,
) -> CommentPublic:
    comment, author, role = await comment_context(session, comment_id, user)
    if (
        comment.author_id != user.id
        and ROLE_RANK[role] < ROLE_RANK[OrganizationRole.ADMIN]
    ):
        raise AppError(
            403,
            "insufficient_permissions",
            "Only the author or an admin can edit this comment.",
        )
    comment.body = payload.body.strip()
    await session.commit()
    await session.refresh(comment)
    return comment_public(comment, author)


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    comment_id: UUID,
    session: SessionDep,
    user: CurrentUser,
) -> Response:
    comment, _, role = await comment_context(session, comment_id, user)
    if (
        comment.author_id != user.id
        and ROLE_RANK[role] < ROLE_RANK[OrganizationRole.ADMIN]
    ):
        raise AppError(
            403,
            "insufficient_permissions",
            "Only the author or an admin can delete this comment.",
        )
    await session.delete(comment)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
