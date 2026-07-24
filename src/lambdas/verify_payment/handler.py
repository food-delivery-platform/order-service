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

from src.lambdas.verify_payment.schema import VerifyPaymentInput
from src.shared.errors.app_error import AppError
from src.shared.payments import payment_repository, paypal_client
from src.shared.validation import validated_input

logger = logging.getLogger(__name__)


@validated_input(VerifyPaymentInput)
def handler(event, context=None):
    # ------------------------------------------------------------------
    # 1. Validated input (via decorator)
    # ------------------------------------------------------------------
    paypal_order_id = event.paypal_order_id

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
    # 3. Fetch PayPal order; capture it if the buyer approved but it has
    #    not been captured yet (APPROVED -> COMPLETED).
    # ------------------------------------------------------------------
    try:
        pp_order = paypal_client.get_order(paypal_order_id)
        if pp_order.get("status") == "APPROVED":
            logger.info("PayPal order %s is APPROVED — capturing now", paypal_order_id)
            paypal_client.capture_order(paypal_order_id)
            pp_order = paypal_client.get_order(paypal_order_id)
    except paypal_client.PayPalError:
        logger.exception(
            "PayPal verify/capture failed for paypal_order_id=%s", paypal_order_id
        )
        raise
    except Exception as exc:
        logger.exception(
            "PayPal verify/capture failed for paypal_order_id=%s with unexpected error",
            paypal_order_id,
        )
        raise AppError(
            500,
            "PAYPAL_GET_ORDER_FAILED",
            f"Unexpected error verifying PayPal order: {exc}",
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
