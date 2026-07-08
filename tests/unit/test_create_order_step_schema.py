"""Unit tests for CreateOrderStepEvent pydantic schema (FDS-24)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.lambdas.create_order_step.schema import CreateOrderStepEvent

_VALID = {
    "customer_id": "c1",
    "restaurant_id": "v1",
    "delivery_address": {
        "address_id": "a1",
        "street": "s",
        "city": "c",
        "postal_code": "p",
    },
    "validated_items": [
        {
            "menu_item_id": "m1",
            "name": "Pizza",
            "unit_price": 10.0,
            "quantity": 2,
        }
    ],
}


def test_valid_event_parses():
    ev = CreateOrderStepEvent(**_VALID)
    assert ev.customer_id == "c1"
    assert ev.validated_items[0].quantity == 2


def test_empty_items_rejected():
    bad = {**_VALID, "validated_items": []}
    with pytest.raises(ValidationError):
        CreateOrderStepEvent(**bad)


def test_missing_address_rejected():
    bad = {k: v for k, v in _VALID.items() if k != "delivery_address"}
    with pytest.raises(ValidationError):
        CreateOrderStepEvent(**bad)
