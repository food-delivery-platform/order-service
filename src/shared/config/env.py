"""Centralized access to environment variables (12-factor config).

This module holds non-secret, per-environment configuration.  Credentials
live in ``src/shared/config/secrets.py`` — never in environment variables.
"""

import os

from src.shared.errors.app_error import AppError


def get(name: str, default: str | None = None, required: bool = False) -> str | None:
    value = os.environ.get(name, default)
    if required and not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def get_required_env(name: str) -> str:
    """Return a non-empty environment variable or fail with a 500 AppError.

    ``get(name, required=True)`` raises ``RuntimeError``, which surfaces as an
    unhandled 500 with no error code. Handlers need a typed failure they can
    turn into a proper API response, so configuration defects use AppError with
    code ``CONFIGURATION_ERROR``. The message names the variable, never a value.
    """
    value = os.environ.get(name, "").strip()
    if not value:
        raise AppError(
            500,
            "CONFIGURATION_ERROR",
            f"Environment variable {name} is not set",
        )
    return value


AWS_REGION = get("AWS_REGION", "eu-west-1")

ORDER_STATUS_TABLE_NAME = get("ORDER_STATUS_TABLE_NAME", "order-status-live")

ORDER_EVENTS_TOPIC_ARN = get("ORDER_EVENTS_TOPIC_ARN")
ORDER_INBOUND_QUEUE_URL = get("ORDER_INBOUND_QUEUE_URL")

ORDER_PRE_PAYMENT_STATE_MACHINE_ARN = get("ORDER_PRE_PAYMENT_STATE_MACHINE_ARN")
ORDER_POST_PAYMENT_STATE_MACHINE_ARN = get("ORDER_POST_PAYMENT_STATE_MACHINE_ARN")

MENU_SERVICE_BASE_URL = get("MENU_SERVICE_BASE_URL")
PAYMENT_SERVICE_BASE_URL = get("PAYMENT_SERVICE_BASE_URL")
INTERNAL_SERVICE_JWT = get("INTERNAL_SERVICE_JWT")
