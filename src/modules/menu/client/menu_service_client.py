"""HTTP client for Menu Service cart validation (FDS-21).

Order Service does not duplicate Menu Service validation logic; it only
sends the cart and consumes the validation response.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import asdict

from src.modules.menu.model.menu_validation import (
    MenuValidationRequest,
    MenuValidationResult,
    ValidatedMenuItem,
)
from src.shared.config import env
from src.shared.errors.app_error import AppError

_VALIDATE_CART_PATH = "/api/v1/cart/validate"


def validate_cart(request: MenuValidationRequest) -> MenuValidationResult:
    """Call Menu Service to validate a cart and return its response."""
    base_url = env.MENU_SERVICE_BASE_URL
    if not base_url:
        raise AppError(
            500, "MENU_SERVICE_NOT_CONFIGURED", "MENU_SERVICE_BASE_URL is not set"
        )

    url = base_url.rstrip("/") + _VALIDATE_CART_PATH
    body = json.dumps(asdict(request)).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if env.INTERNAL_SERVICE_JWT:
        headers["Authorization"] = f"Bearer {env.INTERNAL_SERVICE_JWT}"

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise AppError(
            502, "MENU_SERVICE_ERROR", f"Menu Service returned HTTP {exc.code}"
        ) from exc
    except urllib.error.URLError as exc:
        raise AppError(
            502, "MENU_SERVICE_UNAVAILABLE", "Menu Service is unreachable"
        ) from exc

    return _to_result(payload)


def _to_result(payload: dict) -> MenuValidationResult:
    items = [
        ValidatedMenuItem(
            menu_item_id=item["menu_item_id"],
            name=item["name"],
            unit_price=float(item["unit_price"]),
            available=bool(item["available"]),
        )
        for item in payload.get("items", [])
    ]
    return MenuValidationResult(
        valid=bool(payload.get("valid", False)),
        items=items,
        errors=list(payload.get("errors", [])),
    )
