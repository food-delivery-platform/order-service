"""Lambda handler - POST /api/v1/orders/{orderId}/cancel (cancel_order).

Stub for FDS-15. Real logic arrives in a later task.
"""
from src.shared.http import api_response

def handler(event, context=None):
    return api_response.error(501, "NOT_IMPLEMENTED", "cancel_order is not implemented yet")
