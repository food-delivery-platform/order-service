"""Hermetic unit tests for payment_repository (FDS-27).

All tests mock the Supabase DB client — no network calls.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from src.shared.payments.models import PaymentSession, PaymentStatus
from src.shared.payments.payment_repository import (
    create_payment,
    get_by_paypal_order_id,
    mark_failed,
    mark_paid,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _mock_client():
    """Return a MagicMock that mimics the supabase client chain."""
    return MagicMock()


def _mock_insert_ok(mock_client, row: dict):
    """Configure the mock so .table().insert().execute() succeeds."""
    chain = mock_client.table.return_value
    chain.insert.return_value.execute.return_value.data = [row]


def _mock_insert_conflict(mock_client):
    """Configure the mock so .table().insert().execute() raises a conflict."""
    chain = mock_client.table.return_value
    chain.insert.return_value.execute.side_effect = RuntimeError(
        "duplicate key value violates unique constraint"
    )


def _mock_select(mock_client, rows: list[dict] | None = None):
    """Configure the mock so .table().select().eq().execute() returns rows."""
    chain = mock_client.table.return_value
    chain.select.return_value.eq.return_value.execute.return_value.data = rows or []
    # Also support chaining .select(...).eq(...).limit(...).execute()
    chain.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = (
        rows or []
    )
    return mock_client


def _payment_row(
    *,
    order_id: str = "ord-1",
    paypal_order_id: str = "PP-1",
    status: str = "CREATED",
    amount: str = "50.00",
    currency: str = "ILS",
    approval_url: str = "https://paypal.com/approve",
) -> dict:
    return {
        "order_id": order_id,
        "paypal_order_id": paypal_order_id,
        "status": status,
        "amount": amount,
        "currency": currency,
        "approval_url": approval_url,
    }


# ---------------------------------------------------------------------------
# create_payment — happy path
# ---------------------------------------------------------------------------


@patch("src.shared.payments.payment_repository.supabase_client.get_client")
def test_create_payment_happy_path(mock_get_client):
    client = _mock_client()
    mock_get_client.return_value = client

    row = _payment_row()
    _mock_insert_ok(client, row)

    result = create_payment(
        order_id="ord-1",
        paypal_order_id="PP-1",
        amount=Decimal("50.00"),
        currency="ILS",
    )

    assert isinstance(result, PaymentSession)
    assert result.order_id == "ord-1"
    assert result.paypal_order_id == "PP-1"
    assert result.amount == Decimal("50.00")
    assert result.currency == "ILS"
    assert result.status == PaymentStatus.CREATED
    # Verify the insert payload includes the key fields.
    insert_call = client.table.return_value.insert
    insert_call.assert_called_once()
    payload = insert_call.call_args[0][0]
    assert payload["paypal_order_id"] == "PP-1"
    assert payload["order_id"] == "ord-1"
    assert payload["status"] == "CREATED"
    assert payload["amount"] == "50.00"


# ---------------------------------------------------------------------------
# create_payment — idempotency (duplicate paypal_order_id)
# ---------------------------------------------------------------------------


@patch("src.shared.payments.payment_repository.supabase_client.get_client")
def test_create_payment_duplicate_is_idempotent(mock_get_client):
    client = _mock_client()
    mock_get_client.return_value = client

    row = _payment_row()
    _mock_insert_conflict(client)
    _mock_select(client, [row])

    result = create_payment(
        order_id="ord-1",
        paypal_order_id="PP-1",
        amount=Decimal("50.00"),
        currency="ILS",
    )

    assert result.paypal_order_id == "PP-1"
    # The insert was attempted (and hit the conflict).
    client.table.return_value.insert.assert_called_once()


# ---------------------------------------------------------------------------
# get_by_paypal_order_id
# ---------------------------------------------------------------------------


@patch("src.shared.payments.payment_repository.supabase_client.get_client")
def test_get_by_paypal_order_id_found(mock_get_client):
    client = _mock_client()
    mock_get_client.return_value = client
    _mock_select(client, [_payment_row()])

    result = get_by_paypal_order_id("PP-1")
    assert result is not None
    assert result.paypal_order_id == "PP-1"


@patch("src.shared.payments.payment_repository.supabase_client.get_client")
def test_get_by_paypal_order_id_not_found(mock_get_client):
    client = _mock_client()
    mock_get_client.return_value = client
    _mock_select(client, [])

    result = get_by_paypal_order_id("DOES-NOT-EXIST")
    assert result is None


# ---------------------------------------------------------------------------
# mark_paid
# ---------------------------------------------------------------------------


@patch("src.shared.payments.payment_repository.supabase_client.get_client")
def test_mark_paid_first_call_returns_true(mock_get_client):
    client = _mock_client()
    mock_get_client.return_value = client

    # Payment exists with status CREATED.
    _mock_select(client, [_payment_row(status="CREATED")])

    result = mark_paid("PP-1")
    assert result is True
    # Verify the update was called with PAID status.
    update_call = client.table.return_value.update
    update_call.assert_called_once()
    assert update_call.call_args[0][0]["status"] == "PAID"


@patch("src.shared.payments.payment_repository.supabase_client.get_client")
def test_mark_paid_second_call_returns_false(mock_get_client):
    client = _mock_client()
    mock_get_client.return_value = client

    # Payment is already PAID.
    _mock_select(client, [_payment_row(status="PAID")])

    result = mark_paid("PP-1")
    assert result is False
    # Update must NOT be called when already PAID.
    client.table.return_value.update.assert_not_called()


@patch("src.shared.payments.payment_repository.supabase_client.get_client")
def test_mark_paid_nonexistent_returns_false(mock_get_client):
    client = _mock_client()
    mock_get_client.return_value = client
    _mock_select(client, [])

    result = mark_paid("DOES-NOT-EXIST")
    assert result is False
    # Update must NOT be called for nonexistent row.
    client.table.return_value.update.assert_not_called()


# ---------------------------------------------------------------------------
# mark_failed
# ---------------------------------------------------------------------------


@patch("src.shared.payments.payment_repository.supabase_client.get_client")
def test_mark_failed_sets_failed(mock_get_client):
    client = _mock_client()
    mock_get_client.return_value = client

    mark_failed("PP-1", PaymentStatus.FAILED)

    # Verify update was called with FAILED status.
    update_call = client.table.return_value.update
    update_call.assert_called_once()
    call_args = update_call.call_args[0][0]
    assert call_args["status"] == "FAILED"


@patch("src.shared.payments.payment_repository.supabase_client.get_client")
def test_mark_failed_sets_cancelled(mock_get_client):
    client = _mock_client()
    mock_get_client.return_value = client

    mark_failed("PP-1", PaymentStatus.CANCELLED)

    update_call = client.table.return_value.update
    call_args = update_call.call_args[0][0]
    assert call_args["status"] == "CANCELLED"


@patch("src.shared.payments.payment_repository.supabase_client.get_client")
def test_mark_failed_rejects_paid(mock_get_client):
    client = _mock_client()
    mock_get_client.return_value = client

    with pytest.raises(ValueError, match="only accepts FAILED or CANCELLED"):
        mark_failed("PP-1", PaymentStatus.PAID)


@patch("src.shared.payments.payment_repository.supabase_client.get_client")
def test_mark_failed_rejects_created(mock_get_client):
    client = _mock_client()
    mock_get_client.return_value = client

    with pytest.raises(ValueError, match="only accepts FAILED or CANCELLED"):
        mark_failed("PP-1", PaymentStatus.CREATED)
