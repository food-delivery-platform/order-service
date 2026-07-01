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
python scripts/invoke_local.py health
python scripts/invoke_local.py create_order events/create-order.json
```

## Notes
- Restaurant `preparing` / `ready` stages are handled on the restaurant frontend (per team decision), not in this service.
- No shared `PATCH /orders/{orderId}/status` endpoint.
