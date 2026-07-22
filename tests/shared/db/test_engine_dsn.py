"""Hermetic tests for the _dsn() function (FDS-30).

No network, no real AWS/DB — all secret and env reads are monkey-patched.
"""

from __future__ import annotations

from unittest import mock

import pytest

import src.shared.db.engine as engine


class TestDsnFromDatabaseUrl:
    """When database_url (secret) or DATABASE_URL (env) is set, skip DB_* fallback."""

    @mock.patch.object(engine, "get_service_secret", return_value={})
    @mock.patch.dict("os.environ", {"DATABASE_URL": "postgresql://env"}, clear=True)
    def test_env_var_wins_when_secret_empty(self, _mock_secret):
        assert engine._dsn() == "postgresql://env"

    @mock.patch.object(
        engine,
        "get_service_secret",
        return_value={"database_url": "postgresql://secret"},
    )
    @mock.patch.dict("os.environ", {}, clear=True)
    def test_secret_wins_when_both_set(self, _mock_secret):
        assert engine._dsn() == "postgresql://secret"

    @mock.patch.object(
        engine,
        "get_service_secret",
        return_value={"database_url": "postgresql://secret"},
    )
    @mock.patch.dict("os.environ", {"DATABASE_URL": "postgresql://env"}, clear=True)
    def test_secret_takes_precedence_over_env(self, _mock_secret):
        assert engine._dsn() == "postgresql://secret"


class TestDsnFromDbFields:
    """When no database_url is available, assemble from DB_* fields."""

    @mock.patch.object(
        engine,
        "get_service_secret",
        return_value={
            "DB_HOST": "db.example.com",
            "DB_USER": "u$er",
            "DB_PASS": "p@ss:word",
            "DB_NAME": "orders",
            "DB_PORT": "5439",
        },
    )
    @mock.patch.dict("os.environ", {}, clear=True)
    def test_all_fields_from_secret(self, _mock_secret):
        dsn = engine._dsn()
        assert "db.example.com" in dsn
        assert "orders" in dsn
        assert "5439" in dsn
        # quote_plus encodes special chars
        assert "u%24er" in dsn
        assert "p%40ss%3Aword" in dsn

    @mock.patch.object(engine, "get_service_secret", return_value={})
    @mock.patch.dict(
        "os.environ",
        {
            "DB_HOST": "db.env.com",
            "DB_USER": "envuser",
            "DB_PASS": "envpass",
            "DB_NAME": "envdb",
        },
        clear=True,
    )
    def test_all_fields_from_env(self, _mock_secret):
        dsn = engine._dsn()
        assert "db.env.com" in dsn
        assert "envuser" in dsn
        assert "envpass" in dsn
        assert "envdb" in dsn
        # default port
        assert "5432" in dsn

    @mock.patch.object(
        engine,
        "get_service_secret",
        return_value={"DB_HOST": "secret.host", "DB_USER": "secuser"},
    )
    @mock.patch.dict(
        "os.environ",
        {"DB_PASS": "envpass", "DB_NAME": "envdb"},
        clear=True,
    )
    def test_mixed_secret_and_env(self, _mock_secret):
        dsn = engine._dsn()
        assert "secret.host" in dsn
        assert "secuser" in dsn
        assert "envpass" in dsn
        assert "envdb" in dsn
        assert "5432" in dsn

    @mock.patch.object(
        engine,
        "get_service_secret",
        return_value={
            "database_url": "postgresql://secret-url",
            "DB_HOST": "secret.host",
            "DB_USER": "secuser",
            "DB_PASS": "secpass",
            "DB_NAME": "secdb",
        },
    )
    @mock.patch.dict("os.environ", {}, clear=True)
    def test_database_url_skips_fields_even_when_both_present(self, _mock_secret):
        assert engine._dsn() == "postgresql://secret-url"


class TestDsnMissing:
    """When nothing is configured, raise RuntimeError."""

    @mock.patch.object(engine, "get_service_secret", return_value={})
    @mock.patch.dict("os.environ", {}, clear=True)
    def test_no_config_raises(self, _mock_secret):
        with pytest.raises(RuntimeError, match="DATABASE_URL not configured"):
            engine._dsn()

    @mock.patch.object(
        engine,
        "get_service_secret",
        return_value={"DB_HOST": "h", "DB_NAME": "n"},
    )
    @mock.patch.dict("os.environ", {}, clear=True)
    def test_partial_db_fields_raises(self, _mock_secret):
        with pytest.raises(RuntimeError, match="DATABASE_URL not configured"):
            engine._dsn()
