"""Runtime loader for AWS Secrets Manager.

Reads a JSON secret once per warm Lambda invocation and caches it.
In local dev (no SERVICE_SECRET_ARN), returns an empty dict so plain env
vars are used instead.
"""

import json
import logging
import os

import boto3

logger = logging.getLogger(__name__)

_secret_cache: dict | None = None


def get_service_secret() -> dict:
    """Return the parsed JSON secret dict, fetching + caching once per Lambda.

    Returns:
        Parsed secret as a dict.  Empty dict when SERVICE_SECRET_ARN is unset
        (local-dev / no-secret fallback).

    Raises:
        RuntimeError: the secret exists but cannot be read or parsed.
    """
    global _secret_cache

    if _secret_cache is not None:
        return _secret_cache

    secret_arn = os.environ.get("SERVICE_SECRET_ARN")
    if not secret_arn:
        logger.info("SERVICE_SECRET_ARN not set – using env-only configuration")
        _secret_cache = {}
        return _secret_cache

    try:
        aws_region = os.environ.get("AWS_REGION", "eu-west-1")
        client = boto3.client("secretsmanager", region_name=aws_region)
        response = client.get_secret_value(SecretId=secret_arn)
        secret_string = response.get("SecretString", "{}")
        _secret_cache = json.loads(secret_string)
        logger.info("Service secret loaded successfully")
        return _secret_cache
    except Exception as exc:
        logger.error("Failed to load service secret")
        raise RuntimeError("Failed to load service secret") from exc
