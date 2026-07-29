"""Pydantic models for the POST /api/v1/orders request body (FDS-42).

Field names mirror the state machine payload: validate_order reads
``restaurant_id`` and ``items``, resolve_delivery_address reads
``delivery_address`` and ``delivery_address_id``, and create_order_step
reads ``customer_id``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class DeliveryAddressRequest(BaseModel):
    """Delivery address in the create order request."""

    street: str = Field(..., min_length=1)
    city: str = Field(..., min_length=1)
    postal_code: str = Field(..., min_length=1)


class CartItemRequest(BaseModel):
    """Single cart item in the create order request."""

    menu_item_id: str = Field(..., min_length=1)
    quantity: int = Field(..., gt=0)


class CreateOrderRequest(BaseModel):
    """Validated body for POST /api/v1/orders.

    Extra fields are forbidden — the API rejects unknown keys with a 400.
    """

    model_config = ConfigDict(extra="forbid")

    customer_id: str = Field(..., min_length=1)
    restaurant_id: str = Field(..., min_length=1)
    items: list[CartItemRequest] = Field(..., min_length=1)
    delivery_address: DeliveryAddressRequest | None = None
    delivery_address_id: str | None = None
