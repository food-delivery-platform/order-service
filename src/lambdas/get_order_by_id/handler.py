"""Lambda handler - GET /api/v1/orders/{orderId} (FDS-21)."""

from src.modules.orders.api import mappers
from src.modules.orders.service import order_read_service
from src.shared.errors.app_error import AppError
from src.shared.http import api_response


def handler(event, context=None):
    path_params = event.get("pathParameters") or {}
    order_id = path_params.get("orderId", "")
    try:
        order = order_read_service.get_order_by_id(order_id)
    except AppError as err:
        return api_response.from_app_error(err)
    return api_response.ok(mappers.to_order_response(order))
