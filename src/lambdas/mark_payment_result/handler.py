"""Step Functions step — persist verification result as PAID or FAILED (FDS-27 P2-C9).

This step runs after ``verify_payment`` and idempotently marks the payment
as PAID (if verified) or FAILED (if not verified).  Uses the atomic
``payment_repository.mark_paid`` / ``mark_failed`` which are safe to retry.

Input:
    ``{ "verified": bool, "order_id": str, "paypal_order_id": str }``
    — output of verify_payment (C8)

Output:
    ``{ "order_id": str, "paypal_order_id": str, "status": str, "applied": bool }``
"""

from __future__ import annotations

import logging

from src.lambdas.mark_payment_result.schema import MarkPaymentInput
from src.shared.payments import payment_repository
from src.shared.validation import validated_input

logger = logging.getLogger(__name__)

_PROVIDER = "paypal"
_FAILURE_CODE = "PAYMENT_NOT_VERIFIED"
_FAILURE_MESSAGE = "PayPal payment did not match the order"


@validated_input(MarkPaymentInput)
def handler(event, context=None):
    # ------------------------------------------------------------------
    # 1. Validated input (via decorator)
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # 2. Idempotently mark PAID or FAILED
    # ------------------------------------------------------------------
    if event.verified:
        applied = payment_repository.mark_paid(_PROVIDER, event.paypal_order_id)
        status = "PAID" if applied else "ALREADY_PAID"
    else:
        applied = payment_repository.mark_failed(
            _PROVIDER,
            event.paypal_order_id,
            failure_code=_FAILURE_CODE,
            failure_message=_FAILURE_MESSAGE,
        )
        status = "FAILED" if applied else "ALREADY_FAILED"

    return {
        "order_id": str(event.order_id),
        "paypal_order_id": event.paypal_order_id,
        "status": status,
        "applied": applied,
    }
