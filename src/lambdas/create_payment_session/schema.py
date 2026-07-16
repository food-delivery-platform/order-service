"""Pydantic models for CreatePaymentSession input validation (FDS-27 R3).

Validates the Step Functions event payload before the handler processes it,
replacing manual ``if not`` / ``try/except`` checks with declarative validation.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class CreatePaymentSessionInput(BaseModel):
    """Validated input for the create_payment_session Lambda.

    Money is kept as ``Decimal`` — never ``float``. Pydantic v2 coerces
    int/float/str -> Decimal natively; Field(gt=0) enforces positivity.
    """

    order_id: str = Field(..., min_length=1)
    amount: Decimal = Field(..., gt=0)
    currency: str = Field(..., min_length=3, max_length=3)
