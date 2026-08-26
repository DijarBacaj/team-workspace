from functools import lru_cache
from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Team Workspace API"
    app_environment: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    database_url: str = (
        "postgresql+psycopg://team_workspace:team_workspace@localhost:5432/"
        "team_workspace"
    )
    jwt_secret_key: str = Field(
        default="change-me-in-production-use-32-bytes",
        min_length=32,
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @model_validator(mode="after")
    def validate_production_secret(self) -> Self:
        placeholder_prefixes = ("change-me", "replace-with")
        if self.app_environment == "production" and self.jwt_secret_key.startswith(
            placeholder_prefixes
        ):
            raise ValueError("JWT_SECRET_KEY must be changed in production.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
