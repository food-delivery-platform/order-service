"""Access to non-secret, per-environment Lambda configuration (FDS-42).

Two storages, two purposes:

* Secrets Manager (``SERVICE_SECRET_ARN`` -> ``order-service/db``) holds
  credentials only — database user and password, PayPal client id and secret,
  webhook id. Those must never be visible in the Lambda configuration.
* Environment variables hold non-secret configuration that the deploy workflow
  wires up — event bus names and state machine ARNs. These are resource names,
  not credentials; access to them is controlled by IAM.

Read credentials with ``src.shared.config.secrets``. Read everything else here.
"""

import os

from src.shared.errors.app_error import AppError


def get_required_env(name: str) -> str:
    """Return *name* from the environment, or raise AppError(500) if missing/empty."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise AppError(
            500,
            "CONFIGURATION_ERROR",
            f"Environment variable {name} is not set",
        )
    return value


def get(name: str, default: str | None = None, required: bool = False) -> str | None:
    value = os.environ.get(name, default)
    if required and not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
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
