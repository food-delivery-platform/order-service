"""Read access to orders stored in the database (FDS-21).

Only read methods are implemented in this task; writes arrive later.
"""
from __future__ import annotations

from src.modules.orders.model.delivery_address import DeliveryAddress
from src.modules.orders.model.order import Order
from src.modules.orders.model.order_item import OrderItem
from src.modules.orders.model.order_status import OrderStatus
from src.shared.db import supabase_client

_ORDERS_TABLE = "orders"


def get_orders_by_customer(customer_id: str) -> list[Order]:
    client = supabase_client.get_client()
    resp = (
        client.table(_ORDERS_TABLE)
        .select("*")
        .eq("customer_id", customer_id)
        .order("created_at", desc=True)
        .execute()
    )
    return [_row_to_order(row) for row in (resp.data or [])]


def get_order_by_id(order_id: str) -> Order | None:
    client = supabase_client.get_client()
    resp = (
        client.table(_ORDERS_TABLE)
        .select("*")
        .eq("order_id", order_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return _row_to_order(rows[0]) if rows else None


def _row_to_order(row: dict) -> Order:
    # TODO(FDS-21): align field names with the final DB schema (Yaroslav).
    items = [
        OrderItem(
            menu_item_id=i["menu_item_id"],
            name=i["name"],
            quantity=int(i["quantity"]),
            unit_price=float(i["unit_price"]),
        )
        for i in (row.get("items") or [])
    ]
    address_row = row.get("delivery_address") or {}
    delivery_address = DeliveryAddress(
        address_id=address_row.get("address_id", ""),
        street=address_row.get("street", ""),
        city=address_row.get("city", ""),
        postal_code=address_row.get("postal_code", ""),
    )
    return Order(
        order_id=row["order_id"],
        customer_id=row["customer_id"],
        restaurant_id=row["restaurant_id"],
        items=items,
        delivery_address=delivery_address,
        status=OrderStatus(row.get("status", OrderStatus.CREATED.value)),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )
