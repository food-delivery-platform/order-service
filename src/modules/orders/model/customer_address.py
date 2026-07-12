"""Customer address stored in the local ``addresses`` table (FDS-25).

Separate from ``DeliveryAddress`` (which is a value object embedded inside an
order).  CustomerAddress is the canonical address row linked to a customer.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CustomerAddress:
    address_id: str
    customer_id: str
    street: str
    city: str
    postal_code: str
    latitude: float | None = None
    longitude: float | None = None
    notes: str | None = None
    created_at: str | None = None
