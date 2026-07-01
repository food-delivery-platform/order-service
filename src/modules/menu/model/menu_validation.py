"""DTOs for validating a cart against Menu Service (FDS-16)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MenuValidationItem:
    menu_item_id: str
    quantity: int


@dataclass
class MenuValidationRequest:
    restaurant_id: str
    items: list[MenuValidationItem]


@dataclass
class ValidatedMenuItem:
    menu_item_id: str
    name: str
    unit_price: float
    available: bool


@dataclass
class MenuValidationResult:
    valid: bool
    items: list[ValidatedMenuItem] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
