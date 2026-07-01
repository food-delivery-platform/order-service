"""Inbound delivery.* events consumed from SQS (FDS-16)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

class DeliveryStage(str, Enum):
    """Delivery progress reported by Delivery Service."""

    PICKED_UP = "PICKED_UP"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"

class DeliveryEventType(str, Enum):
    """Discriminator: which kind of inbound delivery event this is."""

    COURIER_ASSIGNED = "delivery.courier_assigned"
    STATUS_CHANGED = "delivery.status_changed"

@dataclass
class DeliveryCourierAssigned:
    order_id: str
    courier_id: str
    event_type: DeliveryEventType = DeliveryEventType.COURIER_ASSIGNED
    occurred_at: str | None = None

@dataclass
class DeliveryStatusChanged:
    order_id: str
    stage: DeliveryStage
    event_type: DeliveryEventType = DeliveryEventType.STATUS_CHANGED
    occurred_at: str | None = None
