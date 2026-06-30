"""Inbound payment.* events consumed from SQS (FDS-16)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PaymentFailureReason(str, Enum):
    CARD_DECLINED = "CARD_DECLINED"
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    EXPIRED_SESSION = "EXPIRED_SESSION"
    OTHER = "OTHER"


class DeclineType(str, Enum):
    SOFT = "SOFT"
    HARD = "HARD"


@dataclass
class PaymentSucceeded:
    type: str
    order_id: str
    occurred_at: str | None = None


@dataclass
class PaymentFailed:
    type: str
    order_id: str
    reason: PaymentFailureReason = PaymentFailureReason.OTHER
    decline_type: DeclineType | None = None
    occurred_at: str | None = None
