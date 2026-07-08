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
_REQUIRED_ADDRESS_FIELDS = ("address_id", "street", "city", "postal_code")


def get_orders_by_customer(customer_id: str) -> list[Order]:
    client = supabase_client.get_client()
    resp = (
        client.table(_ORDERS_TABLE)
        .select(f"*, {_ITEMS_TABLE}(*)")
        .eq("customer_id", customer_id)
        .order("created_at", desc=True)
        .execute()
    )
    return [_row_to_order(row) for row in (resp.data or [])]


def get_order_by_id(order_id: str) -> Order | None:
    client = supabase_client.get_client()
    resp = (
        client.table(_ORDERS_TABLE)
        .select(f"*, {_ITEMS_TABLE}(*)")
        .eq("order_id", order_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return _row_to_order(rows[0]) if rows else None


def insert_order(order: Order) -> None:
    """Persist a new order (FDS-24).

    Calls the ``upsert_order_with_items`` Postgres RPC function to atomically
    upsert the order row and its line items into the ``order_items`` table.
    The RPC is idempotent thanks to ``ON CONFLICT (order_id)`` — safe to
    replay from Step Functions.

    Deploy the function first:
        psql < scripts/order_items_rpc.sql
    """
    client = supabase_client.get_client()
    payload = {
        "order_row": {
            "order_id": order.order_id,
            "customer_id": order.customer_id,
            "restaurant_id": order.restaurant_id,
            "delivery_address": {
                "address_id": order.delivery_address.address_id,
                "street": order.delivery_address.street,
                "city": order.delivery_address.city,
                "postal_code": order.delivery_address.postal_code,
                "latitude": order.delivery_address.latitude,
                "longitude": order.delivery_address.longitude,
                "notes": order.delivery_address.notes,
            },
            "status": order.status.value,
            "subtotal": order.subtotal,
            "currency": order.currency,
            "status_history": [
                {
                    "status": entry.status.value,
                    "changed_at": entry.changed_at,
                    "reason": entry.reason,
                }
                for entry in order.status_history
            ],
            "created_at": order.created_at,
            "updated_at": order.updated_at,
        },
        "items": [
            {
                "menu_item_id": item.menu_item_id,
                "name": item.name,
                "unit_price": item.unit_price,
                "quantity": item.quantity,
                "line_total": item.line_total,
            }
            for item in order.items
        ],
    }
    client.rpc("upsert_order_with_items", {"payload": payload}).execute()


def _row_to_order(row: dict) -> Order:
    order_id = row["order_id"]

    # Items now come from the order_items table (PostgREST resource embedding).
    item_rows = row.get(_ITEMS_TABLE) or []
    if not item_rows:
        raise AppError(500, "INVALID_ORDER_DATA", f"Order {order_id} has no items")
    items = [
        OrderItem(
            menu_item_id=i["menu_item_id"],
            name=i["name"],
            quantity=int(i["quantity"]),
            unit_price=float(i["unit_price"]),
            line_total=float(i.get("line_total", 0.0)),
        )
        for i in item_rows
    ]

    delivery_address = _row_to_address(order_id, row.get("delivery_address") or {})

    # Deserialize status_history from JSONB.
    status_history_raw = row.get("status_history") or []
    status_history = [
        OrderStatusHistoryEntry(
            status=OrderStatus(entry["status"]),
            changed_at=entry["changed_at"],
            reason=entry.get("reason"),
        )
        for entry in status_history_raw
    ]

    return Order(
        order_id=order_id,
        customer_id=row["customer_id"],
        restaurant_id=row["restaurant_id"],
        items=items,
        delivery_address=delivery_address,
        status=OrderStatus(row.get("status", OrderStatus.CREATED.value)),
        subtotal=float(row.get("subtotal", 0.0)),
        currency=str(row.get("currency", "ILS")),
        status_history=status_history,
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


def _row_to_address(order_id: str, address_row: dict) -> DeliveryAddress:
    missing = [f for f in _REQUIRED_ADDRESS_FIELDS if not address_row.get(f)]
    if missing:
        raise AppError(
            500,
            "INVALID_ORDER_DATA",
            f"Order {order_id} address is missing fields: {', '.join(missing)}",
        )
    return DeliveryAddress(
        address_id=address_row["address_id"],
        street=address_row["street"],
        city=address_row["city"],
        postal_code=address_row["postal_code"],
        latitude=address_row.get("latitude"),
        longitude=address_row.get("longitude"),
        notes=address_row.get("notes"),
    )
