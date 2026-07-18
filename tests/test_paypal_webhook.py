"""Hermetic unit tests for paypal_webhook lambda (FDS-27 P2-C6).

All external dependencies (verify_webhook_signature, get_service_secret)
are mocked — no network calls.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from src.lambdas.paypal_webhook.handler import handler
from src.shared.errors.app_error import AppError

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_BASE_EVENT = {
    "headers": {
        "paypal-transmission-id": "txn-abc123",
        "paypal-transmission-time": "2026-07-18T10:00:00Z",
        "paypal-cert-url": "https://api.paypal.com/v1/notifications/certs/CERT-360",
        "paypal-auth-algo": "SHA256withRSA",
        "paypal-transmission-sig": "sig-value",
    },
    "body": json.dumps(
        {
            "event_type": "CHECKOUT.ORDER.APPROVED",
            "resource": {
                "id": "PAYPAL-ORDER-42",
                "status": "APPROVED",
            },
        }
    ),
}


# ---------------------------------------------------------------------------
# Test 1: valid signature → normalised dict
# ---------------------------------------------------------------------------


@patch("src.lambdas.paypal_webhook.handler.verify_webhook_signature", return_value=True)
def test_valid_signature_returns_normalised_event(_mock_verify):
    result = handler(_BASE_EVENT, None)

    assert result == {
        "event_type": "CHECKOUT.ORDER.APPROVED",
        "paypal_order_id": "PAYPAL-ORDER-42",
        "status": "APPROVED",
    }
    _mock_verify.assert_called_once_with(_BASE_EVENT["headers"], _BASE_EVENT["body"])


# ---------------------------------------------------------------------------
# Test 2: invalid signature → AppError(401)
# ---------------------------------------------------------------------------


@patch(
    "src.lambdas.paypal_webhook.handler.verify_webhook_signature", return_value=False
)
def test_invalid_signature_raises_401(_mock_verify):
    with pytest.raises(AppError) as exc_info:
        handler(_BASE_EVENT, None)
    assert exc_info.value.status_code == 401
    assert exc_info.value.code == "WEBHOOK_UNVERIFIED"


# ---------------------------------------------------------------------------
# Test 3: malformed body → AppError(400)
# ---------------------------------------------------------------------------


@patch("src.lambdas.paypal_webhook.handler.verify_webhook_signature", return_value=True)
def test_missing_event_type_raises_400(_mock_verify):
    """Missing ``event_type`` in the parsed body → AppError(400)."""
    bad_event = {
        **_BASE_EVENT,
        "body": json.dumps(
            {
                "resource": {"id": "PP-1", "status": "APPROVED"},
            }
        ),
    }
    with pytest.raises(AppError) as exc_info:
        handler(bad_event, None)
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "INVALID_WEBHOOK_PAYLOAD"


@patch("src.lambdas.paypal_webhook.handler.verify_webhook_signature", return_value=True)
def test_missing_resource_raises_400(_mock_verify):
    """Missing ``resource`` object → AppError(400)."""
    bad_event = {
        **_BASE_EVENT,
        "body": json.dumps({"event_type": "CHECKOUT.ORDER.APPROVED"}),
    }
    with pytest.raises(AppError) as exc_info:
        handler(bad_event, None)
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "INVALID_WEBHOOK_PAYLOAD"


@patch("src.lambdas.paypal_webhook.handler.verify_webhook_signature", return_value=True)
def test_not_json_body_raises_400(_mock_verify):
    """Body is not valid JSON → AppError(400, INVALID_JSON)."""
    bad_event = {**_BASE_EVENT, "body": "not-json!!!"}
    with pytest.raises(AppError) as exc_info:
        handler(bad_event, None)
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "INVALID_JSON"


# ---------------------------------------------------------------------------
# Edge case: multiValueHeaders
# ---------------------------------------------------------------------------


@patch("src.lambdas.paypal_webhook.handler.verify_webhook_signature", return_value=True)
def test_multi_value_headers_are_flattened(_mock_verify):
    """API Gateway may use multiValueHeaders (lists) instead of headers."""
    event = {
        "multiValueHeaders": {
            "paypal-transmission-id": ["txn-multi"],
            "paypal-transmission-time": ["2026-07-18T10:00:00Z"],
            "paypal-cert-url": [
                "https://api.paypal.com/v1/notifications/certs/CERT-360"
            ],
            "paypal-auth-algo": ["SHA256withRSA"],
            "paypal-transmission-sig": ["sig-multi"],
        },
        "body": _BASE_EVENT["body"],
    }
    result = handler(event, None)

    assert result["paypal_order_id"] == "PAYPAL-ORDER-42"
    # Assert headers were flattened to strings
    _mock_verify.assert_called_once()
    headers_arg = _mock_verify.call_args[0][0]
    assert headers_arg["paypal-transmission-id"] == "txn-multi"
    assert headers_arg["paypal-transmission-sig"] == "sig-multi"


# ---------------------------------------------------------------------------
# Edge case: missing body
# ---------------------------------------------------------------------------


@patch("src.lambdas.paypal_webhook.handler.verify_webhook_signature", return_value=True)
def test_missing_body_raises_400(_mock_verify):
    """No 'body' key in event → AppError(400)."""
    event = {"headers": _BASE_EVENT["headers"]}
    with pytest.raises(AppError) as exc_info:
        handler(event, None)
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "MISSING_BODY"
