"""Lambda handler - POST /api/v1/orders (create_order).

Stub for FDS-15. Real logic arrives in a later task.
"""
from src.shared.http import api_response

def handler(event, context=None):
    return api_response.error(501, "NOT_IMPLEMENTED", "create_order is not implemented yet")
