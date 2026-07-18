"""SQLAlchemy engine and table metadata (FDS-27 R2).

Provides a lazy module-level engine (session-pooler safe via NullPool),
``MetaData``, and ``Table`` definitions for the ``payments`` schema.
"""

from __future__ import annotations

import logging
import os

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
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.pool import NullPool

from src.shared.config.secrets import get_service_secret

logger = logging.getLogger(__name__)

_engine = None
metadata = MetaData()

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
        String(50),
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
    """Build DSN from Secrets Manager first, env var second.

    Raises:
        RuntimeError: neither ``database_url`` (secret) nor
                      ``DATABASE_URL`` (env) is set.
    """
    secret = get_service_secret()
    dsn = secret.get("database_url")
    if dsn:
        return dsn
    dsn = os.environ.get("DATABASE_URL")
    if dsn:
        return dsn
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
