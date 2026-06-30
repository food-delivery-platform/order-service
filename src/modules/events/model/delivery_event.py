"""Inbound delivery.* events consumed from SQS (FDS-16)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DeliveryStage(str, Enum):
    PICKED_UP = "PICKED_UP"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"


@dataclass
class DeliveryCourierAssigned:
    type: str
    order_id: str
    courier_id: str
    occurred_at: str | None = None


@dataclass
class DeliveryStatusChanged:
    type: str
    order_id: str
    stage: DeliveryStage
    occurred_at: str | None = None
