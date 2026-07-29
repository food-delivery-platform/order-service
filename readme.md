# order-service

Order Service for the Food Delivery Platform — a set of Python AWS Lambda handlers.

## Structure
- `src/lambdas/` — Lambda entry points (one folder per handler)
- `src/shared/` — shared infra: `http`, `errors`, `config`, `aws`, `db`, `utils`
- `src/modules/` — feature modules (orders, payments, menu, events, orchestration)
- `events/` — mock API Gateway / SQS events for local testing
- `scripts/invoke_local.py` — run a handler locally

## Setup

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run a handler locally

```
python scripts/invoke_local.py get_order_by_id events/get-order-by-id.json
python scripts/invoke_local.py create_order events/create-order.json
```

## API Endpoints

Machine-readable OpenAPI spec: [`docs/openapi.yaml`](docs/openapi.yaml)
Payment end-to-end runbook: [`docs/payment-e2e-runbook.md`](docs/payment-e2e-runbook.md)

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/orders` | Create an order |
| `GET` | `/api/v1/orders` | List the current customer's orders |
| `GET` | `/api/v1/orders/{orderId}` | Get one order by id |
| `POST` | `/api/v1/orders/{orderId}/cancel` | Cancel an order |
| `GET` | `/api/v1/orders/{orderId}/status` | Get order status |
| `POST` | `/api/payment…` | Receive PayPal webhook notifications |

> **TODO:** The PayPal webhook path is the CloudFormation output `PaypalWebhookPath`
> (exact path starts with `/api/payment` — full path not yet resolved from deploy
> infrastructure).

### Step Functions steps (internal, not HTTP)

These Lambda functions are invoked by AWS Step Functions and are not exposed
as HTTP endpoints.

| State Machine | Steps (in execution order) |
|---|---|
| **order-creation** | `validate_order` → `resolve_delivery_address` → `create_order_step` → `create_payment_session` |
| **payment-confirmation** | `verify_payment` → `mark_payment_result` → `publish_order_event` |

## POST /api/v1/orders — Asynchronous order creation

The `POST /api/v1/orders` endpoint is **asynchronous**: it validates the request
envelope, starts the order-creation Step Functions state machine, and immediately
returns `202 Accepted` with an execution identifier. The actual order is created
inside the state machine (cart validation, address resolution, persistence,
payment session).

### Request

All fields below are validated with a Pydantic schema
(`src/lambdas/create_order/schema.py`). Unknown / extra fields are rejected
with a `400 INVALID_INPUT`.

| Field | Type | Required | Notes |
|---|---|---|---|
| `customer_id` | string | ✅ | |
| `restaurant_id` | string | ✅ | |
| `items` | array of objects | ✅ | At least one item; each has `menu_item_id` (string) and `quantity` (integer > 0) |
| `delivery_address` | object | ❌ | `{street, city, postal_code}` — all non-empty strings |
| `delivery_address_id` | string | ❌ | Pre-existing address identifier |

```json
{
  "customer_id": "<uuid>",
  "restaurant_id": "<uuid>",
  "items": [{"menu_item_id": "<uuid>", "quantity": 2}],
  "delivery_address": {"street": "...", "city": "...", "postal_code": "..."},
  "delivery_address_id": "<uuid>"
}
```

### Response (202 Accepted)

```json
{
  "executionId": "create-order-<uuid>",
  "executionArn": "arn:aws:states:...:execution:order-creation:create-order-<uuid>",
  "status": "PENDING"
}
```

### Notes

- The client should poll `GET /api/v1/orders` to discover the order once the
  state machine completes.
- The `executionId` in the response is the Step Functions execution name, not
  the final order ID.
- The route **currently has no authorizer** — any caller can trigger order
  creation. FDS-34 will attach a JWT authorizer.

## Notes
- Restaurant `preparing` / `ready` stages are handled on the restaurant frontend (per team decision), not in this service.
- No shared `PATCH /orders/{orderId}/status` endpoint.
