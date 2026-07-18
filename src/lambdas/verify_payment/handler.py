"""Step Functions step — verify a PayPal payment against the stored order (FDS-27 P2-C8).

This step runs after the ``paypal_webhook`` lambda receives a notification.
It verifies the PayPal order matches the stored payment session by comparing
status, amount and currency — ensuring the payment is legitimate before
marking it paid.

Input:
    ``{ "paypal_order_id": str, "event_type": str }``  — output of paypal_webhook

Output:
    ``{ "verified": bool, "order_id": str, "paypal_order_id": str, "amount": str, "currency": str }``
"""

from __future__ import annotations

import logging
from decimal import Decimal

from pydantic import ValidationError

from src.lambdas.verify_payment.schema import VerifyPaymentInput
from src.shared.errors.app_error import AppError
from src.shared.payments import paypal_client
from src.shared.payments import payment_repository

logger = logging.getLogger(__name__)


def handler(event, context=None):
    # ------------------------------------------------------------------
    # 1. Parse + validate input (Pydantic v2)
    # ------------------------------------------------------------------
    try:
        data = VerifyPaymentInput.model_validate(event)
    except ValidationError as exc:
        raise AppError(400, "INVALID_INPUT", str(exc)) from exc

    paypal_order_id = data.paypal_order_id

    # ------------------------------------------------------------------
    # 2. Look up the stored payment session
    # ------------------------------------------------------------------
    payment = payment_repository.get_by_provider_ref("paypal", paypal_order_id)
    if payment is None:
        raise AppError(
            404,
            "PAYMENT_NOT_FOUND",
            f"No payment found for PayPal order {paypal_order_id}",
        )

    # ------------------------------------------------------------------
    # 3. Fetch PayPal order details
    # ------------------------------------------------------------------
    try:
        pp_order = paypal_client.get_order(paypal_order_id)
    except paypal_client.PayPalError:
        logger.exception(
            "PayPal get_order failed for paypal_order_id=%s", paypal_order_id
        )
        raise
    except Exception as exc:
        logger.exception(
            "PayPal get_order failed for paypal_order_id=%s with unexpected error",
            paypal_order_id,
        )
        raise AppError(
            500,
            "PAYPAL_GET_ORDER_FAILED",
            f"Unexpected error fetching PayPal order: {exc}",
        ) from exc

    # ------------------------------------------------------------------
    # 4. Verify: status must be COMPLETED, amount + currency must match
    # ------------------------------------------------------------------
    pp_status = pp_order.get("status", "")
    pp_amount = Decimal(pp_order.get("amount", "0"))
    pp_currency = pp_order.get("currency", "").upper()

    verified = (
        pp_status == "COMPLETED"
        and pp_amount == payment.amount
        and pp_currency == payment.currency.upper()
    )

    return {
        "verified": verified,
        "order_id": payment.order_id,
        "paypal_order_id": paypal_order_id,
        "amount": str(payment.amount),
        "currency": payment.currency,
    }
