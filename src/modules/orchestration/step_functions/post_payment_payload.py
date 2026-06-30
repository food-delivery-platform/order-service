"""Input payload for the post-payment Step Functions state machine (FDS-16)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PostPaymentPayload:
    order_id: str
    customer_id: str
    restaurant_id: str
    payment_session_id: str
