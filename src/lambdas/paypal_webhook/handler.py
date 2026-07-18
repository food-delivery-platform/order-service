"""API Gateway Lambda — receive and verify PayPal webhook notifications (FDS-27 P2-C6).

Verifies the webhook signature using the existing ``PayPalClient.verify_webhook_signature``
and normalises the event into a compact dict for the second state machine.

The incoming ``event`` is the standard API Gateway proxy integration format:
``headers`` (or ``multiValueHeaders``) + ``body`` (raw JSON string).
"""

from __future__ import annotations

import json
import logging

from pydantic import ValidationError

from src.lambdas.paypal_webhook.schema import WebhookBody
from src.shared.errors.app_error import AppError
from src.shared.payments.paypal_client import verify_webhook_signature

logger = logging.getLogger(__name__)

# PayPal webhook header names (API Gateway lowercases them).
_HEADER_TRANSMISSION_ID = "paypal-transmission-id"
_HEADER_TRANSMISSION_TIME = "paypal-transmission-time"
_HEADER_CERT_URL = "paypal-cert-url"
_HEADER_AUTH_ALGO = "paypal-auth-algo"
_HEADER_TRANSMISSION_SIG = "paypal-transmission-sig"


def _extract_headers(event: dict) -> dict:
    """Pull the PayPal webhook headers from an API Gateway event.

    API Gateway delivers headers in either ``headers`` or
    ``multiValueHeaders`` — both are lowercased.
    """
    raw = event.get("headers") or event.get("multiValueHeaders") or {}
    # multiValueHeaders values are lists; flatten to single string.
    flat: dict[str, str] = {}
    for key, value in raw.items():
        flat[key.lower()] = value[0] if isinstance(value, list) else value
    return flat


def handler(event, context=None):
    # ------------------------------------------------------------------
    # 1. Extract PayPal webhook headers
    # ------------------------------------------------------------------
    headers = _extract_headers(event)

    # ------------------------------------------------------------------
    # 2. Get raw body (must be the raw string — do NOT re-serialize)
    # ------------------------------------------------------------------
    raw_body = event.get("body", "")
    if not raw_body:
        raise AppError(400, "MISSING_BODY", "Webhook request has no body")

    # ------------------------------------------------------------------
    # 3. Verify webhook signature (reuse existing PayPalClient method)
    # ------------------------------------------------------------------
    if not verify_webhook_signature(headers, raw_body):
        raise AppError(
            401, "WEBHOOK_UNVERIFIED", "PayPal webhook signature verification failed"
        )

    # ------------------------------------------------------------------
    # 4. Parse + validate body via Pydantic
    # ------------------------------------------------------------------
    try:
        parsed = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise AppError(
            400, "INVALID_JSON", f"Webhook body is not valid JSON: {exc}"
        ) from exc

    try:
        body = WebhookBody.model_validate(parsed)
    except ValidationError as exc:
        raise AppError(400, "INVALID_WEBHOOK_PAYLOAD", str(exc)) from exc

    # ------------------------------------------------------------------
    # 5. Return normalised event for the second state machine
    # ------------------------------------------------------------------
    return {
        "event_type": body.event_type,
        "paypal_order_id": body.resource.id,
        "status": body.resource.status,
    }
