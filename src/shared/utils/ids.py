"""ID generation helpers."""
import uuid

def new_order_id() -> str:
    """Generate a new order id like 'order-1a2b3c4d5e6f'."""
    return f"order-{uuid.uuid4().hex[:12]}"
