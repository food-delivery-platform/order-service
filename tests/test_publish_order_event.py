"""Hermetic unit tests for publish_order_event lambda (FDS-27 P2-C11).

All external dependencies (EventBridge client, bus name resolution) are
mocked — no real AWS calls.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.lambdas.publish_order_event.handler import handler
from src.shared.errors.app_error import AppError
from src.shared.events.event_publisher import EventPublishError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_UUID = "550e8400-e29b-41d4-a716-446655440000"

_VALID_EVENT_PAID = {
    "order_id": _VALID_UUID,
    "paypal_order_id": "5O190127TN364715T",
    "status": "PAID",
}

_VALID_EVENT_FAILED = {
    "order_id": _VALID_UUID,
    "paypal_order_id": "5O190127TN364715T",
    "status": "FAILED",
}


def _make_mock_publisher() -> MagicMock:
    """Return a MagicMock publisher whose ``put_event`` returns a fake EventId."""
    pub = MagicMock()
    pub.put_event.return_value = "evt-1"
    return pub


_PUBLISHER_PATCH = patch(
    "src.lambdas.publish_order_event.handler.event_publisher.get_event_publisher"
)
_BUS_PATCH = patch(
    "src.lambdas.publish_order_event.handler.event_publisher.get_bus_name",
    return_value="orders-bus",
)


# ---------------------------------------------------------------------------
# Test 1: status PAID → event_name == "order.paid", publisher called once
# ---------------------------------------------------------------------------


@_BUS_PATCH
@_PUBLISHER_PATCH
def test_paid_status_emits_order_paid(mock_pub, _mock_bus):
    pub = _make_mock_publisher()
    mock_pub.return_value = pub

    result = handler(_VALID_EVENT_PAID, None)

    assert result == {
        "published": True,
        "event_name": "order.paid",
        "order_id": _VALID_UUID,
    }
    pub.put_event.assert_called_once_with(
        bus="orders-bus",
        source="order-service",
        detail_type="order.paid",
        detail={
            "order_id": _VALID_UUID,
            "paypal_order_id": "5O190127TN364715T",
            "status": "PAID",
        },
    )


# ---------------------------------------------------------------------------
# Test 2: status FAILED → event_name == "order.payment_failed"
# ---------------------------------------------------------------------------


@_BUS_PATCH
@_PUBLISHER_PATCH
def test_failed_status_emits_payment_failed(mock_pub, _mock_bus):
    pub = _make_mock_publisher()
    mock_pub.return_value = pub

    result = handler(_VALID_EVENT_FAILED, None)

    assert result["event_name"] == "order.payment_failed"
    assert result["published"] is True
    assert result["order_id"] == _VALID_UUID
    pub.put_event.assert_called_once()
    assert pub.put_event.call_args.kwargs["detail_type"] == "order.payment_failed"
    assert pub.put_event.call_args.kwargs["detail"]["status"] == "FAILED"


# ---------------------------------------------------------------------------
# Test 3: ALREADY_PAID → also mapped to order.paid
# ---------------------------------------------------------------------------


@_BUS_PATCH
@_PUBLISHER_PATCH
def test_already_paid_emits_order_paid(mock_pub, _mock_bus):
    pub = _make_mock_publisher()
    mock_pub.return_value = pub

    result = handler({**_VALID_EVENT_PAID, "status": "ALREADY_PAID"}, None)

    assert result["event_name"] == "order.paid"
    pub.put_event.assert_called_once_with(
        bus="orders-bus",
        source="order-service",
        detail_type="order.paid",
        detail={
            "order_id": _VALID_UUID,
            "paypal_order_id": "5O190127TN364715T",
            "status": "ALREADY_PAID",
        },
    )


# ---------------------------------------------------------------------------
# Test 3b: ALREADY_FAILED → also mapped to order.payment_failed
# ---------------------------------------------------------------------------


@_BUS_PATCH
@_PUBLISHER_PATCH
def test_already_failed_emits_payment_failed(mock_pub, _mock_bus):
    """C9 may emit ALREADY_FAILED — it must still map to order.payment_failed."""
    pub = _make_mock_publisher()
    mock_pub.return_value = pub

    result = handler({**_VALID_EVENT_FAILED, "status": "ALREADY_FAILED"}, None)

    assert result["event_name"] == "order.payment_failed"
    assert result["published"] is True
    pub.put_event.assert_called_once_with(
        bus="orders-bus",
        source="order-service",
        detail_type="order.payment_failed",
        detail={
            "order_id": _VALID_UUID,
            "paypal_order_id": "5O190127TN364715T",
            "status": "ALREADY_FAILED",
        },
    )


# ---------------------------------------------------------------------------
# Test 4: invalid input → AppError(400, INVALID_INPUT)
# ---------------------------------------------------------------------------


def test_missing_order_id_raises_400():
    """Missing ``order_id`` → AppError(400, INVALID_INPUT)."""
    bad_event = {"paypal_order_id": "5O190127TN364715T", "status": "PAID"}

    with pytest.raises(AppError) as exc_info:
        handler(bad_event, None)

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "INVALID_INPUT"


def test_empty_status_raises_400():
    """Empty string for ``status`` → AppError(400, INVALID_INPUT)."""
    bad_event = {
        "order_id": _VALID_UUID,
        "paypal_order_id": "5O190127TN364715T",
        "status": "",
    }

    with pytest.raises(AppError) as exc_info:
        handler(bad_event, None)

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "INVALID_INPUT"


# ---------------------------------------------------------------------------
# Test 5: publisher raises EventPublishError → AppError(500, EVENT_PUBLISH_FAILED)
# ---------------------------------------------------------------------------


def test_non_uuid_order_id_raises_400():
    """A non-UUID order_id like 'not-a-uuid' → AppError(400, INVALID_INPUT)."""
    bad_event = {
        "order_id": "not-a-uuid",
        "paypal_order_id": "5O190127TN364715T",
        "status": "PAID",
    }

    with pytest.raises(AppError) as exc_info:
        handler(bad_event, None)

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "INVALID_INPUT"


@_BUS_PATCH
@_PUBLISHER_PATCH
def test_result_is_json_serializable(mock_pub, _mock_bus):
    """The returned dict is JSON-encodable and order_id is a plain str."""
    pub = _make_mock_publisher()
    mock_pub.return_value = pub

    result = handler(_VALID_EVENT_PAID, None)

    dumped = json.dumps(result)
    assert isinstance(dumped, str)

    # Round-trip to verify order_id survived as a string
    reloaded = json.loads(dumped)
    assert reloaded["order_id"] == _VALID_UUID
    assert isinstance(reloaded["order_id"], str)


@_BUS_PATCH
@_PUBLISHER_PATCH
def test_publish_failure_raises_500(mock_pub, _mock_bus):
    pub = MagicMock()
    pub.put_event.side_effect = EventPublishError("boom")
    mock_pub.return_value = pub

    with pytest.raises(AppError) as exc_info:
        handler(_VALID_EVENT_PAID, None)

    assert exc_info.value.status_code == 500
    assert exc_info.value.code == "EVENT_PUBLISH_FAILED"
