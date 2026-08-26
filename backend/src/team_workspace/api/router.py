from fastapi import APIRouter

from team_workspace.api.routes import (
    auth,
    comments,
    labels,
    organizations,
    projects,
    tasks,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(auth.users_router)
api_router.include_router(organizations.router)
api_router.include_router(projects.router)
api_router.include_router(tasks.router)
api_router.include_router(labels.router)
api_router.include_router(comments.router)
