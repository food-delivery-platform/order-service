"""Delivery address value object (FDS-16)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DeliveryAddress:
    address_id: str
    street: str
    city: str
    postal_code: str
    latitude: float | None = None
    longitude: float | None = None
    notes: str | None = None
