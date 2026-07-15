"""Payments repository — correlation with PayPal orders (FDS-27).

Stores payment sessions in the ``payments`` table. Relies on the
``UNIQUE(paypal_order_id)`` constraint for idempotency so that
duplicate ``create_payment`` calls are safe.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from src.shared.db import supabase_client
from src.shared.payments.models import PaymentSession, PaymentStatus

logger = logging.getLogger(__name__)

_PAYMENTS_TABLE = "payments"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_payment(
    *,
    order_id: str,
    paypal_order_id: str,
    amount: Decimal,
    currency: str,
    status: PaymentStatus = PaymentStatus.CREATED,
    approval_url: str = "",
) -> PaymentSession:
    """Insert a new payment row, returning the domain model.

    If a row with the same ``paypal_order_id`` already exists the unique
    constraint is violated and the call is treated as a no-op — the
    existing row is fetched and returned instead of raising an error.
    """
    client = supabase_client.get_client()
    now = _utcnow_iso()

    row = {
        "paypal_order_id": paypal_order_id,
        "order_id": order_id,
        "status": status.value,
        "amount": str(amount),
        "currency": currency,
        "approval_url": approval_url,
        "created_at": now,
        "updated_at": now,
    }

    try:
        client.table(_PAYMENTS_TABLE).insert(row).execute()
        return PaymentSession(
            order_id=order_id,
            paypal_order_id=paypal_order_id,
            approval_url=approval_url,
            amount=amount,
            currency=currency,
            status=status,
        )
    except Exception:
        logger.warning(
            "Payment insert failed for paypal_order_id=%s — "
            "checking for idempotent duplicate",
            paypal_order_id,
        )
        existing = get_by_paypal_order_id(paypal_order_id)
        if existing is not None:
            return existing
        raise


def get_by_paypal_order_id(paypal_order_id: str) -> PaymentSession | None:
    """Look up a payment by its PayPal order id.

    Returns ``None`` when no matching row exists.
    """
    client = supabase_client.get_client()
    resp = (
        client.table(_PAYMENTS_TABLE)
        .select("*")
        .eq("paypal_order_id", paypal_order_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return _row_to_payment(rows[0]) if rows else None


def mark_paid(paypal_order_id: str) -> bool:
    """Conditionally mark a payment as PAID.

    Returns
    -------
    bool
        ``True`` if this call flipped the status to ``PAID``.
        ``False`` if the payment was *already* ``PAID`` (duplicate / replay).
    """
    existing = get_by_paypal_order_id(paypal_order_id)
    if existing is None:
        logger.warning(
            "mark_paid: no payment found for paypal_order_id=%s",
            paypal_order_id,
        )
        return False

    if existing.status == PaymentStatus.PAID:
        logger.info(
            "mark_paid: paypal_order_id=%s is already PAID — idempotent no-op",
            paypal_order_id,
        )
        return False

    _update_status(paypal_order_id, PaymentStatus.PAID)
    return True


def mark_failed(paypal_order_id: str, status: PaymentStatus) -> None:
    """Set the payment status to ``FAILED`` or ``CANCELLED``.

    ``status`` must be one of ``PaymentStatus.FAILED`` or
    ``PaymentStatus.CANCELLED``; other values raise ``ValueError``.
    """
    if status not in (PaymentStatus.FAILED, PaymentStatus.CANCELLED):
        raise ValueError(
            f"mark_failed only accepts FAILED or CANCELLED, got {status!r}"
        )
    _update_status(paypal_order_id, status)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _update_status(paypal_order_id: str, status: PaymentStatus) -> None:
    """Write a new ``status`` and ``updated_at`` to the payments table."""
    client = supabase_client.get_client()
    client.table(_PAYMENTS_TABLE).update(
        {"status": status.value, "updated_at": _utcnow_iso()}
    ).eq("paypal_order_id", paypal_order_id).execute()


def _row_to_payment(row: dict) -> PaymentSession:
    return PaymentSession(
        order_id=row["order_id"],
        paypal_order_id=row["paypal_order_id"],
        approval_url=row.get("approval_url", ""),
        amount=Decimal(row["amount"]),
        currency=row["currency"],
        status=PaymentStatus(row["status"]),
    )


def _utcnow_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
