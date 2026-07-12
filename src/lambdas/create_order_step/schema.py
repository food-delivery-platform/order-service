"""Pydantic models for CreateOrderStep input validation (FDS-24).

Validates the Step Functions event payload before the handler processes it,
replacing manual ``if not`` checks with declarative validation.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DeliveryAddressInput(BaseModel):
    """Delivery address carried in the event (resolved by FDS-25 step)."""

    address_id: str
    street: str
    city: str
    postal_code: str
    latitude: float | None = None
    longitude: float | None = None
    notes: str | None = None


class ValidatedItemInput(BaseModel):
    """Single validated cart item from the validate_order step."""

    menu_item_id: str
    name: str
    unit_price: float
    quantity: int
    available: bool | None = None


class CreateOrderStepEvent(BaseModel):
    """Full event payload for the CreateOrderStep Lambda."""

    order_id: str | None = None
    customer_id: str
    restaurant_id: str
    delivery_address: DeliveryAddressInput
    validated_items: list[ValidatedItemInput] = Field(min_length=1)
