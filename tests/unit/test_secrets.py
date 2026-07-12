"""Unit tests for Secrets Manager runtime loader (FDS-25)."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

import src.shared.config.secrets as secrets


@pytest.fixture(autouse=True)
def _clear_cache():
    """Ensure the module-level cache is empty before each test."""
    secrets._secret_cache = None


class TestGetServiceSecret:
    def test_returns_empty_dict_when_arn_unset(self, monkeypatch):
        monkeypatch.delenv("SERVICE_SECRET_ARN", raising=False)
        result = secrets.get_service_secret()
        assert result == {}

    def test_parses_json_secret_and_returns_dict(self, monkeypatch):
        monkeypatch.setenv("SERVICE_SECRET_ARN", "arn:aws:secretsmanager:eu-west-1:123456789:secret:test")
        secret_body = {"SUPABASE_URL": "https://db.example.com", "SUPABASE_SERVICE_ROLE_KEY": "sk-xyz"}

        with patch("boto3.client") as mock_boto:
            mock_client = mock_boto.return_value
            mock_client.get_secret_value.return_value = {"SecretString": json.dumps(secret_body)}
            result = secrets.get_service_secret()

        assert result == secret_body

    def test_caches_secret_so_client_called_once(self, monkeypatch):
        monkeypatch.setenv("SERVICE_SECRET_ARN", "arn:aws:secretsmanager:eu-west-1:123456789:secret:test")
        secret_body = {"KEY": "value"}

        with patch("boto3.client") as mock_boto:
            mock_client = mock_boto.return_value
            mock_client.get_secret_value.return_value = {"SecretString": json.dumps(secret_body)}

            secrets.get_service_secret()
            secrets.get_service_secret()  # second call – should use cache

            # boto3 client should have been created exactly once across both calls
            assert mock_boto.call_count == 1
            # get_secret_value should also have been called exactly once
            assert mock_client.get_secret_value.call_count == 1

    def test_raises_runtime_error_on_failure(self, monkeypatch):
        monkeypatch.setenv("SERVICE_SECRET_ARN", "arn:aws:secretsmanager:eu-west-1:123456789:secret:test")

        with patch("boto3.client") as mock_boto:
            mock_client = mock_boto.return_value
            mock_client.get_secret_value.side_effect = Exception("boom")

            with pytest.raises(RuntimeError, match="Failed to load service secret"):
                secrets.get_service_secret()

    def test_empty_secret_string_parsed_as_empty_dict(self, monkeypatch):
        monkeypatch.setenv("SERVICE_SECRET_ARN", "arn:aws:secretsmanager:eu-west-1:123456789:secret:test")

        with patch("boto3.client") as mock_boto:
            mock_client = mock_boto.return_value
            mock_client.get_secret_value.return_value = {}
            result = secrets.get_service_secret()

        assert result == {}
