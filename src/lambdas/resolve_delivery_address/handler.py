"""Step Functions step — resolve / create delivery address (FDS-25).

This step runs AFTER successful cart validation and BEFORE CreateOrderStep.
It either creates a new address or verifies an existing one, ensuring
CreateOrderStep always receives a fully resolved delivery address.

The output is placed at ``$.delivery_address`` via Step Functions ResultPath,
so downstream steps see the resolved address at the same path.
"""

from __future__ import annotations

from src.modules.orders.repository import address_repository
from src.shared.errors.app_error import AppError


def handler(event, context=None):
    customer_id = event.get("customer_id")
    delivery_address = event.get("delivery_address")
    delivery_address_id = event.get("delivery_address_id")

    # --- input validation ---
    if not customer_id:
        raise AppError(400, "MISSING_CUSTOMER_ID", "customer_id is required")
    if not delivery_address:
        raise AppError(
            400,
            "MISSING_DELIVERY_ADDRESS",
            "delivery_address is required (full address object)",
        )
    required = ("street", "city", "postal_code")
    missing = [f for f in required if not delivery_address.get(f)]
    if missing:
        raise AppError(
            400,
            "INCOMPLETE_DELIVERY_ADDRESS",
            f"delivery_address missing fields: {', '.join(missing)}",
        )

    # --- create-or-verify ---
    try:
        if not delivery_address_id:
            # New address — create and link to customer.
            addr = address_repository.create_address(
                customer_id=customer_id,
                street=delivery_address["street"],
                city=delivery_address["city"],
                postal_code=delivery_address["postal_code"],
                latitude=delivery_address.get("latitude"),
                longitude=delivery_address.get("longitude"),
                notes=delivery_address.get("notes"),
            )
        else:
            # Existing address — verify it exists and belongs to customer.
            addr = address_repository.get_address(delivery_address_id)
            if addr is None:
                raise AppError(
                    404,
                    "ADDRESS_NOT_FOUND",
                    f"Address {delivery_address_id} not found",
                )
            if addr.customer_id != customer_id:
                raise AppError(
                    403,
                    "ADDRESS_FORBIDDEN",
                    f"Address {delivery_address_id} does not belong to customer {customer_id}",
                )
    except AppError:
        raise
    except Exception as exc:
        raise AppError(
            500,
            "ADDRESS_RESOLUTION_FAILED",
            f"Failed to resolve delivery address: {exc}",
        ) from exc

    # Return the resolved address — Step Functions will merge this into
    # ``$.delivery_address`` via ``ResultPath``, preserving validated_items
    # and the rest of the state.
    return {
        "address_id": addr.address_id,
        "street": addr.street,
        "city": addr.city,
        "postal_code": addr.postal_code,
        "latitude": addr.latitude,
        "longitude": addr.longitude,
        "notes": addr.notes,
    }
