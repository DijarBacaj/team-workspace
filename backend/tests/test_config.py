from pathlib import Path

import pytest

from team_workspace.config import Settings


def test_settings_use_default_values(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)

    for variable_name in ("APP_NAME", "APP_ENVIRONMENT", "DEBUG"):
        monkeypatch.delenv(variable_name, raising=False)

    settings = Settings()

    assert settings.app_name == "Team Workspace API"
    assert settings.app_environment == "development"
    assert settings.debug is False


def test_settings_read_environment_variables(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APP_NAME", "Test Workspace API")
    monkeypatch.setenv("APP_ENVIRONMENT", "testing")
    monkeypatch.setenv("DEBUG", "true")

    settings = Settings()

    assert settings.app_name == "Test Workspace API"
    assert settings.app_environment == "testing"
    assert settings.debug is True
