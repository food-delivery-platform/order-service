"""Unit tests for env credential hydration from Secrets Manager (FDS-25)."""

from __future__ import annotations

import importlib
import json
from unittest.mock import patch

import src.shared.config.env as env_module
import src.shared.config.secrets as secrets_module


def _clear_secrets_cache():
    """Reset the module-level secret cache before each test."""
    secrets_module._secret_cache = None


class TestHydrateFromSecret:
    def test_env_value_used_when_secret_missing(self, monkeypatch):
        """Plain env is used when SERVICE_SECRET_ARN is unset (secret = {})."""
        monkeypatch.delenv("SERVICE_SECRET_ARN", raising=False)
        monkeypatch.setenv("SUPABASE_URL", "https://env.example.com")

        _clear_secrets_cache()
        importlib.reload(env_module)
        assert env_module.SUPABASE_URL == "https://env.example.com"

    def test_secret_value_wins_over_env(self, monkeypatch):
        """Secret value takes priority over plain env."""
        monkeypatch.setenv("SERVICE_SECRET_ARN", "arn:aws:secretsmanager:eu-west-1:123456789:secret:test")
        monkeypatch.setenv("SUPABASE_URL", "https://env.example.com")

        _clear_secrets_cache()

        with patch("boto3.client") as mock_boto:
            mock_client = mock_boto.return_value
            mock_client.get_secret_value.return_value = {
                "SecretString": json.dumps({"SUPABASE_URL": "https://secret.example.com"})
            }
            importlib.reload(env_module)

        assert env_module.SUPABASE_URL == "https://secret.example.com"

    def test_env_fallback_when_key_not_in_secret(self, monkeypatch):
        """When the secret doesn't have the key, env is used as fallback."""
        monkeypatch.setenv("SERVICE_SECRET_ARN", "arn:aws:secretsmanager:eu-west-1:123456789:secret:test")
        monkeypatch.setenv("SUPABASE_URL", "https://env.example.com")

        _clear_secrets_cache()

        with patch("boto3.client") as mock_boto:
            mock_client = mock_boto.return_value
            mock_client.get_secret_value.return_value = {
                "SecretString": json.dumps({"OTHER_KEY": "other_value"})
            }
            importlib.reload(env_module)

        assert env_module.SUPABASE_URL == "https://env.example.com"

    def test_none_returned_when_neither_source_has_key(self, monkeypatch):
        """Returns None when the key is missing from both secret and env."""
        monkeypatch.delenv("SERVICE_SECRET_ARN", raising=False)
        monkeypatch.delenv("SUPABASE_URL", raising=False)

        _clear_secrets_cache()
        importlib.reload(env_module)
        assert env_module.SUPABASE_URL is None

    def test_empty_string_in_secret_is_not_overridden_by_env(self, monkeypatch):
        """Empty string in secret should be used as-is, not fall through to env."""
        monkeypatch.setenv("SERVICE_SECRET_ARN", "arn:aws:secretsmanager:eu-west-1:123456789:secret:test")
        monkeypatch.setenv("SUPABASE_URL", "https://env.example.com")

        _clear_secrets_cache()

        with patch("boto3.client") as mock_boto:
            mock_client = mock_boto.return_value
            mock_client.get_secret_value.return_value = {
                "SecretString": json.dumps({"SUPABASE_URL": ""})
            }
            importlib.reload(env_module)

        assert env_module.SUPABASE_URL == ""
