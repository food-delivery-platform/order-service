"""Payments repository — SQLAlchemy Core (FDS-27 R2).

Writes payment sessions into the ``payments`` table.  Relies on DB-level
unique constraints (``idempotency_key``, ``UNIQUE(provider, provider_ref)``)
for idempotency — no application-side locking.

Writes use ``get_engine().begin()`` (transactional); reads use
``get_engine().connect()``.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from src.shared.db.engine import get_engine, payments_table
from src.shared.payments.models import PaymentSession, PaymentStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_payment(
    *,
    order_id: str,
    provider: str = "paypal",
    provider_ref: str,
    amount: Decimal,
    currency: str,
    approval_url: str = "",
    status: PaymentStatus = PaymentStatus.PENDING,
) -> PaymentSession:
    """Insert a new payment row, returning the domain model.

    Idempotency: ``idempotency_key = f"{provider}:{provider_ref}:{order_id}"``.
    On ``IntegrityError`` (duplicate idempotency_key or provider/provider_ref)
    the existing row is returned via ``get_by_provider_ref``.
    """
    idempotency_key = f"{provider}:{provider_ref}:{order_id}"

    with get_engine().begin() as conn:
        stmt = payments_table.insert().values(
            order_id=order_id,
            provider=provider,
            provider_ref=provider_ref,
            idempotency_key=idempotency_key,
            status=status.value,
            amount=amount,
            currency=currency,
            approval_url=approval_url,
        )
        try:
            conn.execute(stmt)
        except IntegrityError:
            logger.warning(
                "Payment insert duplicate for provider=%s provider_ref=%s",
                provider,
                provider_ref,
            )
            # Rollback the failed insert, then fetch the existing row.
            # get_engine().begin() auto-rolls back on exception.
            # We must fetch *after* the connection is released.
            pass
        else:
            return PaymentSession(
                order_id=order_id,
                provider=provider,
                provider_ref=provider_ref,
                approval_url=approval_url,
                amount=amount,
                currency=currency,
                status=status,
            )

    # IntegrityError path — fetch the existing record
    existing = get_by_provider_ref(provider, provider_ref)
    if existing is not None:
        return existing
    raise RuntimeError(
        f"Duplicate payment for provider={provider} provider_ref={provider_ref} "
        "but get_by_provider_ref returned None"
    )


def get_by_provider_ref(provider: str, provider_ref: str) -> PaymentSession | None:
    """Look up a payment by provider + provider_ref.

    Returns ``None`` when no matching row exists.
    """
    with get_engine().connect() as conn:
        stmt = (
            select(payments_table)
            .where(
                payments_table.c.provider == provider,
                payments_table.c.provider_ref == provider_ref,
            )
            .limit(1)
        )
        row = conn.execute(stmt).fetchone()
        if row is None:
            return None
        return _row_to_payment(row)


def mark_paid(provider: str, provider_ref: str) -> bool:
    """Conditionally mark a payment as SUCCEEDED (atomic, race-safe).

    Only transitions from ``PENDING`` → ``SUCCEEDED``.  ``paid_at`` and
    ``updated_at`` are set to ``now()``.

    Returns:
        ``True`` if exactly one row was updated, ``False`` otherwise
        (already terminal, or row does not exist).
    """
    with get_engine().begin() as conn:
        stmt = (
            update(payments_table)
            .where(
                payments_table.c.provider == provider,
                payments_table.c.provider_ref == provider_ref,
                payments_table.c.status == PaymentStatus.PENDING.value,
            )
            .values(
                status=PaymentStatus.SUCCEEDED.value,
                paid_at=func.now(),
                updated_at=func.now(),
            )
        )
        result = conn.execute(stmt)
        return result.rowcount == 1


def mark_failed(
    provider: str,
    provider_ref: str,
    failure_code: str | None = None,
    failure_message: str | None = None,
) -> bool:
    """Conditionally mark a payment as FAILED (atomic, race-safe).

    Transitions from ``PENDING`` **or** ``CUSTOMER_ACTION_REQUIRED`` →
    ``FAILED``.  ``updated_at`` is set to ``now()``.

    Returns:
        ``True`` if exactly one row was updated, ``False`` otherwise.
    """
    values: dict = {
        "status": PaymentStatus.FAILED.value,
        "updated_at": func.now(),
    }
    if failure_code is not None:
        values["failure_code"] = failure_code
    if failure_message is not None:
        values["failure_message"] = failure_message

    with get_engine().begin() as conn:
        stmt = (
            update(payments_table)
            .where(
                payments_table.c.provider == provider,
                payments_table.c.provider_ref == provider_ref,
                payments_table.c.status.in_(
                    [
                        PaymentStatus.PENDING.value,
                        PaymentStatus.CUSTOMER_ACTION_REQUIRED.value,
                    ]
                ),
            )
            .values(**values)
        )
        result = conn.execute(stmt)
        return result.rowcount == 1


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _row_to_payment(row) -> PaymentSession:
    """Convert a SQLAlchemy Row to a PaymentSession domain model."""
    return PaymentSession(
        order_id=row.order_id,
        provider=row.provider,
        provider_ref=row.provider_ref,
        approval_url=row.approval_url or "",
        amount=Decimal(str(row.amount)),
        currency=row.currency,
        status=PaymentStatus(row.status),
    )
