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

from src.lambdas.publish_order_event.schema import PublishInput
from src.shared.errors.app_error import AppError
from src.shared.events import event_publisher
from src.shared.validation import validated_input

logger = logging.getLogger(__name__)

_PAID_STATUSES = {"PAID", "ALREADY_PAID"}
# Both statuses mean the payment is confirmed paid; they differ only by
# idempotency: "PAID" = marked paid by THIS execution, "ALREADY_PAID" = was
# already paid by an earlier (retried/duplicate) run. Both must still emit
# the order.paid event, so they are grouped together here.
_SOURCE = "order-service"


@validated_input(PublishInput)
def handler(event, context=None):
    # ------------------------------------------------------------------
    # 1. Validated input (via decorator)
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # 2. Map persisted status → domain event name
    # ------------------------------------------------------------------
    event_name = (
        "order.paid" if event.status in _PAID_STATUSES else "order.payment_failed"
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
                "order_id": event.order_id,
                "paypal_order_id": event.paypal_order_id,
                "status": event.status,
            },
        )
    except Exception as exc:
        logger.exception(
            "EventBridge put_event failed for order_id=%s event_name=%s",
            event.order_id,
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
        "order_id": event.order_id,
    }
