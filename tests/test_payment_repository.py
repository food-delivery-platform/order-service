"""Hermetic unit tests for payment_repository (FDS-27 R2).

All tests mock the SQLAlchemy engine — no database connection.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from src.shared.payments.models import PaymentSession, PaymentStatus
from src.shared.payments.payment_repository import (
    create_payment,
    get_by_provider_ref,
    mark_failed,
    mark_paid,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_engine():
    """Return a MagicMock that simulates the SQLAlchemy engine + connection."""
    mock_conn = MagicMock()
    mock_engine = MagicMock()
    mock_engine.begin.return_value.__enter__.return_value = mock_conn
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    return mock_engine, mock_conn


def _setup_insert_ok(mock_conn):
    """Configure so conn.execute(insert_stmt) succeeds."""
    mock_conn.execute.return_value = MagicMock()


def _setup_insert_integrity_error(mock_conn):
    """Configure so conn.execute(insert_stmt) raises IntegrityError."""
    mock_conn.execute.side_effect = IntegrityError(
        "duplicate", params={}, orig=Exception()
    )


def _setup_select_row(mock_conn, row_data: dict | None):
    """Configure so conn.execute(select_stmt).fetchone() returns a row."""
    mock_result = MagicMock()
    if row_data is not None:
        row = MagicMock()
        # Allow attribute access (e.g. row.order_id) and dict-like access
        for k, v in row_data.items():
            setattr(row, k, v)
        mock_result.fetchone.return_value = row
    else:
        mock_result.fetchone.return_value = None
    mock_conn.execute.return_value = mock_result


def _setup_update_result(mock_conn, rowcount: int):
    """Configure so conn.execute(update_stmt).rowcount == rowcount."""
    mock_result = MagicMock()
    mock_result.rowcount = rowcount
    mock_conn.execute.return_value = mock_result


def _payment_row(
    *,
    order_id: str = "ord-1",
    provider: str = "paypal",
    provider_ref: str = "PP-1",
    status: str = "PENDING",
    amount: str = "50.00",
    currency: str = "ILS",
    approval_url: str = "https://paypal.com/approve",
) -> dict:
    return {
        "order_id": order_id,
        "provider": provider,
        "provider_ref": provider_ref,
        "status": status,
        "amount": amount,
        "currency": currency,
        "approval_url": approval_url,
    }


# ---------------------------------------------------------------------------
# create_payment — happy path
# ---------------------------------------------------------------------------


@patch("src.shared.payments.payment_repository.get_engine")
def test_create_payment_happy_path(mock_get_engine):
    mock_engine, mock_conn = _mock_engine()
    mock_get_engine.return_value = mock_engine
    _setup_insert_ok(mock_conn)

    result = create_payment(
        order_id="ord-1",
        provider="paypal",
        provider_ref="PP-1",
        amount=Decimal("50.00"),
        currency="ILS",
    )

    assert isinstance(result, PaymentSession)
    assert result.order_id == "ord-1"
    assert result.provider == "paypal"
    assert result.provider_ref == "PP-1"
    assert result.amount == Decimal("50.00")
    assert result.currency == "ILS"
    assert result.status == PaymentStatus.PENDING
    # Verify insert params
    call_args = mock_conn.execute.call_args[0][0]
    compiled = call_args.compile()
    params = compiled.params
    assert params["order_id"] == "ord-1"
    assert params["provider"] == "paypal"
    assert params["provider_ref"] == "PP-1"
    assert params["status"] == "PENDING"
    assert params["amount"] == Decimal("50.00")
    assert params["currency"] == "ILS"
    # idempotency_key is composite
    assert params["idempotency_key"] == "paypal:PP-1:ord-1"


# ---------------------------------------------------------------------------
# create_payment — idempotency (IntegrityError → returns existing)
# ---------------------------------------------------------------------------


@patch("src.shared.payments.payment_repository.get_engine")
def test_create_payment_duplicate_is_idempotent(mock_get_engine):
    mock_engine, mock_conn = _mock_engine()
    mock_get_engine.return_value = mock_engine

    # First call inside begin() — IntegrityError on insert
    _setup_insert_integrity_error(mock_conn)
    # Then the connect() call for get_by_provider_ref returns the existing row
    row = _payment_row()

    # We need separate mocks for begin() and connect()
    # The create_payment uses begin() first, then on IntegrityError falls to connect()
    # Actually, begin() returns a context manager. Let me restructure.
    # The pattern: with get_engine().begin() as conn: ...  (this is the write tx)
    # Then after the block: with get_engine().connect() as conn: ... (read)
    write_conn = MagicMock()
    write_conn.execute.side_effect = IntegrityError(
        "duplicate", params={}, orig=Exception()
    )
    read_conn = MagicMock()
    read_result = MagicMock()
    read_row = MagicMock()
    for k, v in row.items():
        setattr(read_row, k, v)
    read_result.fetchone.return_value = read_row
    read_conn.execute.return_value = read_result

    # First call returns write_conn, second returns read_conn
    mock_engine.begin.return_value.__enter__.return_value = write_conn
    mock_engine.connect.return_value.__enter__.return_value = read_conn

    result = create_payment(
        order_id="ord-1",
        provider="paypal",
        provider_ref="PP-1",
        amount=Decimal("50.00"),
        currency="ILS",
    )

    assert result.provider_ref == "PP-1"
    assert result.order_id == "ord-1"


@patch("src.shared.payments.payment_repository.get_engine")
def test_create_payment_duplicate_but_not_found_reraises(mock_get_engine):
    """When IntegrityError fires but get_by_provider_ref returns None."""
    mock_engine = MagicMock()
    write_conn = MagicMock()
    write_conn.execute.side_effect = IntegrityError(
        "duplicate", params={}, orig=Exception()
    )
    read_conn = MagicMock()
    read_result = MagicMock()
    read_result.fetchone.return_value = None
    read_conn.execute.return_value = read_result

    mock_engine.begin.return_value.__enter__.return_value = write_conn
    mock_engine.connect.return_value.__enter__.return_value = read_conn
    mock_get_engine.return_value = mock_engine

    with pytest.raises(RuntimeError, match="get_by_provider_ref returned None"):
        create_payment(
            order_id="ord-1",
            provider="paypal",
            provider_ref="PP-1",
            amount=Decimal("50.00"),
            currency="ILS",
        )


# ---------------------------------------------------------------------------
# get_by_provider_ref
# ---------------------------------------------------------------------------


@patch("src.shared.payments.payment_repository.get_engine")
def test_get_by_provider_ref_found(mock_get_engine):
    mock_engine, mock_conn = _mock_engine()
    mock_get_engine.return_value = mock_engine
    _setup_select_row(mock_conn, _payment_row())

    result = get_by_provider_ref("paypal", "PP-1")
    assert result is not None
    assert result.provider_ref == "PP-1"
    assert result.provider == "paypal"


@patch("src.shared.payments.payment_repository.get_engine")
def test_get_by_provider_ref_not_found(mock_get_engine):
    mock_engine, mock_conn = _mock_engine()
    mock_get_engine.return_value = mock_engine
    _setup_select_row(mock_conn, None)

    result = get_by_provider_ref("paypal", "DOES-NOT-EXIST")
    assert result is None


# ---------------------------------------------------------------------------
# mark_paid — atomic conditional UPDATE
# ---------------------------------------------------------------------------


@patch("src.shared.payments.payment_repository.get_engine")
def test_mark_paid_updates_pending_to_succeeded(mock_get_engine):
    mock_engine, mock_conn = _mock_engine()
    mock_get_engine.return_value = mock_engine
    _setup_update_result(mock_conn, rowcount=1)

    result = mark_paid("paypal", "PP-1")
    assert result is True

    # Check the compiled UPDATE params contain the right values
    call_args = mock_conn.execute.call_args[0][0]
    compiled = call_args.compile()
    assert "payments" in str(compiled)
    # Provider/provider_ref are in the WHERE clause — check values, not param names
    params = compiled.params
    assert "paypal" in params.values()
    assert "PP-1" in params.values()
    assert PaymentStatus.SUCCEEDED.value in params.values()


@patch("src.shared.payments.payment_repository.get_engine")
def test_mark_paid_already_terminal_returns_false(mock_get_engine):
    mock_engine, mock_conn = _mock_engine()
    mock_get_engine.return_value = mock_engine
    _setup_update_result(mock_conn, rowcount=0)

    result = mark_paid("paypal", "PP-1")
    assert result is False


@patch("src.shared.payments.payment_repository.get_engine")
def test_mark_paid_nonexistent_returns_false(mock_get_engine):
    mock_engine, mock_conn = _mock_engine()
    mock_get_engine.return_value = mock_engine
    _setup_update_result(mock_conn, rowcount=0)

    result = mark_paid("paypal", "DOES-NOT-EXIST")
    assert result is False


# ---------------------------------------------------------------------------
# mark_failed — atomic conditional UPDATE
# ---------------------------------------------------------------------------


@patch("src.shared.payments.payment_repository.get_engine")
def test_mark_failed_sets_failed_from_pending(mock_get_engine):
    mock_engine, mock_conn = _mock_engine()
    mock_get_engine.return_value = mock_engine
    _setup_update_result(mock_conn, rowcount=1)

    result = mark_failed("paypal", "PP-1")
    assert result is True

    call_args = mock_conn.execute.call_args[0][0]
    compiled = call_args.compile()
    params = compiled.params
    assert "paypal" in params.values()
    assert "PP-1" in params.values()
    assert PaymentStatus.FAILED.value in params.values()


@patch("src.shared.payments.payment_repository.get_engine")
def test_mark_failed_with_failure_details(mock_get_engine):
    mock_engine, mock_conn = _mock_engine()
    mock_get_engine.return_value = mock_engine
    _setup_update_result(mock_conn, rowcount=1)

    result = mark_failed(
        "paypal",
        "PP-1",
        failure_code="INSUFFICIENT_FUNDS",
        failure_message="Not enough money",
    )
    assert result is True

    call_args = mock_conn.execute.call_args[0][0]
    compiled = call_args.compile()
    assert compiled.params.get("failure_code") == "INSUFFICIENT_FUNDS"
    assert compiled.params.get("failure_message") == "Not enough money"


@patch("src.shared.payments.payment_repository.get_engine")
def test_mark_failed_nonexistent_returns_false(mock_get_engine):
    mock_engine, mock_conn = _mock_engine()
    mock_get_engine.return_value = mock_engine
    _setup_update_result(mock_conn, rowcount=0)

    result = mark_failed("paypal", "DOES-NOT-EXIST")
    assert result is False


@patch("src.shared.payments.payment_repository.get_engine")
def test_mark_failed_already_terminal_returns_false(mock_get_engine):
    """When payment is already SUCCEEDED or REFUNDED, mark_failed returns False."""
    mock_engine, mock_conn = _mock_engine()
    mock_get_engine.return_value = mock_engine
    _setup_update_result(mock_conn, rowcount=0)

    result = mark_failed("paypal", "PP-ALREADY-DONE")
    assert result is False
