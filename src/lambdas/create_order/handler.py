"""Lambda handler - POST /api/v1/orders (create_order).

Thin entry point: validates the request envelope and starts the order
creation state machine. All business logic lives in the state machine.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
import uuid

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from src.shared.http import api_response

STATE_MACHINE_ARN_ENV = "ORDER_CREATION_SM_ARN"

# TODO(FDS-34): take the customer identity from the authorizer claims
# (claims.sub) once the JWT authorizer is attached to the HTTP API.

REQUIRED_FIELDS = ("customer_id", "items")

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


def handler(event, context=None):
    # ----------------------------------------------------------------
    # 1. Decode request body
    # ----------------------------------------------------------------
    body = _decode_body(event)
    if body is None:
        return api_response.error(
            400, "MALFORMED_BODY", "Request body is missing or not valid JSON"
        )

    # ----------------------------------------------------------------
    # 2. Validate required fields
    # ----------------------------------------------------------------
    for field in REQUIRED_FIELDS:
        if not body.get(field):
            return api_response.error(
                400,
                "INVALID_INPUT",
                f"Missing or empty required field: {field}",
            )

    # ----------------------------------------------------------------
    # 3. Read state machine ARN from env
    # ----------------------------------------------------------------
    sm_arn = os.environ.get(STATE_MACHINE_ARN_ENV, "").strip()
    if not sm_arn:
        return api_response.error(
            500,
            "MISSING_CONFIG",
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
            "ORCHESTRATION_FAILED",
            f"Failed to start state machine: {exc}",
        )

    # ----------------------------------------------------------------
    # 6. Return 202 Accepted
    # ----------------------------------------------------------------
    return api_response.ok(
        {
            "executionId": execution_name,
            "status": "accepted",
        },
        status_code=202,
    )
