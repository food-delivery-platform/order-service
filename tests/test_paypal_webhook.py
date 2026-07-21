"""Hermetic unit tests for paypal_webhook lambda (FDS-27 P2-C6).

All external dependencies (verify_webhook_signature, boto3 stepfunctions)
are mocked — no network calls.
"""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch


from src.lambdas.paypal_webhook.handler import handler

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SM_ARN = "arn:aws:states:us-east-1:000000000000:stateMachine:payment-confirmation"

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
                "id": "5O190127TN364715T",
                "status": "APPROVED",
            },
        }
    ),
}

_NORMALISED = {
    "event_type": "CHECKOUT.ORDER.APPROVED",
    "paypal_order_id": "5O190127TN364715T",
    "status": "APPROVED",
}


def _patch_env():
    """Set PAYMENT_CONFIRMATION_SM_ARN for tests that need it."""
    return patch.dict(os.environ, {"PAYMENT_CONFIRMATION_SM_ARN": _SM_ARN})


def _assert_response(response: dict, expected_status: int):
    """Assert an API Gateway proxy response has the expected shape and status."""
    assert isinstance(response, dict)
    assert "statusCode" in response
    assert "headers" in response
    assert "body" in response
    assert response["statusCode"] == expected_status
    assert response["headers"]["Content-Type"] == "application/json"
    body = json.loads(response["body"])
    return body


# ---------------------------------------------------------------------------
# Test 1: valid signature → starts SM → 200 accepted
# ---------------------------------------------------------------------------


@patch("src.lambdas.paypal_webhook.handler.verify_webhook_signature", return_value=True)
@patch("src.lambdas.paypal_webhook.handler.boto3.client")
def test_valid_signature_starts_sm_and_returns_200(mock_boto3_client, _mock_verify):
    mock_sfn = MagicMock()
    mock_boto3_client.return_value = mock_sfn

    with _patch_env():
        response = handler(_BASE_EVENT, None)

    body = _assert_response(response, 200)
    assert body == {"status": "accepted", "paypal_order_id": "5O190127TN364715T"}

    _mock_verify.assert_called_once_with(_BASE_EVENT["headers"], _BASE_EVENT["body"])
    mock_boto3_client.assert_called_once_with("stepfunctions")
    mock_sfn.start_execution.assert_called_once_with(
        stateMachineArn=_SM_ARN,
        input=json.dumps(_NORMALISED),
    )


# ---------------------------------------------------------------------------
# Test 2: invalid signature → 401
# ---------------------------------------------------------------------------


@patch(
    "src.lambdas.paypal_webhook.handler.verify_webhook_signature",
    return_value=False,
)
def test_invalid_signature_returns_401(_mock_verify):
    with _patch_env():
        response = handler(_BASE_EVENT, None)

    body = _assert_response(response, 401)
    assert body["error"] == "WEBHOOK_UNVERIFIED"


# ---------------------------------------------------------------------------
# Test 3: missing PAYMENT_CONFIRMATION_SM_ARN → 500
# ---------------------------------------------------------------------------


@patch("src.lambdas.paypal_webhook.handler.verify_webhook_signature", return_value=True)
def test_missing_sm_arn_returns_500(_mock_verify):
    with patch.dict(os.environ, {}, clear=True):
        response = handler(_BASE_EVENT, None)

    body = _assert_response(response, 500)
    assert body["error"] == "MISSING_SM_ARN"


# ---------------------------------------------------------------------------
# Test 4: missing event_type → 400
# ---------------------------------------------------------------------------


@patch("src.lambdas.paypal_webhook.handler.verify_webhook_signature", return_value=True)
def test_missing_event_type_returns_400(_mock_verify):
    """Missing ``event_type`` in the parsed body → 400."""
    bad_event = {
        **_BASE_EVENT,
        "body": json.dumps(
            {
                "resource": {"id": "PP-1", "status": "APPROVED"},
            }
        ),
    }
    with _patch_env():
        response = handler(bad_event, None)

    body = _assert_response(response, 400)
    assert body["error"] == "INVALID_WEBHOOK_PAYLOAD"


# ---------------------------------------------------------------------------
# Test 5: missing resource → 400
# ---------------------------------------------------------------------------


@patch("src.lambdas.paypal_webhook.handler.verify_webhook_signature", return_value=True)
def test_missing_resource_returns_400(_mock_verify):
    """Missing ``resource`` object → 400."""
    bad_event = {
        **_BASE_EVENT,
        "body": json.dumps({"event_type": "CHECKOUT.ORDER.APPROVED"}),
    }
    with _patch_env():
        response = handler(bad_event, None)

    body = _assert_response(response, 400)
    assert body["error"] == "INVALID_WEBHOOK_PAYLOAD"


# ---------------------------------------------------------------------------
# Test 6: not-JSON body → 400
# ---------------------------------------------------------------------------


@patch("src.lambdas.paypal_webhook.handler.verify_webhook_signature", return_value=True)
def test_not_json_body_returns_400(_mock_verify):
    """Body is not valid JSON → 400, INVALID_JSON."""
    bad_event = {**_BASE_EVENT, "body": "not-json!!!"}
    with _patch_env():
        response = handler(bad_event, None)

    body = _assert_response(response, 400)
    assert body["error"] == "INVALID_JSON"


# ---------------------------------------------------------------------------
# Test 7: missing body → 400
# ---------------------------------------------------------------------------


@patch("src.lambdas.paypal_webhook.handler.verify_webhook_signature", return_value=True)
def test_missing_body_returns_400(_mock_verify):
    """No 'body' key in event → 400."""
    event = {"headers": _BASE_EVENT["headers"]}
    with _patch_env():
        response = handler(event, None)

    body = _assert_response(response, 400)
    assert body["error"] == "MISSING_BODY"


# ---------------------------------------------------------------------------
# Test 8: multiValueHeaders are flattened, SM started
# ---------------------------------------------------------------------------


@patch("src.lambdas.paypal_webhook.handler.verify_webhook_signature", return_value=True)
@patch("src.lambdas.paypal_webhook.handler.boto3.client")
def test_multi_value_headers_are_flattened_and_sm_started(
    mock_boto3_client, _mock_verify
):
    """API Gateway may use multiValueHeaders (lists) instead of headers."""
    mock_sfn = MagicMock()
    mock_boto3_client.return_value = mock_sfn

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

    with _patch_env():
        response = handler(event, None)

    body = _assert_response(response, 200)
    assert body["paypal_order_id"] == "5O190127TN364715T"

    # Assert headers were flattened to strings
    _mock_verify.assert_called_once()
    headers_arg = _mock_verify.call_args[0][0]
    assert headers_arg["paypal-transmission-id"] == "txn-multi"
    assert headers_arg["paypal-transmission-sig"] == "sig-multi"

    # Assert SM was started
    mock_sfn.start_execution.assert_called_once()
