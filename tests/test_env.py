"""Unit tests for env config helpers (FDS-25, FDS-33)."""

from __future__ import annotations

import src.shared.config.env as env_module


class TestGet:
    def test_returns_value_when_set(self, monkeypatch):
        monkeypatch.setenv("TEST_KEY", "hello")
        assert env_module.get("TEST_KEY") == "hello"

    def test_returns_default_when_not_set(self, monkeypatch):
        monkeypatch.delenv("TEST_KEY", raising=False)
        assert env_module.get("TEST_KEY", "fallback") == "fallback"

    def test_returns_none_when_not_set_and_no_default(self, monkeypatch):
        monkeypatch.delenv("TEST_KEY", raising=False)
        assert env_module.get("TEST_KEY") is None

    def test_required_raises_when_not_set(self, monkeypatch):
        monkeypatch.delenv("TEST_KEY", raising=False)
        try:
            env_module.get("TEST_KEY", required=True)
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "Missing required environment variable: TEST_KEY" in str(e)

    def test_required_does_not_raise_when_set(self, monkeypatch):
        monkeypatch.setenv("TEST_KEY", "value")
        assert env_module.get("TEST_KEY", required=True) == "value"


class TestConstants:
    def test_order_status_table_name_default(self, monkeypatch):
        monkeypatch.delenv("ORDER_STATUS_TABLE_NAME", raising=False)
        import importlib

        importlib.reload(env_module)
        assert env_module.ORDER_STATUS_TABLE_NAME == "order-status-live"

    def test_aws_region_default(self, monkeypatch):
        monkeypatch.delenv("AWS_REGION", raising=False)
        import importlib

        importlib.reload(env_module)
        assert env_module.AWS_REGION == "eu-west-1"
