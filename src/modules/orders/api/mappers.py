"""Map internal Order models to API response shapes (FDS-21, FDS-24).

Internal fields (status_history, cancel_reason) are stripped from the response.
currency is preserved (FDS-24).

Note: delivery_address fields (street, city, postal_code) may be null until
FDS-25 implements the full address join.
"""

from __future__ import annotations

from dataclasses import asdict

from src.modules.orders.model.order import Order


def to_order_response(order: Order) -> dict:
    """Serialize an Order (incl. delivery_address) to a response dict.

    Internal fields (status_history, cancel_reason) are stripped.
    currency is kept in the response (FDS-24).
    """
    data = asdict(order)
    data.pop("status_history", None)
    data.pop("cancel_reason", None)
    data["status"] = order.status.value
    data["total"] = order.subtotal
    return data
