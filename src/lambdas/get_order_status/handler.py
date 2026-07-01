"""Lambda handler - GET /api/v1/orders/{orderId}/status (get_order_status).

Stub for FDS-15. Real logic arrives in a later task.
"""

from src.shared.http import api_response


def handler(event, context=None):
    return api_response.error(
        501, "NOT_IMPLEMENTED", "get_order_status is not implemented yet"
    )
