"""Map internal Order models to API response shapes (FDS-21, FDS-24)."""

from __future__ import annotations

from dataclasses import asdict

from src.modules.orders.model.order import Order


def to_order_response(order: Order) -> dict:
    """Serialize an Order (incl. delivery_address) to a response dict.

    Uses dataclasses.asdict for the field mapping.  line_total is now a
    regular OrderItem field (FDS-24) so asdict includes it automatically.
    Internal fields (status_history, cancel_reason, currency) are stripped.
    """
    data = asdict(order)
    data.pop("status_history", None)
    data.pop("cancel_reason", None)
    data.pop("currency", None)
    data["status"] = order.status.value
    data["total"] = order.subtotal
    return data
