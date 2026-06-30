"""Lambda handler - GET /api/v1/customers/{customerId}/orders (get_customer_orders).

Stub for FDS-15. Real logic arrives in a later task.
"""
from src.shared.http import api_response

def handler(event, context=None):
    return api_response.error(501, "NOT_IMPLEMENTED", "get_customer_orders is not implemented yet")
