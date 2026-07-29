"""Unit tests for src.shared.config.env.get_required_env (FDS-42)."""

from __future__ import annotations

import pytest

from src.shared.config.env import get_required_env
from src.shared.errors.app_error import AppError


def test_get_required_env_returns_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MY_VAR", "hello")
    assert get_required_env("MY_VAR") == "hello"


def test_get_required_env_raises_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MY_VAR", raising=False)
    with pytest.raises(AppError) as exc:
        get_required_env("MY_VAR")
    assert exc.value.status_code == 500
    assert exc.value.code == "CONFIGURATION_ERROR"


def test_get_required_env_raises_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MY_VAR", "")
    with pytest.raises(AppError) as exc:
        get_required_env("MY_VAR")
    assert exc.value.status_code == 500
    assert exc.value.code == "CONFIGURATION_ERROR"


def test_get_required_env_raises_when_whitespace(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MY_VAR", "   ")
    with pytest.raises(AppError) as exc:
        get_required_env("MY_VAR")
    assert exc.value.status_code == 500
    assert exc.value.code == "CONFIGURATION_ERROR"
