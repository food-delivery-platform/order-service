"""Sync Lambda environment variables for order-service from one place.

Makes sure every order-service lambda has the environment variables it needs
without wiping the variables it already has. This replaces manual AWS-console
edits that were lost on every deploy.

Usage:
    python scripts/sync_lambda_env.py              # sync all functions
    python scripts/sync_lambda_env.py --dry-run    # print what would change
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

import boto3

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FUNCTIONS: list[str] = [
    "validate_order",
    "resolve_delivery_address",
    "create_order_step",
    "create_payment_session",
    "paypal_webhook",
    "verify_payment",
    "mark_payment_result",
    "publish_order_event",
    "get_customer_orders",
    "get_order_by_id",
]

REQUIRED_VARS: dict[str, list[str]] = {
    "DATABASE_URL": FUNCTIONS,
    "SERVICE_SECRET_ARN": FUNCTIONS,
    "PAYPAL_CLIENT_ID": [
        "create_payment_session",
        "verify_payment",
        "paypal_webhook",
    ],
    "PAYPAL_CLIENT_SECRET": [
        "create_payment_session",
        "verify_payment",
        "paypal_webhook",
    ],
    "PAYPAL_WEBHOOK_ID": [
        "paypal_webhook",
        "verify_payment",
    ],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_values() -> tuple[dict[str, str], list[str]]:
    """Read required values from the process environment.

    Returns:
        (resolved, missing) — *resolved* maps variable name to its value;
        *missing* lists the names of variables absent from ``os.environ``.
    """
    resolved: dict[str, str] = {}
    missing: list[str] = []

    for var_name in REQUIRED_VARS:
        value = os.environ.get(var_name)
        if value is None:
            missing.append(var_name)
        else:
            resolved[var_name] = value

    return resolved, missing


def _build_required_env(
    function_name: str,
    resolved: dict[str, str],
) -> dict[str, str]:
    """Return the env vars that *function_name* needs, drawn from *resolved*.

    Only includes variables whose value was actually present in the environment.
    """
    result: dict[str, str] = {}
    for var_name, funcs in REQUIRED_VARS.items():
        if function_name in funcs and var_name in resolved:
            result[var_name] = resolved[var_name]
    return result


def _make_client(region: str) -> boto3.client:
    """Return a boto3 Lambda client for *region*."""
    return boto3.client("lambda", region_name=region)


# ---------------------------------------------------------------------------
# Core sync logic
# ---------------------------------------------------------------------------


def sync_one(
    client: boto3.client,
    function_name: str,
    required: dict[str, str],
    *,
    dry_run: bool,
) -> bool:
    """Sync one Lambda function's environment variables.

    Returns ``True`` if the function's config was already up to date.
    """
    config = client.get_function_configuration(FunctionName=function_name)
    env = config.get("Environment") or {}
    existing: dict[str, str] = dict(env.get("Variables") or {})

    # Merge required vars on top of existing, never removing existing keys.
    merged = dict(existing)
    added_names: list[str] = []
    for var_name, value in required.items():
        if var_name not in existing or existing[var_name] != value:
            merged[var_name] = value
            if var_name not in existing:
                added_names.append(var_name)

    if merged == existing:
        logger.info("%s: already up to date", function_name)
        return True

    if added_names:
        logger.info("%s: adding %s", function_name, sorted(added_names))
    else:
        changed = sorted(
            k for k in required if k in existing and existing[k] != required[k]
        )
        logger.info("%s: updating %s", function_name, changed)

    if dry_run:
        logger.info(
            "%s: (dry-run) would update %d env var(s)",
            function_name,
            len(required),
        )
        return False

    client.update_function_configuration(
        FunctionName=function_name,
        Environment={"Variables": merged},
    )
    logger.info("%s: updated", function_name)
    return False


def sync_all(
    client: boto3.client,
    resolved: dict[str, str],
    *,
    dry_run: bool,
) -> tuple[int, int]:
    """Sync all functions. Returns ``(updated_count, already_correct_count)``."""
    updated = 0
    correct = 0

    for function_name in FUNCTIONS:
        required = _build_required_env(function_name, resolved)
        if sync_one(client, function_name, required, dry_run=dry_run):
            correct += 1
        else:
            updated += 1

    return updated, correct


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync Lambda environment variables for order-service.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would change without making AWS calls that modify anything.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )

    resolved, missing = _resolve_values()

    region = os.environ.get("AWS_REGION", "us-east-1")
    client = _make_client(region)

    updated, correct = sync_all(client, resolved, dry_run=args.dry_run)

    # Final summary goes to stdout (print, not logging).
    print(f"\nSummary: {updated} updated, {correct} already correct")
    if missing:
        print(f"Missing from environment: {', '.join(sorted(missing))}")
        sys.exit(1)


if __name__ == "__main__":
    main()
