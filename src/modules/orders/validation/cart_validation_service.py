"""Cart validation step of the order creation flow (FDS-21).

Delegates the actual validation to Menu Service and stops the flow when
the cart is invalid.
"""

from __future__ import annotations

from src.modules.menu.client import menu_service_client
from src.modules.menu.model.menu_validation import (
    MenuValidationItem,
    MenuValidationRequest,
    MenuValidationResult,
)
from src.shared.errors.app_error import AppError


def validate_cart(restaurant_id: str, items: list[dict]) -> MenuValidationResult:
    """Validate the customer's cart via Menu Service.

    Raises AppError(422) if Menu Service reports the cart as invalid.
    Returns the validated cart data for the next orchestration step.
    """
    request = MenuValidationRequest(
        restaurant_id=restaurant_id,
        items=[
            MenuValidationItem(
                menu_item_id=i["menu_item_id"], quantity=int(i["quantity"])
            )
            for i in items
        ],
    )
    result = menu_service_client.validate_cart(request)
    if not result.valid:
        raise AppError(
            422,
            "CART_VALIDATION_FAILED",
            "; ".join(result.errors) or "Menu Service rejected the cart",
        )
    return result
