"""Pydantic models for CreatePaymentSession input validation (FDS-27 R3).

Validates the Step Functions event payload before the handler processes it,
replacing manual ``if not`` / ``try/except`` checks with declarative validation.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, Field, field_validator


class CreatePaymentSessionInput(BaseModel):
    """Validated input for the create_payment_session Lambda.

    Money is kept as ``Decimal`` — never ``float``.
    """

    order_id: str = Field(..., min_length=1)
    amount: Decimal = Field(..., gt=0)
    currency: str = Field(..., min_length=3, max_length=3)

    @field_validator("amount", mode="before")
    @classmethod
    def _coerce_amount(cls, v: object) -> Decimal:
        """Convert float/int/str to Decimal and reject unparseable values."""
        try:
            return Decimal(str(v))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("amount must be a valid number") from exc
