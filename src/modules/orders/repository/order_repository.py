"""Read/write access to orders stored in the database (FDS-21, FDS-24)."""

from __future__ import annotations

from src.modules.orders.model.delivery_address import DeliveryAddress
from src.modules.orders.model.order import Order
from src.modules.orders.model.order_item import OrderItem
from src.modules.orders.model.order_status import OrderStatus
from src.modules.orders.model.order_status_history import OrderStatusHistoryEntry
from src.shared.db import supabase_client
from src.shared.errors.app_error import AppError

_ORDERS_TABLE = "orders"
_ITEMS_TABLE = "order_items"
_HISTORY_TABLE = "order_status_history"


def get_orders_by_customer(customer_id: str) -> list[Order]:
    client = supabase_client.get_client()
    resp = (
        client.table(_ORDERS_TABLE)
        .select(f"*, {_ITEMS_TABLE}(*), {_HISTORY_TABLE}(*)")
        .eq("customer_id", customer_id)
        .order("created_at", desc=True)
        .execute()
    )
    return [_row_to_order(row) for row in (resp.data or [])]


def get_order_by_id(order_id: str) -> Order | None:
    client = supabase_client.get_client()
    resp = (
        client.table(_ORDERS_TABLE)
        .select(f"*, {_ITEMS_TABLE}(*), {_HISTORY_TABLE}(*)")
        .eq("id", order_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return _row_to_order(rows[0]) if rows else None


def insert_order(order: Order) -> None:
    """Persist a new order (FDS-24).

    Calls the ``upsert_order_with_items`` Postgres RPC function to atomically
    upsert the order row, its line items, and the initial status history entry.
    The RPC is idempotent — safe to replay from Step Functions.

    Deploy the function first:
        psql < scripts/order_items_rpc.sql
    """
    client = supabase_client.get_client()
    payload = {
        "order_row": {
            "id": order.order_id,
            "customer_id": order.customer_id,
            "venue_id": order.restaurant_id,
            "delivery_address_id": order.delivery_address.address_id,
            "status": order.status.value,
            "subtotal": order.subtotal,
            "delivery_fee": 0,
            "total": order.subtotal,
            "currency": order.currency,
            "created_at": order.created_at,
            "updated_at": order.updated_at,
        },
        "items": [
            {
                "menu_item_id": item.menu_item_id,
                "menu_item_name": item.name,
                "unit_price": item.unit_price,
                "quantity": item.quantity,
                "line_total": item.line_total,
            }
            for item in order.items
        ],
    }
    client.rpc("upsert_order_with_items", {"payload": payload}).execute()


def _row_to_order(row: dict) -> Order:
    _require_columns(row, "id", "customer_id", "venue_id", "delivery_address_id")
    order_id = row["id"]

    # Items from order_items table (PostgREST resource embedding).
    item_rows = row.get(_ITEMS_TABLE) or []
    if not item_rows:
        raise AppError(500, "INVALID_ORDER_DATA", f"Order {order_id} has no items")
    items = []
    for i in item_rows:
        _require_columns(i, "menu_item_id", "menu_item_name", "quantity", "unit_price")
        items.append(
            OrderItem(
                menu_item_id=i["menu_item_id"],
                name=i["menu_item_name"],
                quantity=int(i["quantity"]),
                unit_price=float(i["unit_price"]),
                line_total=float(i.get("line_total", 0.0)),
            )
        )

    # Full address is resolved via a join to the addresses table (FDS-25).
    # For now we only carry the FK.
    delivery_address = DeliveryAddress(
        address_id=row["delivery_address_id"],
    )

    # Deserialize status_history from order_status_history embedding.
    history_rows = row.get(_HISTORY_TABLE) or []
    status_history = []
    for h in history_rows:
        _require_columns(h, "to_status", "created_at")
        status_history.append(
            OrderStatusHistoryEntry(
                status=OrderStatus(h["to_status"]),
                changed_at=h["created_at"],
                reason=h.get("note"),
            )
        )

    return Order(
        order_id=order_id,
        customer_id=row["customer_id"],
        restaurant_id=row["venue_id"],
        items=items,
        delivery_address=delivery_address,
        status=OrderStatus(row.get("status", OrderStatus.CREATED.value)),
        subtotal=float(row.get("subtotal", 0.0)),
        currency=str(row.get("currency", "ILS")),
        status_history=status_history,
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


def _require_columns(row: dict, *names: str) -> None:
    """Raise AppError if any required column is missing from the row."""
    for name in names:
        if name not in row:
            raise AppError(
                500,
                "INVALID_ORDER_DATA",
                f"Order row is missing required column '{name}'",
            )
