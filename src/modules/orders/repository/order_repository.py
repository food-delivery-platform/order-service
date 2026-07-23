"""Read/write access to orders via SQLAlchemy Core (FDS-21, FDS-24, FDS-33).

Replaces the previous supabase-py implementation. Uses the shared engine
(DATABASE_URL) — the same connection path as payment_repository.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.modules.orders.model.delivery_address import DeliveryAddress
from src.modules.orders.model.order import Order
from src.modules.orders.model.order_item import OrderItem
from src.modules.orders.model.order_status import OrderStatus
from src.modules.orders.model.order_status_history import OrderStatusHistoryEntry
from src.shared.db.engine import (
    get_engine,
    order_items_table,
    order_status_history_table,
    orders_table,
)
from src.shared.errors.app_error import AppError

# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def get_orders_by_customer(customer_id: str) -> list[Order]:
    with get_engine().connect() as conn:
        order_rows = conn.execute(
            select(orders_table)
            .where(orders_table.c.customer_id == customer_id)
            .order_by(orders_table.c.created_at.desc())
        ).fetchall()
        if not order_rows:
            return []

        order_ids = [row.id for row in order_rows]
        items_by_order = _fetch_items(conn, order_ids)
        history_by_order = _fetch_history(conn, order_ids)

    return [
        _build_order(
            row,
            items_by_order.get(row.id, []),
            history_by_order.get(row.id, []),
        )
        for row in order_rows
    ]


def get_order_by_id(order_id: str) -> Order | None:
    with get_engine().connect() as conn:
        row = conn.execute(
            select(orders_table).where(orders_table.c.id == order_id).limit(1)
        ).first()
        if row is None:
            return None

        items = _fetch_items(conn, [order_id]).get(order_id, [])
        history = _fetch_history(conn, [order_id]).get(order_id, [])

    return _build_order(row, items, history)


# ---------------------------------------------------------------------------
# Write (idempotent upsert — replaces the upsert_order_with_items RPC)
# ---------------------------------------------------------------------------


def insert_order(order: Order) -> None:
    """Persist a new order atomically: order row + items + initial history.

    Idempotent — safe to replay from Step Functions:
      * orders   -> INSERT ... ON CONFLICT (id) DO UPDATE
      * items    -> delete-then-insert
      * history  -> insert the initial entry only if none exists yet
    """
    order_id = order.order_id
    created_at = _parse_ts(order.created_at)
    updated_at = _parse_ts(order.updated_at)

    order_values: dict = {
        "id": order_id,
        "customer_id": order.customer_id,
        "venue_id": order.restaurant_id,
        "delivery_address_id": order.delivery_address.address_id,
        "status": order.status.value,
        "subtotal": order.subtotal,
        "delivery_fee": 0,
        "total": order.subtotal,
        "currency": order.currency,
    }
    if created_at is not None:
        order_values["created_at"] = created_at
    if updated_at is not None:
        order_values["updated_at"] = updated_at

    with get_engine().begin() as conn:
        # 1) upsert order row
        stmt = pg_insert(orders_table).values(**order_values)
        set_ = {
            "customer_id": stmt.excluded.customer_id,
            "venue_id": stmt.excluded.venue_id,
            "delivery_address_id": stmt.excluded.delivery_address_id,
            "status": stmt.excluded.status,
            "subtotal": stmt.excluded.subtotal,
            "delivery_fee": stmt.excluded.delivery_fee,
            "total": stmt.excluded.total,
            "currency": stmt.excluded.currency,
        }
        if updated_at is not None:
            set_["updated_at"] = stmt.excluded.updated_at
        conn.execute(stmt.on_conflict_do_update(index_elements=["id"], set_=set_))

        # 2) items: delete-then-insert
        conn.execute(
            delete(order_items_table).where(order_items_table.c.order_id == order_id)
        )
        if order.items:
            conn.execute(
                order_items_table.insert(),
                [
                    {
                        "order_id": order_id,
                        "menu_item_id": item.menu_item_id,
                        "menu_item_name": item.name,
                        "unit_price": item.unit_price,
                        "quantity": item.quantity,
                        "line_total": item.line_total,
                    }
                    for item in order.items
                ],
            )

        # 3) initial status history — only if none exists yet
        already = conn.execute(
            select(order_status_history_table.c.order_id)
            .where(order_status_history_table.c.order_id == order_id)
            .limit(1)
        ).first()
        if already is None:
            conn.execute(
                order_status_history_table.insert().values(
                    order_id=order_id,
                    from_status=None,
                    to_status=order.status.value,
                    actor_id=order.customer_id,
                    actor_type="customer",
                    note=None,
                )
            )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _fetch_items(conn, order_ids: list[str]) -> dict[str, list[dict]]:
    rows = conn.execute(
        select(order_items_table).where(order_items_table.c.order_id.in_(order_ids))
    ).fetchall()
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r.order_id, []).append(
            {
                "menu_item_id": r.menu_item_id,
                "menu_item_name": r.menu_item_name,
                "quantity": r.quantity,
                "unit_price": r.unit_price,
                "line_total": r.line_total,
            }
        )
    return out


def _fetch_history(conn, order_ids: list[str]) -> dict[str, list[dict]]:
    rows = conn.execute(
        select(order_status_history_table)
        .where(order_status_history_table.c.order_id.in_(order_ids))
        .order_by(order_status_history_table.c.created_at.asc())
    ).fetchall()
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r.order_id, []).append(
            {
                "to_status": r.to_status,
                "created_at": r.created_at,
                "note": r.note,
            }
        )
    return out


def _build_order(row, item_dicts: list[dict], history_dicts: list[dict]) -> Order:
    if not item_dicts:
        raise AppError(500, "INVALID_ORDER_DATA", f"Order {row.id} has no items")

    items = [
        OrderItem(
            menu_item_id=i["menu_item_id"],
            name=i["menu_item_name"],
            quantity=int(i["quantity"]),
            unit_price=float(i["unit_price"]),
            line_total=float(i.get("line_total") or 0.0),
        )
        for i in item_dicts
    ]

    status_history = [
        OrderStatusHistoryEntry(
            status=OrderStatus(h["to_status"]),
            changed_at=_ts_str(h["created_at"]),
            reason=h.get("note"),
        )
        for h in history_dicts
    ]

    return Order(
        order_id=row.id,
        customer_id=row.customer_id,
        restaurant_id=row.venue_id,
        items=items,
        delivery_address=DeliveryAddress(address_id=row.delivery_address_id),
        status=OrderStatus(row.status),
        subtotal=float(row.subtotal or 0.0),
        currency=str(row.currency or "ILS"),
        status_history=status_history,
        created_at=_ts_str(row.created_at),
        updated_at=_ts_str(row.updated_at),
    )


def _parse_ts(value):
    """Domain models carry ISO strings; the DB columns are timestamptz."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _ts_str(value):
    """Return an ISO-8601 string (matches the old PostgREST behaviour)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)
