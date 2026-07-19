"""Thin AWS EventBridge wrapper — publishes ``order.*`` domain events (FDS-27 P2-C11).

boto3 is imported lazily and the client is created inside ``EventPublisher.__init__``
so tests can patch the ``get_event_publisher`` factory (or the boto3 client) without
any real AWS calls. Mirrors the PayPal client pattern in
``src/shared/payments/paypal_client.py``.

The EventBridge bus name is read from the service secret first, env var
``EVENT_BUS_NAME`` second, defaulting to ``"default"`` when neither is set.
"""

from __future__ import annotations

import json
import logging
import os

from src.shared.config.secrets import get_service_secret

logger = logging.getLogger(__name__)


class EventPublishError(Exception):
    """Raised when EventBridge ``put_events`` fails or returns a failed entry."""


# ---------------------------------------------------------------------------
# Config helpers (stateless — safe at module level)
# ---------------------------------------------------------------------------


def _get_config(key: str, default: str | None = None) -> str | None:
    """Read config from Secrets Manager first, env var second.

    Mirrors ``_hydrate`` in ``src/shared/config/env.py`` and ``_get_config``
    in ``src/shared/payments/paypal_client.py``.
    """
    secret = get_service_secret()
    if key in secret and secret[key] is not None:
        return secret[key]
    return os.environ.get(key, default)


def get_bus_name() -> str:
    """Return the EventBridge bus name (secret-first, env fallback, default)."""
    return _get_config("EVENT_BUS_NAME", "default") or "default"


# ---------------------------------------------------------------------------
# EventPublisher
# ---------------------------------------------------------------------------


class EventPublisher:
    """Thin wrapper around ``boto3.client("events").put_events``.

    The boto3 client is created lazily inside ``__init__`` so the
    ``get_event_publisher`` factory can be patched in tests without
    importing boto3 at module load time.
    """

    def __init__(self) -> None:
        import boto3  # lazy import — keeps tests hermetic

        aws_region = os.environ.get("AWS_REGION", "eu-west-1")
        self._client = boto3.client("events", region_name=aws_region)

    def put_event(
        self,
        bus: str,
        source: str,
        detail_type: str,
        detail: dict,
    ) -> str:
        """Put a single event onto an EventBridge bus.

        Args:
            bus: ``EventBusName``.
            source: Source string (e.g. ``"order-service"``).
            detail_type: Detail-type (e.g. ``"order.paid"``).
            detail: Detail payload (JSON-serialised before sending).

        Returns:
            The ``EventId`` assigned by EventBridge (may be empty on retry).

        Raises:
            EventPublishError: when ``put_events`` raises, or returns an
                entry with an ``ErrorCode``.
        """
        entry = {
            "EventBusName": bus,
            "Source": source,
            "DetailType": detail_type,
            "Detail": json.dumps(detail),
        }
        try:
            resp = self._client.put_events(Entries=[entry])
        except Exception as exc:
            raise EventPublishError(f"put_events call failed: {exc}") from exc

        entries = resp.get("Entries", [])
        if entries:
            error_code = entries[0].get("ErrorCode")
            if error_code:
                raise EventPublishError(
                    f"put_events returned error: {error_code} "
                    f"{entries[0].get('ErrorMessage', '')}"
                )
            return entries[0].get("EventId", "")
        return ""


# ---------------------------------------------------------------------------
# Module-level convenience factory (test-friendly — patch this in tests)
# ---------------------------------------------------------------------------


def get_event_publisher() -> EventPublisher:
    """Factory used by the handler — patch this in tests."""
    return EventPublisher()
