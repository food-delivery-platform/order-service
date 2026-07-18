"""Pydantic models for PayPal webhook notification validation (FDS-27 P2-C6).

Validates the parsed JSON body of an incoming PayPal webhook POST before
the handler normalizes and returns it.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class WebhookResource(BaseModel):
    """The ``resource`` object inside a PayPal webhook notification."""

    id: str = Field(..., min_length=1)
    status: str = Field(..., min_length=1)


class WebhookBody(BaseModel):
    """Validated PayPal webhook notification body.

    Only the fields needed downstream are modelled — PayPal sends many more
    that are simply ignored.
    """

    event_type: str = Field(..., min_length=1)
    resource: WebhookResource
