"""Lambda handler - GET /api/v1/orders (list the customer's orders) (FDS-21)."""

from src.modules.orders.api import mappers
from src.modules.orders.service import order_read_service
from src.shared.errors.app_error import AppError
from src.shared.http import api_response


def handler(event, context=None):
    customer_id = _extract_customer_id(event)
    try:
        orders = order_read_service.get_customer_orders(customer_id)
    except AppError as err:
        return api_response.from_app_error(err)
    return api_response.ok({"orders": [mappers.to_order_response(o) for o in orders]})


def _extract_customer_id(event) -> str:
    params = event.get("queryStringParameters") or {}
    if params.get("customerId"):
        return params["customerId"]
    claims = (event.get("requestContext") or {}).get("authorizer", {}).get("claims", {})
    return claims.get("sub", "")
