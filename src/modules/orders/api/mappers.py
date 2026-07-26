"""Map internal Order models to API response shapes (FDS-21, FDS-24, FDS-27).

Field names/shape match docs/openapi.yaml's OrderResponse/OrderItem schemas
exactly (camelCase) — hardcoded here rather than derived generically, since
the response contract is fixed and documented.
"""

from __future__ import annotations

from src.modules.orders.model.order import Order
from src.shared.payments import payment_repository


def to_order_response(order: Order) -> dict:
    """Serialize an Order to the OrderResponse shape from docs/openapi.yaml.

    ``approvalUrl`` is looked up from the most recent payment session for
    this order (FDS-27) and is ``None`` until ``CreatePaymentSession`` has
    run. This adds one extra query per order — acceptable for now given
    get_customer_orders' list sizes, but worth revisiting (e.g. a join) if
    that changes.
    """
    payment = payment_repository.get_by_order_id(order.order_id)
    approval_url = payment.approval_url or None if payment else None

    return {
        "orderId": order.order_id,
        "customerId": order.customer_id,
        "restaurantId": order.restaurant_id,
        "status": order.status.value,
        "items": [
            {
                "menuItemId": item.menu_item_id,
                "name": item.name,
                "quantity": item.quantity,
                "unitPrice": item.unit_price,
                "lineTotal": item.line_total,
            }
            for item in order.items
        ],
        "total": order.subtotal,
        "createdAt": order.created_at,
        "updatedAt": order.updated_at,
        "approvalUrl": approval_url,
    }
