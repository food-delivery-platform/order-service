"""Pydantic models for mark_payment_result input validation (FDS-27 P2-C9).

Validates the input event (output of ``verify_payment``) before the handler
marks the payment as PAID or FAILED.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from src.shared.payments.validators import PaypalId


class MarkPaymentInput(BaseModel):
    """Validated input for the mark_payment_result Lambda."""

    verified: bool
    order_id: UUID
    paypal_order_id: PaypalId
