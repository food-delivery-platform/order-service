"""Hermetic unit tests for create_order lambda (FDS-42).

All external dependencies (boto3 client, os.environ) are mocked so tests
run without AWS credentials.
"""

from __future__ import annotations

import json
import sys
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Mock boto3 BEFORE importing the handler so the module-level
# ``_stepfunctions = boto3.client("stepfunctions")`` does not try to
# contact AWS.
# ---------------------------------------------------------------------------
_mock_boto3 = MagicMock()
_mock_boto3.client.return_value = MagicMock()
sys.modules["boto3"] = _mock_boto3

import pytest

from src.lambdas.create_order.handler import (
    STATE_MACHINE_ARN_ENV,
    _decode_body,
    handler,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_SM_ARN = "arn:aws:states:us-east-1:000000000000:stateMachine:order-creation"

_VALID_BODY = {
    "customer_id": "user-123",
    "items": [{"menu_item_id": "item-1", "quantity": 2}],
}

_VALID_EVENT = {
    "body": json.dumps(_VALID_BODY),
    "isBase64Encoded": False,
}


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
# Test: successful invocation → 202 Accepted
# ---------------------------------------------------------------------------


@patch("src.lambdas.create_order.handler._stepfunctions")
def test_valid_request_starts_sm_and_returns_202(
    mock_sfn: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_sm_arn(monkeypatch)

    response = handler(_VALID_EVENT, None)

    body = _assert_response(response, 202)
    assert body["status"] == "accepted"
    assert body["executionId"].startswith("create-order-")

    mock_sfn.start_execution.assert_called_once()
    call_kwargs = mock_sfn.start_execution.call_args.kwargs
    assert call_kwargs["stateMachineArn"] == _SM_ARN
    assert call_kwargs["name"].startswith("create-order-")
    assert json.loads(call_kwargs["input"]) == _VALID_BODY


# ---------------------------------------------------------------------------
# Test: base64-encoded body is decoded correctly
# ---------------------------------------------------------------------------


@patch("src.lambdas.create_order.handler._stepfunctions")
def test_base64_encoded_body_is_decoded(
    mock_sfn: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    import base64

    _patch_sm_arn(monkeypatch)

    encoded = json.dumps(_VALID_BODY).encode("utf-8")
    event = {
        "body": base64.b64encode(encoded).decode("ascii"),
        "isBase64Encoded": True,
    }

    response = handler(event, None)

    body = _assert_response(response, 202)
    assert body["status"] == "accepted"

    call_kwargs = mock_sfn.start_execution.call_args.kwargs
    assert json.loads(call_kwargs["input"]) == _VALID_BODY


# ---------------------------------------------------------------------------
# Test: missing body → 400
# ---------------------------------------------------------------------------


def test_missing_body_returns_400(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_sm_arn(monkeypatch)

    response = handler({"body": ""}, None)
    body = _assert_response(response, 400)
    assert body["error"] == "MALFORMED_BODY"


# ---------------------------------------------------------------------------
# Test: not-JSON body → 400
# ---------------------------------------------------------------------------


def test_not_json_body_returns_400(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_sm_arn(monkeypatch)

    response = handler({"body": "not-json!!!"}, None)
    body = _assert_response(response, 400)
    assert body["error"] == "MALFORMED_BODY"


# ---------------------------------------------------------------------------
# Test: malformed base64 body → 400
# ---------------------------------------------------------------------------


def test_malformed_base64_returns_400(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_sm_arn(monkeypatch)

    response = handler({"body": "<<<not base64>>>", "isBase64Encoded": True}, None)
    body = _assert_response(response, 400)
    assert body["error"] == "MALFORMED_BODY"


# ---------------------------------------------------------------------------
# Test: missing customer_id → 400
# ---------------------------------------------------------------------------


def test_missing_customer_id_returns_400(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_sm_arn(monkeypatch)

    body = {"items": [{"menu_item_id": "item-1", "quantity": 2}]}
    response = handler({"body": json.dumps(body)}, None)
    body_resp = _assert_response(response, 400)
    assert body_resp["error"] == "INVALID_INPUT"
    assert "customer_id" in body_resp["message"]


# ---------------------------------------------------------------------------
# Test: missing items → 400
# ---------------------------------------------------------------------------


def test_missing_items_returns_400(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_sm_arn(monkeypatch)

    body = {"customer_id": "user-123"}
    response = handler({"body": json.dumps(body)}, None)
    body_resp = _assert_response(response, 400)
    assert body_resp["error"] == "INVALID_INPUT"
    assert "items" in body_resp["message"]


# ---------------------------------------------------------------------------
# Test: empty items → 400
# ---------------------------------------------------------------------------


def test_empty_items_returns_400(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_sm_arn(monkeypatch)

    body = {"customer_id": "user-123", "items": []}
    response = handler({"body": json.dumps(body)}, None)
    body_resp = _assert_response(response, 400)
    assert body_resp["error"] == "INVALID_INPUT"
    assert "items" in body_resp["message"]


# ---------------------------------------------------------------------------
# Test: missing SM ARN env var → 500
# ---------------------------------------------------------------------------


def test_missing_sm_arn_returns_500(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(STATE_MACHINE_ARN_ENV, raising=False)

    response = handler(_VALID_EVENT, None)
    body = _assert_response(response, 500)
    assert body["error"] == "MISSING_CONFIG"


# ---------------------------------------------------------------------------
# Test: boto3 start_execution ClientError → 502
# ---------------------------------------------------------------------------


@patch("src.lambdas.create_order.handler._stepfunctions")
def test_sfn_client_error_returns_502(
    mock_sfn: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    from botocore.exceptions import ClientError

    _patch_sm_arn(monkeypatch)

    mock_sfn.start_execution.side_effect = ClientError(
        {"Error": {"Code": "StateMachineDoesNotExist", "Message": "nope"}},
        "StartExecution",
    )

    response = handler(_VALID_EVENT, None)
    body = _assert_response(response, 502)
    assert body["error"] == "ORCHESTRATION_FAILED"


# ---------------------------------------------------------------------------
# Test: executionId is unique across calls
# ---------------------------------------------------------------------------


@patch("src.lambdas.create_order.handler._stepfunctions")
def test_execution_id_is_unique(
    mock_sfn: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_sm_arn(monkeypatch)

    response1 = handler(_VALID_EVENT, None)
    response2 = handler(_VALID_EVENT, None)

    id1 = json.loads(response1["body"])["executionId"]
    id2 = json.loads(response2["body"])["executionId"]
    assert id1 != id2


# ---------------------------------------------------------------------------
# Test: _decode_body edge cases
# ---------------------------------------------------------------------------


def test_decode_body_no_body_key_returns_none() -> None:
    assert _decode_body({}) is None


def test_decode_body_none_body_returns_none() -> None:
    assert _decode_body({"body": None}) is None


def test_decode_body_plain_json() -> None:
    result = _decode_body({"body": '{"a": 1}'})
    assert result == {"a": 1}
