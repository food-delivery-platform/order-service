"""Input payload for the pre-payment Step Functions state machine (FDS-16)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PrePaymentPayload:
    order_id: str
    customer_id: str
    restaurant_id: str
    amount: float
    items: list[dict] = field(default_factory=list)
