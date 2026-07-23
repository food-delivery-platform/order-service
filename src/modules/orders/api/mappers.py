"""Map internal Order models to API response shapes (FDS-21, FDS-24, FDS-27).

Internal fields (status_history, cancel_reason) are stripped from the response.
currency is preserved (FDS-24).

Note: delivery_address fields (street, city, postal_code) may be null until
FDS-25 implements the full address join.
"""

from __future__ import annotations

from dataclasses import asdict

from src.modules.orders.model.order import Order
from src.shared.payments import payment_repository


def to_order_response(order: Order) -> dict:
    """Serialize an Order (incl. delivery_address) to a response dict.

    Internal fields (status_history, cancel_reason) are stripped.
    currency is kept in the response (FDS-24).

    ``approval_url`` is looked up from the most recent payment session for
    this order (FDS-27) and is ``None`` until ``CreatePaymentSession`` has
    run. This adds one extra query per order — acceptable for now given
    get_customer_orders' list sizes, but worth revisiting (e.g. a join) if
    that changes.
    """
    data = asdict(order)
    data.pop("status_history", None)
    data.pop("cancel_reason", None)
    data["status"] = order.status.value
    data["total"] = order.subtotal

    payment = payment_repository.get_by_order_id(order.order_id)
    data["approval_url"] = payment.approval_url or None if payment else None

    return data
