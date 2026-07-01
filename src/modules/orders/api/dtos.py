"""Request/response DTOs for Order Service API endpoints (FDS-16).

DTOs are the shapes that cross the API boundary; they are intentionally
separate from the internal domain models.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.modules.orders.model.order_status import OrderStatus


@dataclass
class CreateOrderItemDTO:
    menu_item_id: str
    quantity: int


@dataclass
class CreateOrderRequest:
    customer_id: str
    restaurant_id: str
    items: list[CreateOrderItemDTO]
    delivery_address_id: str


@dataclass
class OrderItemDTO:
    menu_item_id: str
    name: str
    quantity: int
    unit_price: float
    line_total: float


@dataclass
class OrderResponse:
    order_id: str
    customer_id: str
    restaurant_id: str
    status: OrderStatus
    items: list[OrderItemDTO] = field(default_factory=list)
    total: float = 0.0
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class OrderStatusResponse:
    order_id: str
    status: OrderStatus
    updated_at: str | None = None


@dataclass
class CancelOrderRequest:
    reason: str | None = None
