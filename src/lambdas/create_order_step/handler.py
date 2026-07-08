"""Step Functions step — create and persist an order (FDS-24).

This step runs RIGHT AFTER a successful address resolution.  It receives the
validated cart data and a resolved delivery_address, snapshots every line
item, computes totals, persists the order via the repository, and returns it
as input for the next step (payment).

Input validation is handled by the ``CreateOrderStepEvent`` pydantic model
— no manual ``if not`` checks.
"""

from __future__ import annotations

from pydantic import ValidationError

from src.lambdas.create_order_step.schema import CreateOrderStepEvent
from src.modules.orders.model.delivery_address import DeliveryAddress
from src.modules.orders.service import order_create_service
from src.shared.errors.app_error import AppError


def handler(event, context=None):
    # --- pydantic validation (replaces all manual guards) ---
    try:
        data = CreateOrderStepEvent(**event)
    except ValidationError as e:
        raise AppError(400, "INVALID_EVENT", str(e)) from e

    # Build domain DeliveryAddress from the validated input.
    delivery_address = DeliveryAddress(
        address_id=data.delivery_address.address_id,
        street=data.delivery_address.street,
        city=data.delivery_address.city,
        postal_code=data.delivery_address.postal_code,
        latitude=data.delivery_address.latitude,
        longitude=data.delivery_address.longitude,
        notes=data.delivery_address.notes,
    )

    try:
        order = order_create_service.create_order(
            customer_id=data.customer_id,
            restaurant_id=data.restaurant_id,
            validated_items=[i.model_dump() for i in data.validated_items],
            delivery_address=delivery_address,
            order_id=data.order_id,
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
