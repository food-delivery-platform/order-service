"""Hermetic unit tests for create_payment_session lambda (FDS-27).

All external dependencies (paypal_client, payment_repository) are mocked.
No network calls.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest

from src.lambdas.create_payment_session.handler import handler
from src.shared.errors.app_error import AppError
from src.shared.payments.models import PaymentStatus
from src.shared.payments.paypal_client import PayPalError

_VALID_EVENT = {
    "order_id": "ord-abc123",
    "amount": 78.50,
    "currency": "ILS",
}

_PAYPAL_OK = {
    "paypal_order_id": "PAYPAL-TEST-001",
    "approval_url": "https://www.sandbox.paypal.com/checkout/approve",
}


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@patch("src.lambdas.create_payment_session.handler.payment_repository.create_payment")
@patch("src.lambdas.create_payment_session.handler.paypal_client.create_order")
def test_happy_path(mock_create_order, mock_create_payment):
    mock_create_order.return_value = _PAYPAL_OK

    result = handler(_VALID_EVENT, None)

    assert result == {
        "order_id": "ord-abc123",
        "paypal_order_id": "PAYPAL-TEST-001",
        "approval_url": _PAYPAL_OK["approval_url"],
    }

    mock_create_order.assert_called_once_with(
        order_id="ord-abc123",
        amount=Decimal("78.50"),
        currency="ILS",
    )

    mock_create_payment.assert_called_once_with(
        order_id="ord-abc123",
        paypal_order_id="PAYPAL-TEST-001",
        amount=Decimal("78.50"),
        currency="ILS",
        status=PaymentStatus.CREATED,
        approval_url=_PAYPAL_OK["approval_url"],
    )


# ---------------------------------------------------------------------------
# PayPal failure → re-raise, repo NOT called
# ---------------------------------------------------------------------------


@patch("src.lambdas.create_payment_session.handler.payment_repository.create_payment")
@patch("src.lambdas.create_payment_session.handler.paypal_client.create_order")
def test_paypal_failure_re_raises_and_skips_repo(
    mock_create_order, mock_create_payment
):
    mock_create_order.side_effect = PayPalError(500, "PayPal is down")

    with pytest.raises(PayPalError, match="PayPal is down"):
        handler(_VALID_EVENT, None)

    mock_create_payment.assert_not_called()


# ---------------------------------------------------------------------------
# PayPal unexpected error
# ---------------------------------------------------------------------------


@patch("src.lambdas.create_payment_session.handler.payment_repository.create_payment")
@patch("src.lambdas.create_payment_session.handler.paypal_client.create_order")
def test_paypal_unexpected_error_wraps_in_app_error(
    mock_create_order, mock_create_payment
):
    mock_create_order.side_effect = ValueError("some bug")

    with pytest.raises(AppError, match="Unexpected error calling PayPal"):
        handler(_VALID_EVENT, None)

    mock_create_payment.assert_not_called()


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


@patch("src.lambdas.create_payment_session.handler.paypal_client.create_order")
def test_missing_order_id_raises(mock_create_order):
    bad = {k: v for k, v in _VALID_EVENT.items() if k != "order_id"}
    with pytest.raises(AppError, match="order_id is required"):
        handler(bad, None)
    mock_create_order.assert_not_called()


@patch("src.lambdas.create_payment_session.handler.paypal_client.create_order")
def test_missing_amount_raises(mock_create_order):
    bad = {k: v for k, v in _VALID_EVENT.items() if k != "amount"}
    with pytest.raises(AppError, match="amount is required"):
        handler(bad, None)
    mock_create_order.assert_not_called()


@patch("src.lambdas.create_payment_session.handler.paypal_client.create_order")
def test_zero_amount_raises(mock_create_order):
    bad = {**_VALID_EVENT, "amount": 0}
    with pytest.raises(AppError, match="amount must be greater than zero"):
        handler(bad, None)
    mock_create_order.assert_not_called()


@patch("src.lambdas.create_payment_session.handler.paypal_client.create_order")
def test_invalid_amount_string_raises(mock_create_order):
    bad = {**_VALID_EVENT, "amount": "not-a-number"}
    with pytest.raises(AppError, match="amount must be a valid number"):
        handler(bad, None)
    mock_create_order.assert_not_called()


@patch("src.lambdas.create_payment_session.handler.paypal_client.create_order")
def test_missing_currency_raises(mock_create_order):
    bad = {k: v for k, v in _VALID_EVENT.items() if k != "currency"}
    with pytest.raises(AppError, match="currency must be a 3-letter"):
        handler(bad, None)
    mock_create_order.assert_not_called()


@patch("src.lambdas.create_payment_session.handler.paypal_client.create_order")
def test_currency_too_short_raises(mock_create_order):
    bad = {**_VALID_EVENT, "currency": "IL"}
    with pytest.raises(AppError, match="currency must be a 3-letter"):
        handler(bad, None)
    mock_create_order.assert_not_called()


@patch("src.lambdas.create_payment_session.handler.paypal_client.create_order")
def test_currency_too_long_raises(mock_create_order):
    bad = {**_VALID_EVENT, "currency": "ILSS"}
    with pytest.raises(AppError, match="currency must be a 3-letter"):
        handler(bad, None)
    mock_create_order.assert_not_called()
