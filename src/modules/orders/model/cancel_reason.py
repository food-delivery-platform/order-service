"""Reasons an order can be cancelled or fail (FDS-16)."""

from __future__ import annotations

from enum import Enum


class CancelReason(str, Enum):
    PAYMENT_FAILED = "PAYMENT_FAILED"
    RESTAURANT_REJECTED = "RESTAURANT_REJECTED"
    RESTAURANT_TIMEOUT = "RESTAURANT_TIMEOUT"
    INVALID_ORDER = "INVALID_ORDER"
    CUSTOMER_CANCELLED = "CUSTOMER_CANCELLED"
