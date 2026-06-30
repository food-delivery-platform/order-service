"""One entry in an order status change history (FDS-16)."""
from __future__ import annotations

from dataclasses import dataclass

from src.modules.orders.model.order_status import OrderStatus


@dataclass
class OrderStatusHistoryEntry:
    status: OrderStatus
    changed_at: str  # ISO-8601 timestamp
    reason: str | None = None
