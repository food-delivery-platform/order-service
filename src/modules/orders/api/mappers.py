"""Map internal Order models to API response shapes (FDS-21)."""

from __future__ import annotations

from src.modules.orders.model.order import Order


def to_order_response(order: Order) -> dict:
    return {
        "order_id": order.order_id,
        "customer_id": order.customer_id,
        "restaurant_id": order.restaurant_id,
        "status": order.status.value,
        "items": [
            {
                "menu_item_id": item.menu_item_id,
                "name": item.name,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "line_total": item.line_total,
            }
            for item in order.items
        ],
        "total": order.total,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
    }
