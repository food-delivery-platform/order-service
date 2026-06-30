"""Thin SNS wrapper (publishes order.* events). boto3 imported lazily."""
from src.shared.config import env

_client = None

def get_client():
    global _client
    if _client is None:
        import boto3  # lazy import
        _client = boto3.client("sns", region_name=env.AWS_REGION)
    return _client
