"""Step Functions step - validate the customer's cart via Menu Service (FDS-21).

This is the first step of the order creation flow. On an invalid cart it
returns a structured result with ``valid = False`` so the state machine can
stop the flow via a Choice state, instead of letting an exception bubble up.
"""

from src.modules.orders.validation import cart_validation_service
from src.shared.errors.app_error import AppError


def handler(event, context=None):
    restaurant_id = event.get("restaurant_id")
    items = event.get("items", [])

    try:
        result = cart_validation_service.validate_cart(restaurant_id, items)
    except AppError as err:
        return {
            "order_id": event.get("order_id"),
            "customer_id": event.get("customer_id"),
            "restaurant_id": restaurant_id,
            "valid": False,
            "error": err.code,
            "message": err.message,
            "validated_items": [],
        }

    return {
        "order_id": event.get("order_id"),
        "customer_id": event.get("customer_id"),
        "restaurant_id": restaurant_id,
        "valid": result.valid,
        "validated_items": [
            {
                "menu_item_id": i.menu_item_id,
                "name": i.name,
                "unit_price": i.unit_price,
                "available": i.available,
            }
            for i in result.items
        ],
    }
