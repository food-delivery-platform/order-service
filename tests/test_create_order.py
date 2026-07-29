"""Hermetic unit tests for create_order lambda (FDS-42).

All external dependencies (boto3 client, os.environ) are mocked so tests
run without AWS credentials.  Tests exercise the pydantic schema rather
than manual ``if not`` checks.
"""

from __future__ import annotations

import json
import sys
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Mock boto3 BEFORE importing the handler so the module-level
# ``_stepfunctions = boto3.client("stepfunctions")`` does not try to
# contact AWS.
# ---------------------------------------------------------------------------
_mock_boto3 = MagicMock()
_mock_sfn_client = MagicMock()
_mock_boto3.client.return_value = _mock_sfn_client
sys.modules["boto3"] = _mock_boto3

import pytest

from src.lambdas.create_order.handler import (
    STATE_MACHINE_ARN_ENV,
    _decode_body,
    handler,
)

# ---------------------------------------------------------------------------
# Module-level fixtures
# ---------------------------------------------------------------------------

_SM_ARN = "arn:aws:states:us-east-1:000000000000:stateMachine:order-creation"

_VALID_BODY = {
    "customer_id": "user-123",
    "restaurant_id": "rest-456",
    "items": [{"menu_item_id": "item-1", "quantity": 2}],
    "delivery_address": {
        "street": "Main St",
        "city": "Tel Aviv",
        "postal_code": "12345",
    },
}

_VALID_EVENT = {
    "body": json.dumps(_VALID_BODY),
    "isBase64Encoded": False,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _patch_sm_arn(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(STATE_MACHINE_ARN_ENV, _SM_ARN)


def _assert_response(response: dict, expected_status: int) -> dict:
    assert isinstance(response, dict)
    assert "statusCode" in response
    assert "headers" in response
    assert "body" in response
    assert response["statusCode"] == expected_status
    assert response["headers"]["Content-Type"] == "application/json"
    return json.loads(response["body"])


# ---------------------------------------------------------------------------
# 1. valid payload → 202
# ---------------------------------------------------------------------------


def test_valid_payload_returns_202(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_sm_arn(monkeypatch)
    _mock_sfn_client.reset_mock()

    response = handler(_VALID_EVENT, None)

    body = _assert_response(response, 202)
    assert body["status"] == "PENDING"
    assert body["executionId"].startswith("create-order-")
    assert body["executionArn"].startswith(_SM_ARN)

    _mock_sfn_client.start_execution.assert_called_once()
    call_kwargs = _mock_sfn_client.start_execution.call_args.kwargs
    assert call_kwargs["stateMachineArn"] == _SM_ARN
    assert call_kwargs["name"].startswith("create-order-")
    assert json.loads(call_kwargs["input"]) == _VALID_BODY


# ---------------------------------------------------------------------------
# 2. missing ORDER_CREATION_SM_ARN → 500 CONFIGURATION_ERROR
# ---------------------------------------------------------------------------


def test_missing_sm_arn_returns_500(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(STATE_MACHINE_ARN_ENV, raising=False)
    _mock_sfn_client.reset_mock()

    response = handler(_VALID_EVENT, None)

    body = _assert_response(response, 500)
    assert body["error"] == "CONFIGURATION_ERROR"

    _mock_sfn_client.start_execution.assert_not_called()


# ---------------------------------------------------------------------------
# 2a. whitespace-only ORDER_CREATION_SM_ARN → 500 CONFIGURATION_ERROR
# ---------------------------------------------------------------------------


def test_whitespace_sm_arn_returns_500(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(STATE_MACHINE_ARN_ENV, "   ")
    _mock_sfn_client.reset_mock()

    response = handler(_VALID_EVENT, None)

    body = _assert_response(response, 500)
    assert body["error"] == "CONFIGURATION_ERROR"

    _mock_sfn_client.start_execution.assert_not_called()


# ---------------------------------------------------------------------------
# 3. missing body → 400 INVALID_BODY
# ---------------------------------------------------------------------------


def test_missing_body_returns_400(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_sm_arn(monkeypatch)

    response = handler({"body": ""}, None)
    body = _assert_response(response, 400)
    assert body["error"] == "INVALID_BODY"


# ---------------------------------------------------------------------------
# 4. body that is not JSON → 400 INVALID_BODY
# ---------------------------------------------------------------------------


def test_not_json_body_returns_400(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_sm_arn(monkeypatch)

    response = handler({"body": "not-json!!!"}, None)
    body = _assert_response(response, 400)
    assert body["error"] == "INVALID_BODY"


# ---------------------------------------------------------------------------
# 5. payload without customer_id → 400 INVALID_INPUT
# ---------------------------------------------------------------------------


def test_missing_customer_id_returns_400(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_sm_arn(monkeypatch)

    body = {k: v for k, v in _VALID_BODY.items() if k != "customer_id"}
    response = handler({"body": json.dumps(body)}, None)
    body_resp = _assert_response(response, 400)
    assert body_resp["error"] == "INVALID_INPUT"
    assert "customer_id" in body_resp["message"]


# ---------------------------------------------------------------------------
# 6. item with quantity 0 → 400 INVALID_INPUT
# ---------------------------------------------------------------------------


def test_zero_quantity_returns_400(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_sm_arn(monkeypatch)

    body = {
        **_VALID_BODY,
        "items": [{"menu_item_id": "item-1", "quantity": 0}],
    }
    response = handler({"body": json.dumps(body)}, None)
    body_resp = _assert_response(response, 400)
    assert body_resp["error"] == "INVALID_INPUT"


# ---------------------------------------------------------------------------
# 7. empty items list → 400 INVALID_INPUT
# ---------------------------------------------------------------------------


def test_empty_items_returns_400(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_sm_arn(monkeypatch)

    body = {**_VALID_BODY, "items": []}
    response = handler({"body": json.dumps(body)}, None)
    body_resp = _assert_response(response, 400)
    assert body_resp["error"] == "INVALID_INPUT"


# ---------------------------------------------------------------------------
# 8. delivery_address missing postal_code → 400 INVALID_INPUT
# ---------------------------------------------------------------------------


def test_delivery_address_missing_postal_code_returns_400(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_sm_arn(monkeypatch)

    body = {
        **_VALID_BODY,
        "delivery_address": {"street": "Main St", "city": "Tel Aviv"},
    }
    response = handler({"body": json.dumps(body)}, None)
    body_resp = _assert_response(response, 400)
    assert body_resp["error"] == "INVALID_INPUT"


# ---------------------------------------------------------------------------
# 9. unknown extra field → 400 INVALID_INPUT (extra="forbid")
# ---------------------------------------------------------------------------


def test_unknown_field_returns_400(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_sm_arn(monkeypatch)

    body = {**_VALID_BODY, "garbage": 42}
    response = handler({"body": json.dumps(body)}, None)
    body_resp = _assert_response(response, 400)
    assert body_resp["error"] == "INVALID_INPUT"


# ---------------------------------------------------------------------------
# 10. start_execution raising ClientError → 502 ORCHESTRATION_UNAVAILABLE
# ---------------------------------------------------------------------------


def test_sfn_client_error_returns_502(monkeypatch: pytest.MonkeyPatch) -> None:
    from botocore.exceptions import ClientError

    _patch_sm_arn(monkeypatch)
    _mock_sfn_client.reset_mock()
    _mock_sfn_client.start_execution.side_effect = ClientError(
        {"Error": {"Code": "StateMachineDoesNotExist", "Message": "nope"}},
        "StartExecution",
    )

    response = handler(_VALID_EVENT, None)
    body = _assert_response(response, 502)
    assert body["error"] == "ORCHESTRATION_UNAVAILABLE"


# ---------------------------------------------------------------------------
# _decode_body edge cases
# ---------------------------------------------------------------------------


def test_decode_body_no_body_key_returns_none() -> None:
    assert _decode_body({}) is None


def test_decode_body_none_body_returns_none() -> None:
    assert _decode_body({"body": None}) is None


def test_decode_body_plain_json() -> None:
    result = _decode_body({"body": '{"a": 1}'})
    assert result == {"a": 1}
