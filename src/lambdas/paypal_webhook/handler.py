"""API Gateway Lambda — receive and verify PayPal webhook notifications (FDS-27 P2-C6).

Verifies the webhook signature using the existing ``PayPalClient.verify_webhook_signature``,
normalises the event into a compact dict, starts the payment-confirmation state machine,
and returns a proper API Gateway proxy integration response.

The incoming ``event`` is the standard API Gateway proxy integration format:
``headers`` (or ``multiValueHeaders``) + ``body`` (raw JSON string).
"""

from __future__ import annotations

import json
import logging
import os

import boto3
from pydantic import ValidationError

from src.lambdas.paypal_webhook.schema import WebhookBody
from src.shared.errors.app_error import AppError
from src.shared.http.api_response import error as api_error
from src.shared.http.api_response import from_app_error, ok
from src.shared.payments.paypal_client import verify_webhook_signature

logger = logging.getLogger(__name__)

_SM_ARN_ENV = "PAYMENT_CONFIRMATION_SM_ARN"


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
    try:
        # --------------------------------------------------------------
        # 1. Extract PayPal webhook headers
        # --------------------------------------------------------------
        headers = _extract_headers(event)

        # --------------------------------------------------------------
        # 2. Get raw body (must be the raw string — do NOT re-serialize)
        # --------------------------------------------------------------
        raw_body = event.get("body", "")
        if not raw_body:
            raise AppError(400, "MISSING_BODY", "Webhook request has no body")

        # --------------------------------------------------------------
        # 3. Verify webhook signature (reuse existing PayPalClient method)
        # --------------------------------------------------------------
        if not verify_webhook_signature(headers, raw_body):
            raise AppError(
                401,
                "WEBHOOK_UNVERIFIED",
                "PayPal webhook signature verification failed",
            )

        # --------------------------------------------------------------
        # 4. Parse + validate body via Pydantic
        # --------------------------------------------------------------
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

        # --------------------------------------------------------------
        # 5. Build normalised event for the second state machine
        # --------------------------------------------------------------
        normalised = {
            "event_type": body.event_type,
            "paypal_order_id": body.resource.id,
            "status": body.resource.status,
        }

        # --------------------------------------------------------------
        # 6. Read state machine ARN from env
        # --------------------------------------------------------------
        sm_arn = os.environ.get(_SM_ARN_ENV, "").strip()
        if not sm_arn:
            return api_error(
                500,
                "MISSING_SM_ARN",
                f"Environment variable {_SM_ARN_ENV} is not set",
            )

        # --------------------------------------------------------------
        # 7. Start the payment-confirmation state machine
        # --------------------------------------------------------------
        sfn = boto3.client("stepfunctions")
        sfn.start_execution(
            stateMachineArn=sm_arn,
            input=json.dumps(normalised),
        )

        logger.info(
            "Started payment-confirmation SM for PayPal order %s",
            normalised["paypal_order_id"],
        )

        return ok(
            {
                "status": "accepted",
                "paypal_order_id": normalised["paypal_order_id"],
            }
        )

    except AppError as err:
        return from_app_error(err)
