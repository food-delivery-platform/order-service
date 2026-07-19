"""Unit tests for PayPal REST client wrapper (FDS-27).

All HTTP calls are mocked — no network access.
"""

from __future__ import annotations

import json
import threading
import time
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from src.shared.payments.paypal_client import PayPalClient, PayPalError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_secret_cache():
    """Ensure the secret cache is empty so env vars are used."""
    import src.shared.config.secrets as secrets

    secrets._secret_cache = None


@pytest.fixture(autouse=True)
def _clear_service_secret_arn(monkeypatch):
    """Unset SERVICE_SECRET_ARN so we use env vars, not Secrets Manager."""
    monkeypatch.delenv("SERVICE_SECRET_ARN", raising=False)


@pytest.fixture
def paypal_env(monkeypatch):
    """Set all required PayPal config env vars."""
    monkeypatch.setenv("PAYPAL_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("PAYPAL_WEBHOOK_ID", "wh_123")
    monkeypatch.setenv("PAYPAL_BASE_URL", "https://api-m.sandbox.paypal.com")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_response(status_code: int, json_data: dict) -> MagicMock:
    """Create a mock httpx.Response with the given status and JSON body."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.text = json.dumps(json_data)
    return resp


def _setup_http_mock(*response_pairs):
    """Patch ``httpx.Client`` so that successive POST/GET calls return the
    given responses in order.

    Each *response_pairs* element is ``(method, url_substring, mock_response)``,
    used as a lookup table keyed by (method, url_substring).

    Returns the ``mock_client_instance`` (the object returned by
    ``httpx.Client().__enter__()``) so callers can assert on call counts etc.
    """
    lookup = {(m, sub): resp for m, sub, resp in response_pairs}

    def _do(method, url, **__):
        for (m, sub), resp in lookup.items():
            if m == method and sub in url:
                return resp
        raise AssertionError(
            f"No mock registered for {method} {url}. Registered: {list(lookup.keys())}"
        )

    mock_instance = MagicMock()
    mock_instance.post.side_effect = lambda url, **kw: _do("POST", url)
    mock_instance.get.side_effect = lambda url, **kw: _do("GET", url)

    return mock_instance


# ---------------------------------------------------------------------------
# Token caching (per-instance)
# ---------------------------------------------------------------------------


class TestAccessTokenCaching:
    def test_token_fetched_once_and_reused(self, paypal_env):
        """First call fetches a token; second call reuses the cached token."""
        token_resp = _mock_response(
            200,
            {
                "access_token": "tok-abc",
                "expires_in": 3600,
            },
        )
        order_resp = _mock_response(
            201,
            {
                "id": "PP-O-1",
                "status": "CREATED",
                "links": [
                    {
                        "rel": "approve",
                        "href": "https://www.paypal.com/checkoutnow?token=PP-O-1",
                    }
                ],
            },
        )

        mock_http = _setup_http_mock(
            ("POST", "/v1/oauth2/token", token_resp),
            ("POST", "/v2/checkout/orders", order_resp),
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_http
            client = PayPalClient()

            r1 = client.create_order("ord-1", Decimal("49.90"), "ILS")
            r2 = client.create_order("ord-2", Decimal("29.90"), "ILS")

        assert r1["paypal_order_id"] == "PP-O-1"
        assert r1["approval_url"] == ("https://www.paypal.com/checkoutnow?token=PP-O-1")
        assert r2["paypal_order_id"] == "PP-O-1"

        # Token endpoint called only once across both create_order calls
        assert mock_http.post.call_count == 3  # 1 token + 2 orders
        token_calls = [
            c for c in mock_http.post.call_args_list if "/v1/oauth2/token" in c[0][0]
        ]
        assert len(token_calls) == 1

    def test_token_not_refetched_when_not_expired(self, paypal_env):
        """Second call to _get_access_token returns the cached token."""
        token_resp = _mock_response(
            200,
            {
                "access_token": "tok-xyz",
                "expires_in": 3600,
            },
        )

        mock_http = _setup_http_mock(
            ("POST", "/v1/oauth2/token", token_resp),
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_http
            client = PayPalClient()
            t1 = client._get_access_token()
            t2 = client._get_access_token()

        assert t1 == "tok-xyz"
        assert t2 == "tok-xyz"
        # httpx.Client called only once (for the token fetch)
        assert mock_client_cls.call_count == 1

    def test_token_refetched_after_expiry(self, monkeypatch, paypal_env):
        """When the token is expired, a new one is fetched."""
        token_resp = _mock_response(
            200,
            {
                "access_token": "fresh-tok",
                "expires_in": 3600,
            },
        )

        mock_http = _setup_http_mock(
            ("POST", "/v1/oauth2/token", token_resp),
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_http
            client = PayPalClient()
            # Inject an expired token directly
            client._token = "old-tok"
            client._token_expiry = 1.0  # way in the past

            result = client._get_access_token()

        assert result == "fresh-tok"
        # Client was created to fetch a new token
        assert mock_client_cls.call_count == 1

    def test_concurrent_callers_dont_double_fetch(self, paypal_env):
        """Lock prevents two concurrent _get_access_token calls from both
        hitting the token endpoint."""
        http_started = threading.Event()
        release_http = threading.Event()

        # Track how many times the token endpoint is POSTed
        token_call_count = 0

        def _slow_token_post(**__):
            nonlocal token_call_count
            token_call_count += 1
            http_started.set()  # Signal: Thread A has the lock and is fetching
            release_http.wait(timeout=2)  # Block until released
            return _mock_response(
                200,
                {
                    "access_token": "tok-concurrent",
                    "expires_in": 3600,
                },
            )

        mock_client = MagicMock()
        mock_client.post.side_effect = lambda url, **kw: (
            _slow_token_post() if "/v1/oauth2/token" in url else MagicMock()
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_client

            client = PayPalClient()
            results = []

            def _fetch():
                results.append(client._get_access_token())

            # Start Thread A — it acquires the lock and blocks on release_http
            thread_a = threading.Thread(target=_fetch)
            thread_a.start()

            # Wait until Thread A is inside the token fetch
            assert http_started.wait(timeout=2)

            # Start Thread B — it will block on the lock
            thread_b = threading.Thread(target=_fetch)
            thread_b.start()

            # Give Thread B a moment to reach the lock
            time.sleep(0.1)

            # Release Thread A so it completes and releases the lock
            release_http.set()

            thread_a.join(timeout=2)
            thread_b.join(timeout=2)

        assert len(results) == 2
        assert results[0] == "tok-concurrent"
        assert results[1] == "tok-concurrent"
        # Exactly ONE HTTP call to the token endpoint
        assert token_call_count == 1


# ---------------------------------------------------------------------------
# create_order
# ---------------------------------------------------------------------------


class TestCreateOrder:
    def test_happy_path(self, paypal_env):
        token_resp = _mock_response(
            200,
            {
                "access_token": "tok-1",
                "expires_in": 3600,
            },
        )
        order_resp = _mock_response(
            201,
            {
                "id": "PAYPAL-ORDER-42",
                "status": "CREATED",
                "intent": "CAPTURE",
                "links": [
                    {
                        "href": "https://api.paypal.com/v2/checkout/orders/PAYPAL-ORDER-42",
                        "rel": "self",
                        "method": "GET",
                    },
                    {
                        "href": "https://www.paypal.com/checkoutnow?token=PAYPAL-ORDER-42",
                        "rel": "approve",
                        "method": "GET",
                    },
                    {
                        "href": "https://api.paypal.com/v2/checkout/orders/PAYPAL-ORDER-42/capture",
                        "rel": "capture",
                        "method": "POST",
                    },
                ],
            },
        )

        mock_http = _setup_http_mock(
            ("POST", "/v1/oauth2/token", token_resp),
            ("POST", "/v2/checkout/orders", order_resp),
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_http
            client = PayPalClient()
            result = client.create_order("my-order", Decimal("99.99"), "ILS")

        assert result == {
            "paypal_order_id": "PAYPAL-ORDER-42",
            "approval_url": (
                "https://www.paypal.com/checkoutnow?token=PAYPAL-ORDER-42"
            ),
        }

    def test_no_approval_link_returns_empty_approval_url(self, paypal_env):
        """If no link with rel=approve, approval_url is empty string."""
        token_resp = _mock_response(
            200,
            {
                "access_token": "tok-1",
                "expires_in": 3600,
            },
        )
        order_resp = _mock_response(
            201,
            {
                "id": "PP-NO-APPROVE",
                "status": "CREATED",
                "links": [
                    {
                        "href": "https://api.paypal.com/...",
                        "rel": "self",
                        "method": "GET",
                    },
                ],
            },
        )

        mock_http = _setup_http_mock(
            ("POST", "/v1/oauth2/token", token_resp),
            ("POST", "/v2/checkout/orders", order_resp),
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_http
            client = PayPalClient()
            result = client.create_order("ord", Decimal("10.00"), "USD")

        assert result["paypal_order_id"] == "PP-NO-APPROVE"
        assert result["approval_url"] == ""

    def test_decimal_amount_formatted_as_string(self, paypal_env):
        """Decimal values are serialized as strings in the payload."""
        token_resp = _mock_response(
            200,
            {
                "access_token": "tok-1",
                "expires_in": 3600,
            },
        )
        order_resp = _mock_response(
            201,
            {
                "id": "PP-1",
                "status": "CREATED",
                "links": [],
            },
        )

        mock_http = _setup_http_mock(
            ("POST", "/v1/oauth2/token", token_resp),
            ("POST", "/v2/checkout/orders", order_resp),
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_http
            client = PayPalClient()
            client.create_order("ord", Decimal("123.45"), "EUR")

        # Check that the order creation POST body had the correct amount format
        order_call = [
            c for c in mock_http.post.call_args_list if "/v2/checkout/orders" in c[0][0]
        ][0]
        payload = order_call[1]["json"]
        assert payload["purchase_units"][0]["amount"]["value"] == "123.45"
        assert payload["purchase_units"][0]["amount"]["currency_code"] == "EUR"
        assert payload["intent"] == "CAPTURE"


# ---------------------------------------------------------------------------
# get_order
# ---------------------------------------------------------------------------


class TestGetOrder:
    def test_normalizes_response(self, paypal_env):
        token_resp = _mock_response(
            200,
            {
                "access_token": "tok-2",
                "expires_in": 3600,
            },
        )
        order_resp = _mock_response(
            200,
            {
                "id": "PP-ORDER-99",
                "status": "APPROVED",
                "intent": "CAPTURE",
                "purchase_units": [
                    {
                        "reference_id": "my-order",
                        "amount": {
                            "currency_code": "ILS",
                            "value": "150.00",
                        },
                    }
                ],
                "payer": {"email_address": "buyer@example.com"},
                "create_time": "2026-07-15T10:00:00Z",
            },
        )

        mock_http = _setup_http_mock(
            ("POST", "/v1/oauth2/token", token_resp),
            ("GET", "/v2/checkout/orders/PP-ORDER-99", order_resp),
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_http
            client = PayPalClient()
            result = client.get_order("PP-ORDER-99")

        assert result == {
            "status": "APPROVED",
            "amount": "150.00",
            "currency": "ILS",
        }

    def test_missing_purchase_units(self, paypal_env):
        """Empty purchase_units → empty amount/currency strings."""
        token_resp = _mock_response(
            200,
            {
                "access_token": "tok-3",
                "expires_in": 3600,
            },
        )
        order_resp = _mock_response(
            200,
            {
                "id": "PP-EMPTY",
                "status": "CREATED",
                "purchase_units": [],
            },
        )

        mock_http = _setup_http_mock(
            ("POST", "/v1/oauth2/token", token_resp),
            ("GET", "/v2/checkout/orders/PP-EMPTY", order_resp),
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_http
            client = PayPalClient()
            result = client.get_order("PP-EMPTY")

        assert result == {
            "status": "CREATED",
            "amount": "",
            "currency": "",
        }


# ---------------------------------------------------------------------------
# verify_webhook_signature
# ---------------------------------------------------------------------------


class TestVerifyWebhookSignature:
    _HEADERS = {
        "paypal-cert-url": ("https://api.paypal.com/v1/notifications/certs/CERT-360"),
        "paypal-transmission-id": "txn-123",
        "paypal-transmission-time": "2026-07-15T10:00:00Z",
        "paypal-transmission-sig": "sig-value",
        "paypal-auth-algo": "SHA256withRSA",
    }
    _BODY = json.dumps(
        {
            "event_type": "CHECKOUT.ORDER.APPROVED",
            "resource": {"id": "PP-1"},
        }
    )

    def test_success_returns_true(self, paypal_env):
        token_resp = _mock_response(
            200,
            {
                "access_token": "tok-4",
                "expires_in": 3600,
            },
        )
        verify_resp = _mock_response(200, {"verification_status": "SUCCESS"})

        mock_http = _setup_http_mock(
            ("POST", "/v1/oauth2/token", token_resp),
            (
                "POST",
                "/v1/notifications/verify-webhook-signature",
                verify_resp,
            ),
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_http
            client = PayPalClient()
            result = client.verify_webhook_signature(self._HEADERS, self._BODY)

        assert result is True

    def test_failure_returns_false(self, paypal_env):
        token_resp = _mock_response(
            200,
            {
                "access_token": "tok-5",
                "expires_in": 3600,
            },
        )
        verify_resp = _mock_response(200, {"verification_status": "FAILURE"})

        mock_http = _setup_http_mock(
            ("POST", "/v1/oauth2/token", token_resp),
            (
                "POST",
                "/v1/notifications/verify-webhook-signature",
                verify_resp,
            ),
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_http
            client = PayPalClient()
            result = client.verify_webhook_signature(self._HEADERS, self._BODY)

        assert result is False

    def test_verification_request_non_200_raises_paypal_error(self, paypal_env):
        token_resp = _mock_response(
            200,
            {
                "access_token": "tok-6",
                "expires_in": 3600,
            },
        )
        verify_resp = _mock_response(500, {"error": "internal_error"})

        mock_http = _setup_http_mock(
            ("POST", "/v1/oauth2/token", token_resp),
            (
                "POST",
                "/v1/notifications/verify-webhook-signature",
                verify_resp,
            ),
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_http
            client = PayPalClient()
            with pytest.raises(PayPalError) as exc_info:
                client.verify_webhook_signature(self._HEADERS, self._BODY)

        assert exc_info.value.status_code == 500

    def test_missing_webhook_id_returns_false(self, paypal_env, monkeypatch):
        monkeypatch.delenv("PAYPAL_WEBHOOK_ID", raising=False)
        client = PayPalClient()
        result = client.verify_webhook_signature(self._HEADERS, self._BODY)
        assert result is False


# ---------------------------------------------------------------------------
# PayPalError
# ---------------------------------------------------------------------------


class TestPayPalError:
    def test_error_stores_fields(self):
        err = PayPalError(
            400,
            "Bad request",
            {"name": "INVALID_REQUEST", "message": "Missing field"},
        )
        assert err.status_code == 400
        assert err.message == "Bad request"
        assert err.response_body == {
            "name": "INVALID_REQUEST",
            "message": "Missing field",
        }

    def test_error_defaults_response_body_to_empty_dict(self):
        err = PayPalError(401, "Unauthorized")
        assert err.response_body == {}


# ---------------------------------------------------------------------------
# Non-2xx → PayPalError
# ---------------------------------------------------------------------------


class TestNon2xxRaisesPayPalError:
    def test_create_order_400_raises(self, paypal_env):
        token_resp = _mock_response(
            200,
            {
                "access_token": "tok-err",
                "expires_in": 3600,
            },
        )
        error_resp = _mock_response(
            400,
            {
                "name": "INVALID_REQUEST",
                "message": "Currency not supported",
            },
        )

        mock_http = _setup_http_mock(
            ("POST", "/v1/oauth2/token", token_resp),
            ("POST", "/v2/checkout/orders", error_resp),
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_http
            client = PayPalClient()
            with pytest.raises(PayPalError) as exc_info:
                client.create_order("ord", Decimal("10"), "XXX")

        assert exc_info.value.status_code == 400
        assert "Failed to create PayPal order" in exc_info.value.message

    def test_get_order_404_raises(self, paypal_env):
        token_resp = _mock_response(
            200,
            {
                "access_token": "tok-err",
                "expires_in": 3600,
            },
        )
        error_resp = _mock_response(
            404,
            {
                "name": "RESOURCE_NOT_FOUND",
                "message": "Order not found",
            },
        )

        mock_http = _setup_http_mock(
            ("POST", "/v1/oauth2/token", token_resp),
            ("GET", "/v2/checkout/orders/PP-NOPE", error_resp),
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_http
            client = PayPalClient()
            with pytest.raises(PayPalError) as exc_info:
                client.get_order("PP-NOPE")

        assert exc_info.value.status_code == 404

    def test_token_endpoint_401_raises(self, paypal_env):
        error_resp = _mock_response(401, {"error": "invalid_client"})

        mock_http = _setup_http_mock(
            ("POST", "/v1/oauth2/token", error_resp),
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_http
            client = PayPalClient()
            with pytest.raises(PayPalError) as exc_info:
                client._get_access_token()

        assert exc_info.value.status_code == 401

    def test_missing_client_id_raises(self, monkeypatch):
        """Without PAYPAL_CLIENT_ID set, _get_access_token raises PayPalError."""
        monkeypatch.delenv("PAYPAL_CLIENT_ID", raising=False)
        monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "secret")
        client = PayPalClient()
        with pytest.raises(PayPalError, match="CLIENT_ID"):
            client._get_access_token()

    def test_missing_client_secret_raises(self, monkeypatch):
        monkeypatch.setenv("PAYPAL_CLIENT_ID", "id")
        monkeypatch.delenv("PAYPAL_CLIENT_SECRET", raising=False)
        client = PayPalClient()
        with pytest.raises(PayPalError, match="CLIENT_SECRET"):
            client._get_access_token()
