"""Delivery address value object (FDS-16)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DeliveryAddress:
    address_id: str
    street: str | None = None
    city: str | None = None
    postal_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    notes: str | None = None
