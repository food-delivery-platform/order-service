"""Lambda handler - GET /api/v1/orders/{orderId} (get_order_by_id).

Stub for FDS-15. Real logic arrives in a later task.
"""
from src.shared.http import api_response

def handler(event, context=None):
    return api_response.error(501, "NOT_IMPLEMENTED", "get_order_by_id is not implemented yet")
