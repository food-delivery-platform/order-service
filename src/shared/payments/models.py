"""Payment domain models (FDS-27 R2).

Pydantic models for payment sessions and payment verification results.
All money amounts use ``Decimal`` — never ``float``.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field


class PaymentStatus(StrEnum):
    """Status of a payment session tracked by Order Service (DB enum)."""

    PENDING = "PENDING"
    CUSTOMER_ACTION_REQUIRED = "CUSTOMER_ACTION_REQUIRED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class PaymentSession(BaseModel):
    """A payment session linked to a payment provider order."""

    order_id: str = Field(..., min_length=1, description="Internal order id")
    provider: str = Field(
        default="paypal", min_length=1, description="Payment provider"
    )
    provider_ref: str = Field(..., min_length=1, description="Provider-side order id")
    approval_url: str = Field(default="", description="Provider approval/checkout URL")
    amount: Decimal = Field(..., gt=0, description="Payment amount")
    currency: str = Field(
        ..., min_length=3, max_length=3, description="ISO 4217 currency code"
    )
    status: PaymentStatus = Field(
        default=PaymentStatus.PENDING, description="Current session status"
    )


class PaymentVerification(BaseModel):
    """Result of verifying a payment (after customer approval)."""

    provider: str = Field(
        default="paypal", min_length=1, description="Payment provider"
    )
    provider_ref: str = Field(
        ..., min_length=1, description="Provider-side order id that was verified"
    )
    status: str = Field(
        ...,
        min_length=1,
        description="Provider order status (e.g. APPROVED, COMPLETED)",
    )
    amount: Decimal = Field(..., gt=0, description="Captured/approved amount")
    currency: str = Field(
        ..., min_length=3, max_length=3, description="ISO 4217 currency code"
    )
