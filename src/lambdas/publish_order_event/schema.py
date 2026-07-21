"""Pydantic models for publish_order_event input validation (FDS-27 P2-C11).

Validates the input event (output of ``mark_payment_result``) before the
handler emits the domain event to EventBridge.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class PublishInput(BaseModel):
    """Validated input for the publish_order_event Lambda."""

    order_id: UUID
    paypal_order_id: str = Field(..., min_length=1)
    status: str = Field(..., min_length=1)
