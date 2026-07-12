"""Single line item inside an order (FDS-16, FDS-24).

All fields are a snapshot captured at order-creation time. No calculations
live inside the model — the service layer computes line_total and subtotal.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class OrderItem:
    menu_item_id: str
    name: str
    quantity: int
    unit_price: float
    line_total: float = 0.0
