"""Step Functions step — create a PayPal payment session (FDS-27 R3).

This step runs after the order has been created with status PENDING_PAYMENT.
It calls PayPal to create a checkout order, persists a PaymentSession row
(via the payments repository), and returns the PayPal approval URL so the
state machine can redirect the customer.

Input:
    { "order_id": str, "amount": <number>, "currency": str }

Output:
    { "order_id", "provider_ref", "approval_url" }

On any failure the exception is logged and re-raised so the state machine's
Catch clause can handle it — no error is ever swallowed.
"""

from __future__ import annotations

import logging

from pydantic import ValidationError

from src.lambdas.create_payment_session.schema import CreatePaymentSessionInput
from src.shared.errors.app_error import AppError
from src.shared.payments import paypal_client
from src.shared.payments import payment_repository
from src.shared.payments.models import PaymentStatus

logger = logging.getLogger(__name__)


def handler(event, context=None):
    # ------------------------------------------------------------------
    # 1. Parse + validate input (Pydantic v2)
    # ------------------------------------------------------------------
    try:
        data = CreatePaymentSessionInput.model_validate(event)
    except ValidationError as exc:
        raise AppError(400, "INVALID_INPUT", str(exc)) from exc

    order_id = data.order_id
    amount = data.amount
    currency = data.currency

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

    provider_ref = paypal_result["paypal_order_id"]
    approval_url = paypal_result["approval_url"]

    # ------------------------------------------------------------------
    # 3. Persist payment session
    # ------------------------------------------------------------------
    try:
        payment_repository.create_payment(
            order_id=order_id,
            provider="paypal",
            provider_ref=provider_ref,
            amount=amount,
            currency=currency,
            status=PaymentStatus.PENDING,
            approval_url=approval_url,
        )
    except Exception as exc:
        logger.exception(
            "create_payment failed for order_id=%s provider_ref=%s",
            order_id,
            provider_ref,
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
        "provider_ref": provider_ref,
        "approval_url": approval_url,
    }
