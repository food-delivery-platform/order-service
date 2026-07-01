"""Order aggregate root (FDS-16)."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.modules.orders.model.cancel_reason import CancelReason
from src.modules.orders.model.delivery_address import DeliveryAddress
from src.modules.orders.model.order_item import OrderItem
from src.modules.orders.model.order_status import OrderStatus
from src.modules.orders.model.order_status_history import OrderStatusHistoryEntry


@dataclass
class Order:
    order_id: str
    customer_id: str
    restaurant_id: str
    items: list[OrderItem]
    delivery_address: DeliveryAddress
    status: OrderStatus = OrderStatus.CREATED
    status_history: list[OrderStatusHistoryEntry] = field(default_factory=list)
    cancel_reason: CancelReason | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @property
    def total(self) -> float:
        return round(sum(item.line_total for item in self.items), 2)
