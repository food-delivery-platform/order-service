"""Hermetic unit tests for scripts/sync_lambda_env.py (FDS-39).

All boto3 calls are stubbed — no real AWS requests.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Make scripts/ importable (it has no __init__.py)
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent / "scripts")
sys.path.insert(0, _SCRIPTS_DIR)
import sync_lambda_env  # noqa: E402

# Restore sys.path to avoid accidental side-effects in other tests.
sys.path.pop(0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_client() -> MagicMock:
    """Return a MagicMock that behaves like a boto3 Lambda client."""
    client = MagicMock()
    return client


# ---------------------------------------------------------------------------
# Test 1: missing DATABASE_URL gets added, existing unrelated vars preserved
# ---------------------------------------------------------------------------


def test_adds_missing_database_url_preserves_existing():
    """A function missing DATABASE_URL gets it added and keeps unrelated vars."""
    client = _make_mock_client()
    client.get_function_configuration.return_value = {
        "Environment": {
            "Variables": {
                "CUSTOM_FLAG": "enabled",
                "LOG_LEVEL": "debug",
            }
        }
    }

    required = {"DATABASE_URL": "postgres://test-db:5432/orders"}
    result = sync_lambda_env.sync_one(
        client, "validate_order", required, dry_run=False
    )

    assert result is False  # was updated
    client.update_function_configuration.assert_called_once_with(
        FunctionName="validate_order",
        Environment={
            "Variables": {
                "CUSTOM_FLAG": "enabled",
                "LOG_LEVEL": "debug",
                "DATABASE_URL": "postgres://test-db:5432/orders",
            }
        },
    )


# ---------------------------------------------------------------------------
# Test 2: already has every required variable → no update call
# ---------------------------------------------------------------------------


def test_already_up_to_date_no_update_call():
    """A function that already has every required var makes no update call."""
    client = _make_mock_client()
    client.get_function_configuration.return_value = {
        "Environment": {
            "Variables": {
                "DATABASE_URL": "postgres://test-db:5432/orders",
                "SERVICE_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123:secret:x",
            }
        }
    }

    required = {
        "DATABASE_URL": "postgres://test-db:5432/orders",
        "SERVICE_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123:secret:x",
    }
    result = sync_lambda_env.sync_one(
        client, "validate_order", required, dry_run=False
    )

    assert result is True  # already up to date
    client.update_function_configuration.assert_not_called()


# ---------------------------------------------------------------------------
# Test 3: missing env var → reported, exit code 1, others still processed
# ---------------------------------------------------------------------------


def test_missing_env_var_exit_code_1_others_processed():
    """Required value missing from env → exit 1, all functions still processed."""
    mock_client = _make_mock_client()
    mock_client.get_function_configuration.return_value = {}

    # Only set the vars that ALL functions need; omit PAYPAL_CLIENT_ID.
    test_env = {
        "DATABASE_URL": "postgres://test-db:5432/orders",
        "SERVICE_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123:secret:x",
        "AWS_REGION": "us-east-1",
    }

    with patch.dict(os.environ, test_env, clear=True):
        with patch(
            "sync_lambda_env.boto3.client", return_value=mock_client
        ):
            with patch.object(sys, "argv", ["sync_lambda_env.py"]):
                with pytest.raises(SystemExit) as exc_info:
                    sync_lambda_env.main()

    assert exc_info.value.code == 1

    # All 10 functions were still processed.
    assert mock_client.get_function_configuration.call_count == len(
        sync_lambda_env.FUNCTIONS
    )
    # At least one update happened (DATABASE_URL / SERVICE_SECRET_ARN).
    assert mock_client.update_function_configuration.call_count > 0


# ---------------------------------------------------------------------------
# Test 4: --dry-run makes no update_function_configuration call
# ---------------------------------------------------------------------------


def test_dry_run_no_update_call():
    """--dry-run prints what would change but makes no AWS modify call."""
    client = _make_mock_client()
    client.get_function_configuration.return_value = {
        "Environment": {
            "Variables": {
                "EXISTING_FLAG": "yes",
            }
        }
    }

    required = {"DATABASE_URL": "postgres://test-db:5432/orders"}
    result = sync_lambda_env.sync_one(
        client, "validate_order", required, dry_run=True
    )

    assert result is False  # would have been updated
    # get was called (read-only), update was NOT called.
    client.get_function_configuration.assert_called_once_with(
        FunctionName="validate_order"
    )
    client.update_function_configuration.assert_not_called()
