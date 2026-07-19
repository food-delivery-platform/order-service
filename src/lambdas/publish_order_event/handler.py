"""Step Functions step — publish an order domain event to EventBridge (FDS-27 P2-C11).

This step runs after ``mark_payment_result`` (C9) has persisted the verification
result. It emits a domain event (``order.paid`` or ``order.payment_failed``) so
downstream services (Delivery, Notifications, Analytics) can react to the final
payment outcome.

Input:
    ``{ "order_id": str, "paypal_order_id": str, "status": str }``
    — output of mark_payment_result (C9). ``status`` is one of
    ``PAID`` / ``ALREADY_PAID`` / ``FAILED`` / ``ALREADY_FAILED``.

Output:
    ``{ "published": bool, "event_name": str, "order_id": str }``
"""

from __future__ import annotations

import logging

from pydantic import ValidationError

from src.lambdas.publish_order_event.schema import PublishInput
from src.shared.errors.app_error import AppError
from src.shared.events import event_publisher

logger = logging.getLogger(__name__)

_PAID_STATUSES = {"PAID", "ALREADY_PAID"}
_SOURCE = "order-service"


def handler(event, context=None):
    # ------------------------------------------------------------------
    # 1. Parse + validate input (Pydantic v2)
    # ------------------------------------------------------------------
    try:
        data = PublishInput.model_validate(event)
    except ValidationError as exc:
        raise AppError(400, "INVALID_INPUT", str(exc)) from exc

    # ------------------------------------------------------------------
    # 2. Map persisted status → domain event name
    # ------------------------------------------------------------------
    event_name = (
        "order.paid" if data.status in _PAID_STATUSES else "order.payment_failed"
    )

    # ------------------------------------------------------------------
    # 3. Publish to EventBridge
    # ------------------------------------------------------------------
    publisher = event_publisher.get_event_publisher()
    try:
        publisher.put_event(
            bus=event_publisher.get_bus_name(),
            source=_SOURCE,
            detail_type=event_name,
            detail={
                "order_id": data.order_id,
                "paypal_order_id": data.paypal_order_id,
                "status": data.status,
            },
        )
    except Exception as exc:
        logger.exception(
            "EventBridge put_event failed for order_id=%s event_name=%s",
            data.order_id,
            event_name,
        )
        raise AppError(
            500,
            "EVENT_PUBLISH_FAILED",
            f"Failed to publish {event_name}: {exc}",
        ) from exc

    # ------------------------------------------------------------------
    # 4. Return SM output
    # ------------------------------------------------------------------
    return {
        "published": True,
        "event_name": event_name,
        "order_id": data.order_id,
    }
