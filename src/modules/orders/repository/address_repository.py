"""Read/write access to customer addresses stored in Supabase (FDS-25).

Addresses live in the local ``addresses`` table — same Supabase instance as
orders, but a separate table (no JSONB embedding).
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.modules.orders.model.customer_address import CustomerAddress
from src.shared.db import supabase_client
from src.shared.utils import ids

_ADDRESSES_TABLE = "addresses"


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
    client = supabase_client.get_client()
    now = datetime.now(timezone.utc).isoformat()
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
    client.table(_ADDRESSES_TABLE).insert(row).execute()
    return CustomerAddress(**row)


def get_address(address_id: str) -> CustomerAddress | None:
    """Look up an address by id, or None if not found."""
    client = supabase_client.get_client()
    resp = (
        client.table(_ADDRESSES_TABLE)
        .select("*")
        .eq("address_id", address_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    if not rows:
        return None
    return CustomerAddress(
        address_id=rows[0]["address_id"],
        customer_id=rows[0]["customer_id"],
        street=rows[0]["street"],
        city=rows[0]["city"],
        postal_code=rows[0]["postal_code"],
        latitude=rows[0].get("latitude"),
        longitude=rows[0].get("longitude"),
        notes=rows[0].get("notes"),
        created_at=rows[0].get("created_at"),
    )
