"""Hermetic unit tests for PayPal capture_order (FDS-32)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.shared.payments.paypal_client import PayPalClient, PayPalError

# Reuse autouse fixtures from the existing test_paypal_client.py pattern


@pytest.fixture(autouse=True)
def _clear_secret_cache():
    """Ensure the secret cache is empty so env vars are used."""
    import src.shared.config.secrets as secrets

    secrets._secret_cache = None


@pytest.fixture(autouse=True)
def _clear_service_secret_arn(monkeypatch):
    """Unset SERVICE_SECRET_ARN so we use env vars, not Secrets Manager."""
    monkeypatch.delenv("SERVICE_SECRET_ARN", raising=False)


@pytest.fixture
def paypal_env(monkeypatch):
    """Set all required PayPal config env vars."""
    monkeypatch.setenv("PAYPAL_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("PAYPAL_WEBHOOK_ID", "wh_123")
    monkeypatch.setenv("PAYPAL_BASE_URL", "https://api-m.sandbox.paypal.com")


def _mock_response(status_code: int, json_data: dict) -> MagicMock:
    """Create a mock httpx.Response with the given status and JSON body."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.text = json.dumps(json_data)
    return resp


# ---------------------------------------------------------------------------
# Test: successful capture (200/201)
# ---------------------------------------------------------------------------


def test_capture_order_success(paypal_env):
    """Capture call returns 200/201 → status extracted from response."""
    token_resp = _mock_response(
        200,
        {
            "access_token": "tok-cap-1",
            "expires_in": 3600,
        },
    )
    capture_resp = _mock_response(
        201,
        {
            "id": "5O190127TN364715T",
            "status": "COMPLETED",
        },
    )

    class FakeClient:
        """A tiny fake httpx.Client that returns responses based on URL."""

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, **kwargs):
            if "/v1/oauth2/token" in url:
                return token_resp
            if "/capture" in url:
                return capture_resp
            raise AssertionError(f"Unexpected POST to {url}")

        def get(self, url, **kwargs):
            raise AssertionError(f"Unexpected GET to {url}")

    with patch("httpx.Client") as mock_client_cls:
        mock_client_cls.return_value = FakeClient()
        client = PayPalClient()
        result = client.capture_order("5O190127TN364715T")

    assert result == {"status": "COMPLETED"}


# ---------------------------------------------------------------------------
# Test: already captured → idempotent (422 with ORDER_ALREADY_CAPTURED)
# ---------------------------------------------------------------------------


def test_capture_order_already_captured_is_idempotent(paypal_env):
    """When PayPal returns 422 ORDER_ALREADY_CAPTURED, treat as success."""
    token_resp = _mock_response(
        200,
        {
            "access_token": "tok-cap-2",
            "expires_in": 3600,
        },
    )
    already_captured_resp = _mock_response(
        422,
        {
            "name": "UNPROCESSABLE_ENTITY",
            "details": [
                {
                    "issue": "ORDER_ALREADY_CAPTURED",
                    "description": "Order already captured.",
                }
            ],
            "message": "The requested action could not be performed.",
        },
    )

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, **kwargs):
            if "/v1/oauth2/token" in url:
                return token_resp
            if "/capture" in url:
                return already_captured_resp
            raise AssertionError(f"Unexpected POST to {url}")

        def get(self, url, **kwargs):
            raise AssertionError(f"Unexpected GET to {url}")

    with patch("httpx.Client") as mock_client_cls:
        mock_client_cls.return_value = FakeClient()
        client = PayPalClient()
        result = client.capture_order("5O190127TN364715T")

    assert result == {"status": "COMPLETED"}


# ---------------------------------------------------------------------------
# Test: non-422 error → PayPalError
# ---------------------------------------------------------------------------


def test_capture_order_raises_on_error(paypal_env):
    """Any non-2xx and non-422 (already-captured) response raises PayPalError."""
    token_resp = _mock_response(
        200,
        {
            "access_token": "tok-cap-3",
            "expires_in": 3600,
        },
    )
    error_resp = _mock_response(
        500,
        {
            "name": "INTERNAL_SERVER_ERROR",
            "message": "An internal error occurred.",
        },
    )

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, **kwargs):
            if "/v1/oauth2/token" in url:
                return token_resp
            if "/capture" in url:
                return error_resp
            raise AssertionError(f"Unexpected POST to {url}")

        def get(self, url, **kwargs):
            raise AssertionError(f"Unexpected GET to {url}")

    with patch("httpx.Client") as mock_client_cls:
        mock_client_cls.return_value = FakeClient()
        client = PayPalClient()
        with pytest.raises(PayPalError) as exc_info:
            client.capture_order("5O190127TN364715T")

    assert exc_info.value.status_code == 500
    assert "Failed to capture PayPal order" in exc_info.value.message
