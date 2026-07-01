"""Lambda handler - GET /api/v1/health. Liveness probe."""

from src.shared.http import api_response


def handler(event, context=None):
    return api_response.ok({"service": "order-service", "status": "ok"})
