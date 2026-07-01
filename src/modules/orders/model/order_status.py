"""Canonical order status values (FDS-16).

Only these statuses are allowed across Order Service. Restaurant-side
`preparing`/`ready` stages live on the restaurant frontend, not here.
"""

from __future__ import annotations

from enum import Enum


class OrderStatus(str, Enum):
    CREATED = "CREATED"
    PENDING_PAYMENT = "PENDING_PAYMENT"
    PAID = "PAID"
    READY = "READY"
    PICKED_UP = "PICKED_UP"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
