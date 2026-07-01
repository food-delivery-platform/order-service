"""Read-side service methods for orders (FDS-21)."""

from __future__ import annotations

from src.modules.orders.model.order import Order
from src.modules.orders.repository import order_repository
from src.shared.errors.app_error import AppError


def get_customer_orders(customer_id: str) -> list[Order]:
    if not customer_id:
        raise AppError(400, "MISSING_CUSTOMER_ID", "customerId is required")
    return order_repository.get_orders_by_customer(customer_id)


def get_order_by_id(order_id: str) -> Order:
    if not order_id:
        raise AppError(400, "MISSING_ORDER_ID", "orderId is required")
    order = order_repository.get_order_by_id(order_id)
    if order is None:
        raise AppError(404, "ORDER_NOT_FOUND", f"Order {order_id} was not found")
    return order
