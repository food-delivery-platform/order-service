"""Payment domain models (FDS-27).

Pydantic models for payment sessions and payment verification results.
All money amounts use ``Decimal`` — never ``float``.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class PaymentStatus(str, Enum):
    """Status of a payment session tracked by Order Service."""

    CREATED = "CREATED"
    PAID = "PAID"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class PaymentSession(BaseModel):
    """A payment session linked to a PayPal checkout order."""

    order_id: str = Field(..., min_length=1, description="Internal order id")
    paypal_order_id: str = Field(..., min_length=1, description="PayPal-side order id")
    approval_url: str = Field(default="", description="PayPal approval/checkout URL")
    amount: Decimal = Field(..., gt=0, description="Payment amount")
    currency: str = Field(
        ..., min_length=3, max_length=3, description="ISO 4217 currency code"
    )
    status: PaymentStatus = Field(
        default=PaymentStatus.CREATED, description="Current session status"
    )


class PaymentVerification(BaseModel):
    """Result of verifying a PayPal payment (after customer approval)."""

    paypal_order_id: str = Field(
        ..., min_length=1, description="PayPal-side order id that was verified"
    )
    status: str = Field(
        ..., min_length=1, description="PayPal order status (e.g. APPROVED, COMPLETED)"
    )
    amount: Decimal = Field(..., gt=0, description="Captured/approved amount")
    currency: str = Field(
        ..., min_length=3, max_length=3, description="ISO 4217 currency code"
    )
