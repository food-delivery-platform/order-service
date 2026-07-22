"""Hermetic unit tests for auto-capture in verify_payment (FDS-32).

Verifies that the verify_payment lambda captures an APPROVED PayPal order
before validating, and skips capture when already COMPLETED.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from src.lambdas.verify_payment.handler import handler
from src.shared.payments.models import PaymentSession, PaymentStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PAYMENT_MATCH = PaymentSession(
    order_id="ord-42",
    provider="paypal",
    provider_ref="5O190127TN364715T",
    amount=Decimal("50.00"),
    currency="ILS",
    status=PaymentStatus.PENDING,
    approval_url="https://paypal.com/approve",
)

_VALID_EVENT = {
    "paypal_order_id": "5O190127TN364715T",
    "event_type": "CHECKOUT.ORDER.APPROVED",
}

_GET_ORDER_APPROVED = {
    "status": "APPROVED",
    "amount": "50.00",
    "currency": "ILS",
}

_GET_ORDER_COMPLETED = {
    "status": "COMPLETED",
    "amount": "50.00",
    "currency": "ILS",
}


# ---------------------------------------------------------------------------
# Test 1: APPROVED → capture → re-fetch → verified=True
# ---------------------------------------------------------------------------


@patch("src.lambdas.verify_payment.handler.payment_repository.get_by_provider_ref")
@patch("src.lambdas.verify_payment.handler.paypal_client.capture_order")
@patch("src.lambdas.verify_payment.handler.paypal_client.get_order")
def test_verify_captures_when_approved(mock_get_order, mock_capture, mock_get_by_ref):
    """When PayPal order is APPROVED, capture it, re-fetch, then verify."""
    mock_get_by_ref.return_value = _PAYMENT_MATCH

    # First call returns APPROVED; after capture, second call returns COMPLETED
    mock_get_order.side_effect = [_GET_ORDER_APPROVED, _GET_ORDER_COMPLETED]

    result = handler(_VALID_EVENT, None)

    # Capture was called
    mock_capture.assert_called_once_with("5O190127TN364715T")

    # get_order called twice: once before capture, once after
    assert mock_get_order.call_count == 2

    # Final result: verified=True (COMPLETED + matching amount/currency)
    assert result == {
        "verified": True,
        "order_id": "ord-42",
        "paypal_order_id": "5O190127TN364715T",
        "amount": "50.00",
        "currency": "ILS",
    }


# ---------------------------------------------------------------------------
# Test 2: already COMPLETED → skip capture → verified=True
# ---------------------------------------------------------------------------


@patch("src.lambdas.verify_payment.handler.payment_repository.get_by_provider_ref")
@patch("src.lambdas.verify_payment.handler.paypal_client.capture_order")
@patch("src.lambdas.verify_payment.handler.paypal_client.get_order")
def test_verify_skips_capture_when_already_completed(
    mock_get_order, mock_capture, mock_get_by_ref
):
    """When PayPal order is already COMPLETED, skip capture entirely."""
    mock_get_by_ref.return_value = _PAYMENT_MATCH
    mock_get_order.return_value = _GET_ORDER_COMPLETED

    result = handler(_VALID_EVENT, None)

    # Capture must NOT have been called
    mock_capture.assert_not_called()

    # get_order called exactly once
    mock_get_order.assert_called_once_with("5O190127TN364715T")

    assert result["verified"] is True
