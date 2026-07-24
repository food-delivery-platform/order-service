"""Read/write access to customer addresses via SQLAlchemy Core (FDS-25, FDS-33).

Replaces the previous supabase-py implementation. Uses the shared engine
(DATABASE_URL) — the same connection path as order_repository.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from src.modules.orders.model.customer_address import CustomerAddress
from src.shared.db.engine import addresses_table, get_engine
from src.shared.utils import ids


def create_address(
    *,
    customer_id: str,
    street: str,
    city: str,
    postal_code: str,
    latitude: float | None = None,
    longitude: float | None = None,
    notes: str | None = None,
) -> CustomerAddress:
    """Insert a new address row, return the created model."""
    now = datetime.now(timezone.utc)
    address_id = ids.new_address_id()

    row = {
        "address_id": address_id,
        "customer_id": customer_id,
        "street": street,
        "city": city,
        "postal_code": postal_code,
        "latitude": latitude,
        "longitude": longitude,
        "notes": notes,
        "created_at": now,
    }

    with get_engine().begin() as conn:
        conn.execute(addresses_table.insert().values(**row))

    return CustomerAddress(
        address_id=address_id,
        customer_id=customer_id,
        street=street,
        city=city,
        postal_code=postal_code,
        latitude=latitude,
        longitude=longitude,
        notes=notes,
        created_at=now.isoformat(),
    )


def get_address(address_id: str) -> CustomerAddress | None:
    """Look up an address by id, or None if not found."""
    with get_engine().connect() as conn:
        row = conn.execute(
            select(addresses_table)
            .where(addresses_table.c.address_id == address_id)
            .limit(1)
        ).first()

    if row is None:
        return None

    return CustomerAddress(
        address_id=row.address_id,
        customer_id=row.customer_id,
        street=row.street,
        city=row.city,
        postal_code=row.postal_code,
        latitude=row.latitude,
        longitude=row.longitude,
        notes=row.notes,
        created_at=row.created_at.isoformat() if row.created_at else None,
    )
