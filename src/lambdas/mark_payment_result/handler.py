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

from pydantic import ValidationError

from src.lambdas.mark_payment_result.schema import MarkPaymentInput
from src.shared.errors.app_error import AppError
from src.shared.payments import payment_repository

logger = logging.getLogger(__name__)

_PROVIDER = "paypal"
_FAILURE_CODE = "PAYMENT_NOT_VERIFIED"
_FAILURE_MESSAGE = "PayPal payment did not match the order"


def handler(event, context=None):
    # ------------------------------------------------------------------
    # 1. Parse + validate input (Pydantic v2)
    # ------------------------------------------------------------------
    try:
        data = MarkPaymentInput.model_validate(event)
    except ValidationError as exc:
        raise AppError(400, "INVALID_INPUT", str(exc)) from exc

    # ------------------------------------------------------------------
    # 2. Idempotently mark PAID or FAILED
    # ------------------------------------------------------------------
    if data.verified:
        applied = payment_repository.mark_paid(_PROVIDER, data.paypal_order_id)
        status = "PAID" if applied else "ALREADY_PAID"
    else:
        applied = payment_repository.mark_failed(
            _PROVIDER,
            data.paypal_order_id,
            failure_code=_FAILURE_CODE,
            failure_message=_FAILURE_MESSAGE,
        )
        status = "FAILED" if applied else "ALREADY_FAILED"

    return {
        "order_id": data.order_id,
        "paypal_order_id": data.paypal_order_id,
        "status": status,
        "applied": applied,
    }
