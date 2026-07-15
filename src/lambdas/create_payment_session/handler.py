"""Step Functions step — create a PayPal payment session (FDS-27).

This step runs after the order has been created with status PENDING_PAYMENT.
It calls PayPal to create a checkout order, persists a PaymentSession row
(via the payments repository), and returns the PayPal approval URL so the
state machine can redirect the customer.

Input:
    { "order_id": str, "amount": <number>, "currency": str }

Output:
    { "order_id", "paypal_order_id", "approval_url" }

On any failure the exception is logged and re-raised so the state machine's
Catch clause can handle it — no error is ever swallowed.
"""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from src.shared.errors.app_error import AppError
from src.shared.payments import paypal_client
from src.shared.payments import payment_repository
from src.shared.payments.models import PaymentStatus

logger = logging.getLogger(__name__)


def handler(event, context=None):
    # ------------------------------------------------------------------
    # 1. Parse + validate input
    # ------------------------------------------------------------------
    order_id = event.get("order_id")
    if not order_id:
        raise AppError(400, "MISSING_ORDER_ID", "order_id is required")

    raw_amount = event.get("amount")
    if raw_amount is None:
        raise AppError(400, "MISSING_AMOUNT", "amount is required")

    try:
        amount = Decimal(str(raw_amount))
    except (InvalidOperation, ValueError) as exc:
        raise AppError(
            400, "INVALID_AMOUNT", f"amount must be a valid number: {exc}"
        ) from exc

    if amount <= 0:
        raise AppError(400, "INVALID_AMOUNT", "amount must be greater than zero")

    currency = event.get("currency")
    if not currency or not isinstance(currency, str) or len(currency) != 3:
        raise AppError(
            400,
            "INVALID_CURRENCY",
            "currency must be a 3-letter ISO 4217 code",
        )

    # ------------------------------------------------------------------
    # 2. Create PayPal checkout order
    # ------------------------------------------------------------------
    try:
        paypal_result = paypal_client.create_order(
            order_id=order_id,
            amount=amount,
            currency=currency,
        )
    except paypal_client.PayPalError:
        logger.exception("PayPal create_order failed for order_id=%s", order_id)
        raise
    except Exception as exc:
        logger.exception(
            "PayPal create_order failed for order_id=%s with unexpected error",
            order_id,
        )
        raise AppError(
            500,
            "PAYPAL_CREATE_ORDER_FAILED",
            f"Unexpected error calling PayPal: {exc}",
        ) from exc

    paypal_order_id = paypal_result["paypal_order_id"]
    approval_url = paypal_result["approval_url"]

    # ------------------------------------------------------------------
    # 3. Persist payment session
    # ------------------------------------------------------------------
    try:
        payment_repository.create_payment(
            order_id=order_id,
            paypal_order_id=paypal_order_id,
            amount=amount,
            currency=currency,
            status=PaymentStatus.CREATED,
            approval_url=approval_url,
        )
    except Exception as exc:
        logger.exception(
            "create_payment failed for order_id=%s paypal_order_id=%s",
            order_id,
            paypal_order_id,
        )
        raise AppError(
            500,
            "PAYMENT_PERSISTENCE_FAILED",
            f"Failed to persist payment session: {exc}",
        ) from exc

    # ------------------------------------------------------------------
    # 4. Return SM output
    # ------------------------------------------------------------------
    return {
        "order_id": order_id,
        "paypal_order_id": paypal_order_id,
        "approval_url": approval_url,
    }
