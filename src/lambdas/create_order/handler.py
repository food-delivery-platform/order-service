"""HTTP entry point — POST /api/v1/orders (FDS-42).

Starts the order creation state machine and returns 202 with the execution
identifier. The order row itself is created asynchronously by the machine.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import os
import uuid

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from pydantic import ValidationError

from src.lambdas.create_order.schema import CreateOrderRequest
from src.shared.http import api_response

logger = logging.getLogger(__name__)

STATE_MACHINE_ARN_ENV = "ORDER_CREATION_SM_ARN"

_stepfunctions = boto3.client("stepfunctions")


def _decode_body(event: dict) -> dict | None:
    """Decode and parse the request body from an API Gateway proxy event.

    API Gateway may base64-encode the body; ``isBase64Encoded`` tells us.
    Returns the parsed JSON dict, or ``None`` when the body is missing or
    malformed.
    """
    raw = event.get("body")
    if not raw:
        return None

    if event.get("isBase64Encoded"):
        try:
            raw = base64.b64decode(raw).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError):
            return None

    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def _format_validation_error(exc: ValidationError) -> str:
    """Format pydantic ``ValidationError`` into a human-readable string."""
    errors = exc.errors()
    messages = []
    for err in errors:
        loc = " -> ".join(str(p) for p in err["loc"])
        messages.append(f"{loc}: {err['msg']}")
    return "; ".join(messages)


def handler(event, context=None):
    # ----------------------------------------------------------------
    # 1. Decode request body
    # ----------------------------------------------------------------
    body = _decode_body(event)
    if body is None:
        return api_response.error(
            400, "INVALID_BODY", "Request body is missing or not valid JSON"
        )

    # ----------------------------------------------------------------
    # 2. Validate with pydantic
    # ----------------------------------------------------------------
    try:
        CreateOrderRequest.model_validate(body)
    except ValidationError as exc:
        return api_response.error(400, "INVALID_INPUT", _format_validation_error(exc))

    # ----------------------------------------------------------------
    # 3. Read state machine ARN from env
    # ----------------------------------------------------------------
    sm_arn = os.environ.get(STATE_MACHINE_ARN_ENV, "").strip()
    if not sm_arn:
        return api_response.error(
            500,
            "CONFIGURATION_ERROR",
            f"Environment variable {STATE_MACHINE_ARN_ENV} is not set",
        )

    # ----------------------------------------------------------------
    # 4. Generate a unique execution name
    # ----------------------------------------------------------------
    execution_name = f"create-order-{uuid.uuid4()}"

    # ----------------------------------------------------------------
    # 5. Start the state machine
    # ----------------------------------------------------------------
    try:
        _stepfunctions.start_execution(
            stateMachineArn=sm_arn,
            name=execution_name,
            input=json.dumps(body),
        )
    except (BotoCoreError, ClientError) as exc:
        return api_response.error(
            502,
            "ORCHESTRATION_UNAVAILABLE",
            f"Failed to start state machine: {exc}",
        )

    # ----------------------------------------------------------------
    # 6. Return 202 Accepted
    # ----------------------------------------------------------------
    return api_response.ok(
        {
            "executionId": execution_name,
            "executionArn": f"{sm_arn}:execution/{execution_name}",
            "status": "PENDING",
        },
        status_code=202,
    )
