"""Step Functions step — create and persist an order (FDS-24).

This step runs RIGHT AFTER a successful cart validation.  It receives the
validated cart data, snapshots every line item, computes totals, persists the
order via the repository, and returns it as input for the next step (payment).
"""

from __future__ import annotations

from src.modules.orders.model.delivery_address import DeliveryAddress
from src.modules.orders.service import order_create_service
from src.shared.errors.app_error import AppError


def handler(event, context=None):
    order_id = event.get("order_id")
    customer_id = event.get("customer_id")
    restaurant_id = event.get("restaurant_id")
    validated_items = event.get("validated_items", [])

    if not customer_id:
        raise AppError(400, "MISSING_CUSTOMER_ID", "customer_id is required")
    if not restaurant_id:
        raise AppError(400, "MISSING_RESTAURANT_ID", "restaurant_id is required")
    if not validated_items:
        raise AppError(400, "EMPTY_CART", "validated_items must not be empty")

    # Build DeliveryAddress from the event.  In production the address is
    # threaded through the Step Functions input; for local testing it can be
    # included in the event.
    address_data = event.get("delivery_address")
    if not address_data:
        raise AppError(
            400,
            "MISSING_DELIVERY_ADDRESS",
            "delivery_address is required to create an order",
        )
    missing = [
        f
        for f in ("address_id", "street", "city", "postal_code")
        if not address_data.get(f)
    ]
    if missing:
        raise AppError(
            400,
            "INCOMPLETE_DELIVERY_ADDRESS",
            f"delivery_address missing fields: {', '.join(missing)}",
        )
    delivery_address = DeliveryAddress(
        address_id=address_data["address_id"],
        street=address_data["street"],
        city=address_data["city"],
        postal_code=address_data["postal_code"],
        latitude=address_data.get("latitude"),
        longitude=address_data.get("longitude"),
        notes=address_data.get("notes"),
    )

    try:
        order = order_create_service.create_order(
            customer_id=customer_id,
            restaurant_id=restaurant_id,
            validated_items=validated_items,
            delivery_address=delivery_address,
            order_id=order_id,
        )
    except AppError:
        raise
    except Exception as exc:
        raise AppError(
            500,
            "ORDER_CREATION_FAILED",
            f"Failed to create order: {exc}",
        ) from exc

    # Return the created order as input for the next Step Functions step.
    return {
        "order_id": order.order_id,
        "customer_id": order.customer_id,
        "restaurant_id": order.restaurant_id,
        "status": order.status.value,
        "subtotal": order.subtotal,
        "currency": order.currency,
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
        "created_at": order.created_at,
    }
