"""Hermetic unit tests for payment domain models (FDS-27 R2)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.modules.orders.model.order_status import OrderStatus
from src.shared.payments.models import (
    PaymentSession,
    PaymentStatus,
    PaymentVerification,
)

# ---------------------------------------------------------------------------
# OrderStatus enum — new values
# ---------------------------------------------------------------------------


def test_order_status_has_new_payment_values():
    """PAYMENT_FAILED is available alongside the existing FAILED."""
    assert OrderStatus.PAYMENT_FAILED.value == "PAYMENT_FAILED"
    assert OrderStatus.PENDING_PAYMENT.value == "PENDING_PAYMENT"
    assert OrderStatus.PAID.value == "PAID"
    assert OrderStatus.CANCELLED.value == "CANCELLED"


def test_existing_order_statuses_are_untouched():
    """Values that existed before FDS-27 must still be present."""
    existing = {
        OrderStatus.CREATED,
        OrderStatus.READY,
        OrderStatus.PICKED_UP,
        OrderStatus.DELIVERED,
        OrderStatus.FAILED,
    }
    assert existing  # read by the runtime; ensure they exist


# ---------------------------------------------------------------------------
# PaymentStatus enum — new StrEnum members (DB schema match)
# ---------------------------------------------------------------------------


def test_payment_status_values():
    assert PaymentStatus.PENDING.value == "PENDING"
    assert PaymentStatus.CUSTOMER_ACTION_REQUIRED.value == "CUSTOMER_ACTION_REQUIRED"
    assert PaymentStatus.SUCCEEDED.value == "SUCCEEDED"
    assert PaymentStatus.FAILED.value == "FAILED"
    assert PaymentStatus.REFUNDED.value == "REFUNDED"


def test_payment_status_is_str_enum():
    """PaymentStatus is an StrEnum (Python 3.11+) — members ARE strings."""
    assert isinstance(PaymentStatus.PENDING, str)
    assert PaymentStatus.PENDING == "PENDING"


def test_payment_status_only_has_five_members():
    """No legacy CREATED/PAID/CANCELLED values remain."""
    assert not hasattr(PaymentStatus, "CREATED")
    assert not hasattr(PaymentStatus, "PAID")
    assert not hasattr(PaymentStatus, "CANCELLED")


# ---------------------------------------------------------------------------
# PaymentSession — valid payloads
# ---------------------------------------------------------------------------


_VALID_SESSION = {
    "order_id": "ord-abc123",
    "provider": "paypal",
    "provider_ref": "PAYPAL-TEST-001",
    "approval_url": "https://www.sandbox.paypal.com/checkout/approve",
    "amount": Decimal("78.50"),
    "currency": "ILS",
    "status": "PENDING",
}


def test_session_valid_payload():
    s = PaymentSession(**_VALID_SESSION)
    assert s.order_id == "ord-abc123"
    assert s.provider == "paypal"
    assert s.provider_ref == "PAYPAL-TEST-001"
    assert s.amount == Decimal("78.50")
    assert s.currency == "ILS"
    assert s.status == PaymentStatus.PENDING


def test_session_default_status_is_pending():
    payload = {k: v for k, v in _VALID_SESSION.items() if k != "status"}
    s = PaymentSession(**payload)
    assert s.status == PaymentStatus.PENDING


def test_session_default_provider_is_paypal():
    payload = {k: v for k, v in _VALID_SESSION.items() if k != "provider"}
    s = PaymentSession(**payload)
    assert s.provider == "paypal"


def test_session_accepts_other_statuses():
    for st in ("CUSTOMER_ACTION_REQUIRED", "SUCCEEDED", "FAILED", "REFUNDED"):
        payload = {**_VALID_SESSION, "status": st}
        s = PaymentSession(**payload)
        assert s.status.value == st


# ---------------------------------------------------------------------------
# PaymentSession — invalid payloads
# ---------------------------------------------------------------------------


def test_session_missing_order_id_rejected():
    bad = {k: v for k, v in _VALID_SESSION.items() if k != "order_id"}
    with pytest.raises(ValidationError):
        PaymentSession(**bad)


def test_session_missing_provider_ref_rejected():
    bad = {k: v for k, v in _VALID_SESSION.items() if k != "provider_ref"}
    with pytest.raises(ValidationError):
        PaymentSession(**bad)


def test_session_empty_order_id_rejected():
    bad = {**_VALID_SESSION, "order_id": ""}
    with pytest.raises(ValidationError):
        PaymentSession(**bad)


def test_session_amount_zero_rejected():
    bad = {**_VALID_SESSION, "amount": Decimal("0")}
    with pytest.raises(ValidationError):
        PaymentSession(**bad)


def test_session_amount_wrong_type_rejected():
    bad = {**_VALID_SESSION, "amount": "not-a-decimal"}
    with pytest.raises(ValidationError):
        PaymentSession(**bad)


def test_session_currency_too_short_rejected():
    bad = {**_VALID_SESSION, "currency": "IL"}
    with pytest.raises(ValidationError):
        PaymentSession(**bad)


def test_session_currency_too_long_rejected():
    bad = {**_VALID_SESSION, "currency": "ILSS"}
    with pytest.raises(ValidationError):
        PaymentSession(**bad)


def test_session_invalid_status_rejected():
    bad = {**_VALID_SESSION, "status": "UNKNOWN_STATUS"}
    with pytest.raises(ValidationError):
        PaymentSession(**bad)


# ---------------------------------------------------------------------------
# PaymentVerification — valid payloads
# ---------------------------------------------------------------------------


_VALID_VERIFICATION = {
    "provider": "paypal",
    "provider_ref": "PAYPAL-TEST-002",
    "status": "COMPLETED",
    "amount": Decimal("25.00"),
    "currency": "USD",
}


def test_verification_valid_payload():
    v = PaymentVerification(**_VALID_VERIFICATION)
    assert v.provider == "paypal"
    assert v.provider_ref == "PAYPAL-TEST-002"
    assert v.status == "COMPLETED"
    assert v.amount == Decimal("25.00")
    assert v.currency == "USD"


def test_verification_default_provider_is_paypal():
    payload = {k: v for k, v in _VALID_VERIFICATION.items() if k != "provider"}
    v = PaymentVerification(**payload)
    assert v.provider == "paypal"


def test_verification_status_is_freeform_string():
    """status is a provider-side value (e.g. APPROVED, COMPLETED) — not an enum."""
    v = PaymentVerification(**_VALID_VERIFICATION)
    assert isinstance(v.status, str)


# ---------------------------------------------------------------------------
# PaymentVerification — invalid payloads
# ---------------------------------------------------------------------------


def test_verification_missing_provider_ref_rejected():
    bad = {k: v for k, v in _VALID_VERIFICATION.items() if k != "provider_ref"}
    with pytest.raises(ValidationError):
        PaymentVerification(**bad)


def test_verification_empty_status_rejected():
    bad = {**_VALID_VERIFICATION, "status": ""}
    with pytest.raises(ValidationError):
        PaymentVerification(**bad)


def test_verification_amount_negative_rejected():
    bad = {**_VALID_VERIFICATION, "amount": Decimal("-5")}
    with pytest.raises(ValidationError):
        PaymentVerification(**bad)
