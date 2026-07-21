"""Hermetic unit tests for verify_payment lambda (FDS-27 P2-C8).

All external dependencies (paypal_client.get_order, payment_repository) are
mocked — no network or database calls.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest

from src.lambdas.verify_payment.handler import handler
from src.shared.errors.app_error import AppError
from src.shared.payments.models import PaymentSession, PaymentStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PP_ORDER_COMPLETED = {
    "status": "COMPLETED",
    "amount": "50.00",
    "currency": "ILS",
}

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


# ---------------------------------------------------------------------------
# Test 1: status COMPLETED + amount/currency match → verified=True
# ---------------------------------------------------------------------------


@patch("src.lambdas.verify_payment.handler.payment_repository.get_by_provider_ref")
@patch("src.lambdas.verify_payment.handler.paypal_client.get_order")
def test_verified_true_when_all_match(mock_get_order, mock_get_by_ref):
    mock_get_by_ref.return_value = _PAYMENT_MATCH
    mock_get_order.return_value = _PP_ORDER_COMPLETED

    result = handler(_VALID_EVENT, None)

    assert result == {
        "verified": True,
        "order_id": "ord-42",
        "paypal_order_id": "5O190127TN364715T",
        "amount": "50.00",
        "currency": "ILS",
    }
    mock_get_by_ref.assert_called_once_with("paypal", "5O190127TN364715T")
    mock_get_order.assert_called_once_with("5O190127TN364715T")


# ---------------------------------------------------------------------------
# Test 2: amount mismatch → verified=False
# ---------------------------------------------------------------------------


@patch("src.lambdas.verify_payment.handler.payment_repository.get_by_provider_ref")
@patch("src.lambdas.verify_payment.handler.paypal_client.get_order")
def test_verified_false_on_amount_mismatch(mock_get_order, mock_get_by_ref):
    mock_get_by_ref.return_value = _PAYMENT_MATCH
    # PayPal reports a different amount
    mock_get_order.return_value = {
        "status": "COMPLETED",
        "amount": "99.99",
        "currency": "ILS",
    }

    result = handler(_VALID_EVENT, None)

    assert result["verified"] is False
    assert result["order_id"] == "ord-42"
    assert result["paypal_order_id"] == "5O190127TN364715T"


# ---------------------------------------------------------------------------
# Test 3: currency mismatch → verified=False
# ---------------------------------------------------------------------------


@patch("src.lambdas.verify_payment.handler.payment_repository.get_by_provider_ref")
@patch("src.lambdas.verify_payment.handler.paypal_client.get_order")
def test_verified_false_on_currency_mismatch(mock_get_order, mock_get_by_ref):
    mock_get_by_ref.return_value = _PAYMENT_MATCH
    mock_get_order.return_value = {
        "status": "COMPLETED",
        "amount": "50.00",
        "currency": "USD",
    }

    result = handler(_VALID_EVENT, None)

    assert result["verified"] is False


# ---------------------------------------------------------------------------
# Test 4: unknown provider_ref → AppError(404)
# ---------------------------------------------------------------------------


@patch("src.lambdas.verify_payment.handler.payment_repository.get_by_provider_ref")
def test_payment_not_found_raises_404(mock_get_by_ref):
    mock_get_by_ref.return_value = None

    with pytest.raises(AppError) as exc_info:
        handler(_VALID_EVENT, None)

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "PAYMENT_NOT_FOUND"
