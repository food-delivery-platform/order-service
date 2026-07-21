"""Pydantic models for verify_payment input validation (FDS-27 P2-C8).

Validates the input event (output of ``paypal_webhook``) before the handler
verifies the PayPal payment against the stored order.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.shared.payments.validators import PaypalId


class VerifyPaymentInput(BaseModel):
    """Validated input for the verify_payment Lambda."""

    paypal_order_id: PaypalId
    event_type: str = Field(..., min_length=1)
