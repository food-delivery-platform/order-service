"""Step Functions step - validate the customer's cart via Menu Service (FDS-21).

This is the first step of the order creation flow. On an invalid cart it
returns a structured result with ``valid = False`` so the state machine can
stop the flow via a Choice state, instead of letting an exception bubble up.
"""

from src.modules.orders.validation import cart_validation_service
from src.shared.errors.app_error import AppError


def handler(event, context=None):
    restaurant_id = event["restaurant_id"]
    items = event.get("items", [])

    # --- pass-through fields: downstream steps need these ---
    delivery_address = event.get("delivery_address")
    delivery_address_id = event.get("delivery_address_id")

    try:
        result = cart_validation_service.validate_cart(restaurant_id, items)
    except AppError as err:
        return {
            "order_id": event.get("order_id"),
            "customer_id": event.get("customer_id"),
            "restaurant_id": restaurant_id,
            "delivery_address": delivery_address,
            "delivery_address_id": delivery_address_id,
            "valid": False,
            "error": err.code,
            "message": err.message,
            "validated_items": [],
        }

    # Merge original quantities into the validated items so downstream steps
    # (e.g. CreateOrderStep) can compute line totals without re-fetching.
    # If a validated item has no matching cart entry (data inconsistency),
    # quantity defaults to 0 — the service will produce a line_total of 0.
    qty_by_id: dict[str, int] = {i["menu_item_id"]: int(i["quantity"]) for i in items}
    return {
        "order_id": event.get("order_id"),
        "customer_id": event.get("customer_id"),
        "restaurant_id": restaurant_id,
        "delivery_address": delivery_address,
        "delivery_address_id": delivery_address_id,
        "valid": result.valid,
        "validated_items": [
            {
                "menu_item_id": vi.menu_item_id,
                "name": vi.name,
                "unit_price": vi.unit_price,
                "quantity": qty_by_id.get(vi.menu_item_id, 0),
                "available": vi.available,
            }
            for vi in result.items
        ],
    }
