"""Outbound order.* events published by Order Service to SNS (FDS-16)."""
from __future__ import annotations

from dataclasses import dataclass, field

from src.modules.orders.model.order_status import OrderStatus


@dataclass
class OrderEvent:
    type: str  # e.g. "order.created", "order.paid", "order.cancelled"
    order_id: str
    status: OrderStatus
    occurred_at: str  # ISO-8601 timestamp
    payload: dict = field(default_factory=dict)
