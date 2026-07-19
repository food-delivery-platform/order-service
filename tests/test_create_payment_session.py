"""Hermetic unit tests for create_payment_session lambda (FDS-27 R3).

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
        "provider_ref": "PAYPAL-TEST-001",
        "approval_url": _PAYPAL_OK["approval_url"],
    }

    mock_create_order.assert_called_once_with(
        order_id="ord-abc123",
        amount=Decimal("78.50"),
        currency="ILS",
    )

    mock_create_payment.assert_called_once_with(
        order_id="ord-abc123",
        provider="paypal",
        provider_ref="PAYPAL-TEST-001",
        amount=Decimal("78.50"),
        currency="ILS",
        status=PaymentStatus.PENDING,
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
# Input validation (Pydantic v2)
# ---------------------------------------------------------------------------


def _assert_invalid_input(mock_create_order, event):
    """Assert that *event* raises AppError(400, "INVALID_INPUT") and
    paypal_client is never called."""
    with pytest.raises(AppError) as exc_info:
        handler(event, None)
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "INVALID_INPUT"
    assert mock_create_order.call_count == 0


@patch("src.lambdas.create_payment_session.handler.paypal_client.create_order")
def test_missing_order_id_raises(mock_create_order):
    _assert_invalid_input(
        mock_create_order,
        {k: v for k, v in _VALID_EVENT.items() if k != "order_id"},
    )


@patch("src.lambdas.create_payment_session.handler.paypal_client.create_order")
def test_missing_amount_raises(mock_create_order):
    _assert_invalid_input(
        mock_create_order,
        {k: v for k, v in _VALID_EVENT.items() if k != "amount"},
    )


@patch("src.lambdas.create_payment_session.handler.paypal_client.create_order")
def test_zero_amount_raises(mock_create_order):
    _assert_invalid_input(mock_create_order, {**_VALID_EVENT, "amount": 0})


@patch("src.lambdas.create_payment_session.handler.paypal_client.create_order")
def test_negative_amount_raises(mock_create_order):
    _assert_invalid_input(mock_create_order, {**_VALID_EVENT, "amount": -5})


@patch("src.lambdas.create_payment_session.handler.paypal_client.create_order")
def test_invalid_amount_string_raises(mock_create_order):
    _assert_invalid_input(mock_create_order, {**_VALID_EVENT, "amount": "not-a-number"})


@patch("src.lambdas.create_payment_session.handler.paypal_client.create_order")
def test_missing_currency_raises(mock_create_order):
    _assert_invalid_input(
        mock_create_order,
        {k: v for k, v in _VALID_EVENT.items() if k != "currency"},
    )


@patch("src.lambdas.create_payment_session.handler.paypal_client.create_order")
def test_currency_too_short_raises(mock_create_order):
    _assert_invalid_input(mock_create_order, {**_VALID_EVENT, "currency": "IL"})


@patch("src.lambdas.create_payment_session.handler.paypal_client.create_order")
def test_currency_too_long_raises(mock_create_order):
    _assert_invalid_input(mock_create_order, {**_VALID_EVENT, "currency": "ILSS"})
