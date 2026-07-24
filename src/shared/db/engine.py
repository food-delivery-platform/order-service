"""SQLAlchemy engine and table metadata (FDS-27 R2, FDS-33).

Provides a lazy module-level engine (session-pooler safe via NullPool),
``MetaData``, and ``Table`` definitions for the ``payments`` and ``orders``
schemas.
"""

from __future__ import annotations

import logging
import os
from urllib.parse import quote_plus

from sqlalchemy import (
    CHAR,
    Column,
    DateTime,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.pool import NullPool

from src.shared.config.secrets import get_service_secret

logger = logging.getLogger(__name__)

_engine = None
metadata = MetaData()

# Postgres owns these enum types (managed by DB migrations). create_type=False
# tells SQLAlchemy never to emit CREATE TYPE and to bind values with a cast so
# INSERT/UPDATE match the real column type.
payment_status = ENUM(
    "PENDING",
    "CUSTOMER_ACTION_REQUIRED",
    "SUCCEEDED",
    "FAILED",
    "REFUNDED",
    name="payment_status",
    create_type=False,
)

order_status = ENUM(
    "CREATED",
    "PENDING_PAYMENT",
    "PAID",
    "READY",
    "PICKED_UP",
    "DELIVERED",
    "PAYMENT_FAILED",
    "CANCELLED",
    "FAILED",
    name="order_status",
    create_type=False,
)

# ---------------------------------------------------------------------------
# payments table — exact schema match
# ---------------------------------------------------------------------------

payments_table = Table(
    "payments",
    metadata,
    Column(
        "id",
        UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    ),
    Column("order_id", UUID(as_uuid=False), nullable=False),
    Column("provider", Text, nullable=False),
    Column("provider_ref", Text, nullable=True),
    Column("idempotency_key", Text, nullable=False, unique=True),
    Column(
        "status",
        payment_status,
        nullable=False,
        server_default=text("'PENDING'"),
    ),
    Column("amount", Numeric(10, 2), nullable=False),
    Column("currency", CHAR(3), nullable=False, server_default=text("'USD'")),
    Column("failure_code", Text, nullable=True),
    Column("failure_message", Text, nullable=True),
    Column("paid_at", String(50), nullable=True),
    Column("approval_url", Text, nullable=True),
    Column("created_at", String(50), nullable=False, server_default=text("now()")),
    Column("updated_at", String(50), nullable=False, server_default=text("now()")),
    UniqueConstraint("provider", "provider_ref"),
)

# ---------------------------------------------------------------------------
# orders tables — match scripts/order_items_rpc.sql
# ---------------------------------------------------------------------------

orders_table = Table(
    "orders",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True),
    Column("customer_id", UUID(as_uuid=False), nullable=False),
    Column("venue_id", UUID(as_uuid=False), nullable=False),
    Column("delivery_address_id", UUID(as_uuid=False), nullable=False),
    Column("status", order_status, nullable=False, server_default=text("'CREATED'")),
    Column("subtotal", Numeric(10, 2), nullable=False, server_default=text("0")),
    Column("delivery_fee", Numeric(10, 2), nullable=False, server_default=text("0")),
    Column("total", Numeric(10, 2), nullable=False, server_default=text("0")),
    Column("currency", Text, nullable=False, server_default=text("'ILS'")),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    Column(
        "updated_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
)

order_items_table = Table(
    "order_items",
    metadata,
    Column("order_id", UUID(as_uuid=False), nullable=False),
    Column("menu_item_id", UUID(as_uuid=False), nullable=False),
    Column("menu_item_name", Text, nullable=False),
    Column("unit_price", Numeric(10, 2), nullable=False),
    Column("quantity", Integer, nullable=False),
    Column("line_total", Numeric(10, 2), nullable=False),
)

order_status_history_table = Table(
    "order_status_history",
    metadata,
    Column("order_id", UUID(as_uuid=False), nullable=False),
    Column("from_status", order_status, nullable=True),
    Column("to_status", order_status, nullable=False),
    Column("actor_id", UUID(as_uuid=False), nullable=True),
    Column("actor_type", Text, nullable=True),
    Column("note", Text, nullable=True),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
)

# ---------------------------------------------------------------------------
# addresses table (FDS-33)
# ---------------------------------------------------------------------------

addresses_table = Table(
    "addresses",
    metadata,
    Column("address_id", UUID(as_uuid=False), primary_key=True),
    Column("customer_id", UUID(as_uuid=False), nullable=False),
    Column("street", Text, nullable=False),
    Column("city", Text, nullable=False),
    Column("postal_code", Text, nullable=False),
    Column("latitude", Numeric(10, 7), nullable=True),
    Column("longitude", Numeric(10, 7), nullable=True),
    Column("notes", Text, nullable=True),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
)

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


def _dsn() -> str:
    """Build the SQLAlchemy DSN.

    Precedence:
      1. A full DSN via ``database_url`` (secret) or ``DATABASE_URL`` (env).
      2. Assembled from ``DB_HOST`` / ``DB_USER`` / ``DB_PASS`` /
         ``DB_NAME`` / ``DB_PORT`` (secret first, plain env second).

    Raises:
        RuntimeError: when no usable configuration is found.
    """
    secret = get_service_secret()

    dsn = secret.get("database_url") or os.environ.get("DATABASE_URL")
    if dsn:
        return dsn

    def _cfg(key: str) -> str | None:
        value = secret.get(key)
        if value is not None:
            return value
        return os.environ.get(key)

    host = _cfg("DB_HOST")
    user = _cfg("DB_USER")
    password = _cfg("DB_PASS")
    name = _cfg("DB_NAME")
    port = _cfg("DB_PORT") or "5432"

    if host and user and password and name:
        return (
            f"postgresql+psycopg://{quote_plus(user)}:{quote_plus(password)}"
            f"@{host}:{port}/{name}"
        )

    raise RuntimeError("DATABASE_URL not configured")


def get_engine():
    """Return the lazy-initialised SQLAlchemy ``Engine``.

    Uses ``NullPool`` so connections are not reused across Lambda
    invocations (session pooler is assumed).
    """
    global _engine
    if _engine is None:
        _engine = create_engine(
            _dsn(),
            poolclass=NullPool,
        )
    return _engine
