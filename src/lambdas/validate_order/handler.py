"""Step Functions step - validate the customer's cart via Menu Service (FDS-21).

This is the first step of the order creation flow. It stops the flow (by
raising) when the cart is invalid, and otherwise returns validated cart data
for the next orchestration step.
"""

from src.modules.orders.validation import cart_validation_service


def handler(event, context=None):
    restaurant_id = event["restaurant_id"]
    items = event.get("items", [])
    result = cart_validation_service.validate_cart(restaurant_id, items)
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
