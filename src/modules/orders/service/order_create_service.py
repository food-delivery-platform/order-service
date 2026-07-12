"""Order creation and persistence service (FDS-24).

Receives validated cart data from the ``validate_order`` Step Functions step,
builds snapshots of every line item, computes totals, and persists the order.
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.modules.orders.model.delivery_address import DeliveryAddress
from src.modules.orders.model.order import Order
from src.modules.orders.model.order_item import OrderItem
from src.modules.orders.model.order_status import OrderStatus
from src.modules.orders.model.order_status_history import OrderStatusHistoryEntry
from src.modules.orders.repository import order_repository
from src.shared.utils import ids


def create_order(
    *,
    customer_id: str,
    restaurant_id: str,
    validated_items: list[dict],
    delivery_address: DeliveryAddress,
    order_id: str | None = None,
) -> Order:
    """Build, persist, and return a new order.

    Parameters
    ----------
    customer_id:
        The customer placing the order.
    restaurant_id:
        The restaurant the order is placed with.
    validated_items:
        List of dicts from the validate_order step::
            {menu_item_id, name, unit_price, quantity}
    delivery_address:
        Fully resolved DeliveryAddress from the upstream resolve-address step
        (FDS-25).
    order_id:
        Optional pre-generated order id.  A new one is created when omitted.

    Returns
    -------
    Order
        The fully constructed, persisted order with ``PENDING_PAYMENT`` status.

    Raises
    ------
    AppError
        When persistence fails (let it bubble up to the handler).
    """
    now = _utcnow_iso()

    # --- snapshot every line item ---
    items: list[OrderItem] = []
    for vi in validated_items:
        unit_price = float(vi["unit_price"])
        quantity = int(vi["quantity"])
        items.append(
            OrderItem(
                menu_item_id=vi["menu_item_id"],
                name=vi["name"],
                quantity=quantity,
                unit_price=unit_price,
                line_total=round(unit_price * quantity, 2),
            )
        )

    subtotal = round(sum(item.line_total for item in items), 2)

    order = Order(
        order_id=order_id or ids.new_order_id(),
        customer_id=customer_id,
        restaurant_id=restaurant_id,
        items=items,
        delivery_address=delivery_address,
        status=OrderStatus.PENDING_PAYMENT,
        subtotal=subtotal,
        currency="ILS",
        status_history=[
            OrderStatusHistoryEntry(
                status=OrderStatus.PENDING_PAYMENT,
                changed_at=now,
                reason=None,
            )
        ],
        created_at=now,
        updated_at=now,
    )

    order_repository.insert_order(order)
    return order


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
