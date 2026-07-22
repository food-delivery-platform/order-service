"""SQLAlchemy engine and table metadata (FDS-27 R2).

Provides a lazy module-level engine (session-pooler safe via NullPool),
``MetaData``, and ``Table`` definitions for the ``payments`` schema.
"""

from __future__ import annotations

import logging
import os
from urllib.parse import quote_plus

from sqlalchemy import (
    CHAR,
    Column,
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

# Postgres already owns the `payment_status` enum type (managed by DB
# migrations). create_type=False tells SQLAlchemy never to emit CREATE TYPE
# and to bind values with a ::payment_status cast so INSERT/UPDATE match the
# real column type.
payment_status = ENUM(
    "PENDING",
    "CUSTOMER_ACTION_REQUIRED",
    "SUCCEEDED",
    "FAILED",
    "REFUNDED",
    name="payment_status",
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
