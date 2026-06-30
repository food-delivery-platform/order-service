"""Single line item inside an order (FDS-16)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class OrderItem:
    menu_item_id: str
    name: str
    quantity: int
    unit_price: float

    @property
    def line_total(self) -> float:
        return round(self.unit_price * self.quantity, 2)
