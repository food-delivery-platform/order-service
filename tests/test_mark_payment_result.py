"""Hermetic unit tests for mark_payment_result lambda (FDS-27 P2-C9).

All external dependencies (payment_repository.mark_paid, mark_failed) are
mocked — no database calls.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.lambdas.mark_payment_result.handler import handler
from src.shared.errors.app_error import AppError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_UUID = "550e8400-e29b-41d4-a716-446655440000"

_VALID_EVENT_VERIFIED = {
    "verified": True,
    "order_id": _VALID_UUID,
    "paypal_order_id": "PP-42",
}

_VALID_EVENT_NOT_VERIFIED = {
    "verified": False,
    "order_id": _VALID_UUID,
    "paypal_order_id": "PP-42",
}


# ---------------------------------------------------------------------------
# Test 1: verified=True + mark_paid succeeds → PAID, applied=True
# ---------------------------------------------------------------------------


@patch("src.lambdas.mark_payment_result.handler.payment_repository.mark_paid")
def test_verified_true_mark_paid_succeeds(mock_mark_paid):
    mock_mark_paid.return_value = True

    result = handler(_VALID_EVENT_VERIFIED, None)

    assert result == {
        "order_id": _VALID_UUID,
        "paypal_order_id": "PP-42",
        "status": "PAID",
        "applied": True,
    }
    mock_mark_paid.assert_called_once_with("paypal", "PP-42")


# ---------------------------------------------------------------------------
# Test 2: verified=True but mark_paid returns False → ALREADY_PAID
# ---------------------------------------------------------------------------


@patch("src.lambdas.mark_payment_result.handler.payment_repository.mark_paid")
def test_verified_true_already_paid(mock_mark_paid):
    """Already paid (rowcount=0 from mark_paid) → status ALREADY_PAID."""
    mock_mark_paid.return_value = False

    result = handler(_VALID_EVENT_VERIFIED, None)

    assert result["status"] == "ALREADY_PAID"
    assert result["applied"] is False
    assert result["order_id"] == _VALID_UUID
    assert result["paypal_order_id"] == "PP-42"


# ---------------------------------------------------------------------------
# Test 3: verified=False → mark_failed called → FAILED, applied=True
# ---------------------------------------------------------------------------


@patch("src.lambdas.mark_payment_result.handler.payment_repository.mark_failed")
def test_verified_false_mark_failed_succeeds(mock_mark_failed):
    mock_mark_failed.return_value = True

    result = handler(_VALID_EVENT_NOT_VERIFIED, None)

    assert result == {
        "order_id": _VALID_UUID,
        "paypal_order_id": "PP-42",
        "status": "FAILED",
        "applied": True,
    }
    mock_mark_failed.assert_called_once_with(
        "paypal",
        "PP-42",
        failure_code="PAYMENT_NOT_VERIFIED",
        failure_message="PayPal payment did not match the order",
    )


# ---------------------------------------------------------------------------
# Test 4: invalid input → AppError(400)
# ---------------------------------------------------------------------------


def test_missing_required_field_raises_400():
    """Missing ``order_id`` in the event → AppError(400, INVALID_INPUT)."""
    bad_event = {"verified": True, "paypal_order_id": "PP-42"}

    with pytest.raises(AppError) as exc_info:
        handler(bad_event, None)

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "INVALID_INPUT"


def test_empty_paypal_order_id_raises_400():
    """Empty string for paypal_order_id → AppError(400, INVALID_INPUT)."""
    bad_event = {
        "verified": True,
        "order_id": _VALID_UUID,
        "paypal_order_id": "",
    }

    with pytest.raises(AppError) as exc_info:
        handler(bad_event, None)

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "INVALID_INPUT"


# ---------------------------------------------------------------------------
# Test 6: valid UUID order_id → passes
# ---------------------------------------------------------------------------


@patch("src.lambdas.mark_payment_result.handler.payment_repository.mark_paid")
def test_valid_uuid_order_id_passes(mock_mark_paid):
    """A valid UUID order_id is accepted — validation does not reject it."""
    mock_mark_paid.return_value = True

    result = handler(_VALID_EVENT_VERIFIED, None)

    assert result["order_id"] == _VALID_UUID
    assert result["status"] == "PAID"


# ---------------------------------------------------------------------------
# Test 7: non-UUID order_id → AppError(400, INVALID_INPUT)
# ---------------------------------------------------------------------------


def test_non_uuid_order_id_raises_400():
    """A non-UUID order_id like 'not-a-uuid' → AppError(400, INVALID_INPUT)."""
    bad_event = {
        "verified": True,
        "order_id": "not-a-uuid",
        "paypal_order_id": "PP-42",
    }

    with pytest.raises(AppError) as exc_info:
        handler(bad_event, None)

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "INVALID_INPUT"
