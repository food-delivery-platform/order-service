"""Map internal Order models to API response shapes (FDS-21)."""

from __future__ import annotations

from dataclasses import asdict

from src.modules.orders.model.order import Order


def to_order_response(order: Order) -> dict:
    """Serialize an Order (incl. delivery_address) to a response dict.

    Uses dataclasses.asdict for the field mapping and then adds the computed
    @property values (total, line_total), which asdict does not include.
    """
    data = asdict(order)
    data["status"] = order.status.value
    data["total"] = order.total
    for item, item_data in zip(order.items, data["items"]):
        item_data["line_total"] = item.line_total
    return data
