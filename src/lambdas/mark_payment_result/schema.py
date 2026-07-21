"""Pydantic models for mark_payment_result input validation (FDS-27 P2-C9).

Validates the input event (output of ``verify_payment``) before the handler
marks the payment as PAID or FAILED.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field, field_validator


class MarkPaymentInput(BaseModel):
    """Validated input for the mark_payment_result Lambda."""

    verified: bool
    order_id: str = Field(..., min_length=1)
    paypal_order_id: str = Field(..., min_length=1)

    @field_validator("order_id")
    @classmethod
    def _order_id_is_uuid(cls, v: str) -> str:
        uuid.UUID(v)  # raises ValueError if not a valid UUID
        return v
