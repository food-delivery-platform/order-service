"""Thin DynamoDB wrapper (live order status). boto3 imported lazily."""
from src.shared.config import env

_table = None

def get_table():
    """Return the DynamoDB table resource for live order status."""
    global _table
    if _table is None:
        import boto3  # lazy import
        _table = boto3.resource("dynamodb", region_name=env.AWS_REGION).Table(
            env.ORDER_STATUS_TABLE_NAME
        )
    return _table
