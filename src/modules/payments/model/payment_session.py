"""DTOs for creating a payment session via Payment Service (FDS-16)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PaymentSessionStatus(str, Enum):
    CREATED = "CREATED"
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


@dataclass
class CreatePaymentSessionRequest:
    order_id: str
    amount: float
    currency: str = "EUR"


@dataclass
class PaymentSession:
    session_id: str
    order_id: str
    status: PaymentSessionStatus
    checkout_url: str | None = None
    expires_at: str | None = None
