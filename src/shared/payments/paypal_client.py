"""PayPal REST API client wrapper (FDS-27).

Uses OAuth2 client_credentials grant for authentication.
Config is read from Secrets Manager first (via get_service_secret),
with plain env vars as fallback for local dev.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from decimal import Decimal

import httpx

from src.shared.config.secrets import get_service_secret

logger = logging.getLogger(__name__)


class PayPalError(Exception):
    """Raised when the PayPal API returns a non-2xx response."""

    def __init__(
        self,
        status_code: int,
        message: str,
        response_body: dict | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.response_body = response_body or {}


# ---------------------------------------------------------------------------
# Config helpers (stateless – safe at module level)
# ---------------------------------------------------------------------------


def _get_config(key: str, default: str | None = None) -> str | None:
    """Read config from Secrets Manager first, env var second.

    Mirrors the _hydrate pattern in src/shared/config/env.py.
    """
    secret = get_service_secret()
    if key in secret and secret[key] is not None:
        return secret[key]
    return os.environ.get(key, default)


def _base_url() -> str:
    url = _get_config("PAYPAL_BASE_URL", "https://api-m.sandbox.paypal.com")
    return url.rstrip("/")


def _frontend_base_url() -> str:
    url = _get_config("CUSTOMER_FRONTEND_BASE_URL", "http://localhost:3000")
    return url.rstrip("/")


# ---------------------------------------------------------------------------
# PayPalClient
# ---------------------------------------------------------------------------


class PayPalClient:
    """Thin PayPal REST API client with instance-scoped OAuth token caching.

    Token is lazily fetched on first API call and reused until it nears
    expiry (60-second buffer).  Token fetch is guarded by a ``threading.Lock``
    so concurrent callers on the same instance will not double-fetch.
    """

    def __init__(self) -> None:
        self._token: str | None = None
        self._token_expiry: float = 0.0
        self._lock: threading.Lock = threading.Lock()

    # -- auth ----------------------------------------------------------------

    def _get_access_token(self) -> str:
        """Obtain an OAuth2 access token using client_credentials grant.

        The token is cached on the instance and reused across calls until
        it approaches expiry (60-second buffer).
        """
        # Fast-path: return cached token without acquiring the lock.
        now = time.time()
        if self._token and now < self._token_expiry - 60:
            return self._token

        with self._lock:
            # Double-check after acquiring the lock – another thread may have
            # fetched the token while we were waiting.
            now = time.time()
            if self._token and now < self._token_expiry - 60:
                return self._token

            client_id = _get_config("PAYPAL_CLIENT_ID")
            client_secret = _get_config("PAYPAL_CLIENT_SECRET")
            if not client_id or not client_secret:
                raise PayPalError(
                    0,
                    "PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET must be configured",
                )

            url = f"{_base_url()}/v1/oauth2/token"
            with httpx.Client() as client:
                resp = client.post(
                    url,
                    data={"grant_type": "client_credentials"},
                    auth=(client_id, client_secret),
                    headers={"Accept": "application/json"},
                )

            if resp.status_code != 200:
                logger.error(
                    "PayPal token request failed: HTTP %s %s",
                    resp.status_code,
                    resp.text,
                )
                raise PayPalError(
                    resp.status_code,
                    "Failed to obtain PayPal access token",
                )

            data = resp.json()
            self._token = data["access_token"]
            expires_in = data.get("expires_in", 3600)
            self._token_expiry = now + expires_in
            return self._token

    # -- public methods ------------------------------------------------------

    def create_order(self, order_id: str, amount: Decimal, currency: str) -> dict:
        """Create a PayPal checkout order with intent=CAPTURE.

        Args:
            order_id: Customer order reference id (sent as
                      purchase_units reference_id).
            amount: Total order amount.
            currency: ISO 4217 currency code (e.g. ``"ILS"``).

        Returns:
            dict with keys ``paypal_order_id`` and ``approval_url``.

        Raises:
            PayPalError: on any non-2xx response.
        """
        token = self._get_access_token()
        url = f"{_base_url()}/v2/checkout/orders"

        frontend_base = _frontend_base_url()
        payload = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "reference_id": order_id,
                    "amount": {
                        "currency_code": currency,
                        "value": str(amount),
                    },
                }
            ],
            "application_context": {
                "return_url": f"{frontend_base}/orders/{order_id}?payment=success",
                "cancel_url": f"{frontend_base}/orders/{order_id}?payment=cancelled",
            },
        }

        with httpx.Client() as client:
            resp = client.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )

        if resp.status_code not in (200, 201):
            logger.error(
                "PayPal create_order failed: HTTP %s %s",
                resp.status_code,
                resp.text,
            )
            raise PayPalError(
                resp.status_code,
                "Failed to create PayPal order",
                resp.json() if resp.text else None,
            )

        data = resp.json()
        approval_url = ""
        for link in data.get("links", []):
            if link.get("rel") == "approve":
                approval_url = link.get("href", "")
                break

        return {
            "paypal_order_id": data["id"],
            "approval_url": approval_url,
        }

    def get_order(self, paypal_order_id: str) -> dict:
        """Fetch a PayPal order by its PayPal-side id.

        Args:
            paypal_order_id: PayPal order id (returned by ``create_order``).

        Returns:
            dict with keys ``status``, ``amount``, ``currency``.

        Raises:
            PayPalError: on any non-2xx response.
        """
        token = self._get_access_token()
        url = f"{_base_url()}/v2/checkout/orders/{paypal_order_id}"

        with httpx.Client() as client:
            resp = client.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
            )

        if resp.status_code != 200:
            logger.error(
                "PayPal get_order failed: HTTP %s %s",
                resp.status_code,
                resp.text,
            )
            raise PayPalError(
                resp.status_code,
                f"Failed to get PayPal order {paypal_order_id}",
                resp.json() if resp.text else None,
            )

        data = resp.json()
        purchase_units = data.get("purchase_units", [])
        amount = ""
        currency = ""
        if purchase_units:
            amt = purchase_units[0].get("amount", {})
            amount = amt.get("value", "")
            currency = amt.get("currency_code", "")

        return {
            "status": data.get("status", ""),
            "amount": amount,
            "currency": currency,
        }

    def capture_order(self, paypal_order_id: str) -> dict:
        """Capture an approved PayPal order (APPROVED -> COMPLETED).

        Idempotent: an already-captured order returns HTTP 422 with issue
        ``ORDER_ALREADY_CAPTURED``; that is treated as success.

        Returns:
            dict with key ``status`` (the order status, e.g. ``"COMPLETED"``).

        Raises:
            PayPalError: on any other non-2xx response.
        """
        token = self._get_access_token()
        url = f"{_base_url()}/v2/checkout/orders/{paypal_order_id}/capture"

        with httpx.Client() as client:
            resp = client.post(
                url,
                json={},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )

        if resp.status_code in (200, 201):
            data = resp.json()
            return {"status": data.get("status", "")}

        # Idempotency: an already-captured order returns 422 ORDER_ALREADY_CAPTURED.
        if resp.status_code == 422:
            body = resp.json() if resp.text else {}
            issues = {d.get("issue") for d in body.get("details", [])}
            if "ORDER_ALREADY_CAPTURED" in issues:
                logger.info(
                    "PayPal order %s already captured — treating as success",
                    paypal_order_id,
                )
                return {"status": "COMPLETED"}

        logger.error(
            "PayPal capture_order failed: HTTP %s %s",
            resp.status_code,
            resp.text,
        )
        raise PayPalError(
            resp.status_code,
            f"Failed to capture PayPal order {paypal_order_id}",
            resp.json() if resp.text else None,
        )

    def verify_webhook_signature(self, headers: dict, body: str) -> bool:
        """Verify a PayPal webhook notification signature.

        Sends the headers and body to PayPal's verification endpoint.

        Args:
            headers: Dict of HTTP headers from the incoming webhook POST
                     (keys are lowercased, e.g.
                     ``paypal-transmission-id``).
            body: Raw JSON body string of the webhook event.

        Returns:
            ``True`` when PayPal confirms
            ``verification_status == "SUCCESS"``, ``False`` otherwise.

        Raises:
            PayPalError: when the verification request itself fails
                         (non-2xx).
        """
        webhook_id = _get_config("PAYPAL_WEBHOOK_ID")
        if not webhook_id:
            logger.warning("PAYPAL_WEBHOOK_ID not configured – skipping verification")
            return False

        token = self._get_access_token()
        url = f"{_base_url()}/v1/notifications/verify-webhook-signature"

        payload = {
            "webhook_id": webhook_id,
            "webhook_event": json.loads(body),
            "cert_url": headers.get("paypal-cert-url", ""),
            "transmission_id": headers.get("paypal-transmission-id", ""),
            "transmission_time": headers.get("paypal-transmission-time", ""),
            "transmission_sig": headers.get("paypal-transmission-sig", ""),
            "auth_algo": headers.get("paypal-auth-algo", ""),
        }

        with httpx.Client() as client:
            resp = client.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )

        if resp.status_code != 200:
            logger.error(
                "PayPal webhook verify failed: HTTP %s %s",
                resp.status_code,
                resp.text,
            )
            raise PayPalError(
                resp.status_code,
                "Webhook signature verification request failed",
                resp.json() if resp.text else None,
            )

        data = resp.json()
        return data.get("verification_status") == "SUCCESS"


# ---------------------------------------------------------------------------
# Module-level convenience functions (backward-compatible shims)
# ---------------------------------------------------------------------------


def create_order(order_id: str, amount: Decimal, currency: str) -> dict:
    """Create a PayPal checkout order (module-level convenience wrapper).

    Creates a throw-away ``PayPalClient`` instance per call.
    For reuse across calls hold a ``PayPalClient`` instance directly.
    """
    return PayPalClient().create_order(order_id, amount, currency)


def get_order(paypal_order_id: str) -> dict:
    """Fetch a PayPal order (module-level convenience wrapper).

    Creates a throw-away ``PayPalClient`` instance per call.
    For reuse across calls hold a ``PayPalClient`` instance directly.
    """
    return PayPalClient().get_order(paypal_order_id)


def capture_order(paypal_order_id: str) -> dict:
    """Capture a PayPal order (module-level convenience wrapper)."""
    return PayPalClient().capture_order(paypal_order_id)


def verify_webhook_signature(headers: dict, body: str) -> bool:
    """Verify a PayPal webhook signature (module-level convenience wrapper).

    Creates a throw-away ``PayPalClient`` instance per call.
    For reuse across calls hold a ``PayPalClient`` instance directly.
    """
    return PayPalClient().verify_webhook_signature(headers, body)
