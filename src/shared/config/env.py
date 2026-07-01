"""Centralized access to environment variables (12-factor config).

Names match the "Required Environment Variables" list in FDS-15.
"""

import os


def get(name: str, default: str | None = None, required: bool = False) -> str | None:
    value = os.environ.get(name, default)
    if required and not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


AWS_REGION = get("AWS_REGION", "eu-west-1")

SUPABASE_URL = get("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = get("SUPABASE_SERVICE_ROLE_KEY")

ORDER_STATUS_TABLE_NAME = get("ORDER_STATUS_TABLE_NAME", "order-status-live")

ORDER_EVENTS_TOPIC_ARN = get("ORDER_EVENTS_TOPIC_ARN")
ORDER_INBOUND_QUEUE_URL = get("ORDER_INBOUND_QUEUE_URL")

ORDER_PRE_PAYMENT_STATE_MACHINE_ARN = get("ORDER_PRE_PAYMENT_STATE_MACHINE_ARN")
ORDER_POST_PAYMENT_STATE_MACHINE_ARN = get("ORDER_POST_PAYMENT_STATE_MACHINE_ARN")

MENU_SERVICE_BASE_URL = get("MENU_SERVICE_BASE_URL")
PAYMENT_SERVICE_BASE_URL = get("PAYMENT_SERVICE_BASE_URL")
INTERNAL_SERVICE_JWT = get("INTERNAL_SERVICE_JWT")
