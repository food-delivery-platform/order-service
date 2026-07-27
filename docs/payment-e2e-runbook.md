# Payment End-to-End Runbook

## Purpose

This document describes how to run a full sandbox payment from session creation
to the paid record in the database, and how to diagnose the failures observed
during the first end-to-end run on 26 July 2026. Follow the steps below exactly;
each step is idempotent and safe to repeat.

## Running the Flow

1. **Create a payment session.** Invoke the `create_payment_session` Lambda
   with the payload
   `{"order_id": "<uuid>", "amount": 42.50, "currency": "USD"}`.
   The response contains `order_id`, `provider_ref` (the PayPal order id),
   and `approval_url`.

2. **Approve the payment in PayPal.** Open `approval_url` and pay with a
   PayPal sandbox buyer account. After approval PayPal redirects the browser
   to `localhost:3000` — this redirect fails unless the frontend runs locally,
   but the payment itself is unaffected.

3. **Start the payment confirmation state machine.** Start an execution of
   the `payment-confirmation-sm` state machine with the payload
   `{"event_type": "PAYMENT.CAPTURE.COMPLETED", "paypal_order_id": "<provider_ref>", "status": "COMPLETED"}`.
   Substitute `<provider_ref>` with the value from step 1. This execution is
   safe to repeat because the payment is written with an idempotency key of
   the form `paypal:<provider_ref>:<order_id>`.

4. **Verify the payment in the database.** Query the `payments` table: the
   row whose `provider_ref` matches step 1 must have `status = 'SUCCEEDED'`.

5. **Understand the step order.** The state machine executes
   `VerifyPayment` → `MarkPaymentResult` → `PublishOrderEvent` in sequence.
   The payment is recorded by `MarkPaymentResult` **before** the event is
   published. A failure in `PublishOrderEvent` still leaves the payment
   correctly marked as paid; the event can be re-published later.

## Failure Modes Observed on the First End-to-End Run

| Symptom | Where it surfaced | Root cause | Fix |
|---|---|---|---|
| `FATAL: (EAUTHQUERY) user not found in the database` | `verify_payment`, later `mark_payment_result` | The function had no `DATABASE_URL`, so the DSN was assembled from the secret parts, where the database user is stored without the `.project-ref` suffix the Supabase pooler requires | Set `DATABASE_URL`, or fix the user value in the secret |
| `PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET` must be configured | `verify_payment` | The keys exist in the secret but their values are unusable, so `_get_config` falls through to per-function environment variables, which this function did not have | Fix the values in the secret |
| `AccessDeniedException ... events:PutEvents ... no identity-based policy allows` | `publish_order_event` | The Lambda execution role lacks permission to publish to the `food-delivery-orders` event bus | Attach an IAM policy allowing `events:PutEvents` scoped to that single event bus ARN |
| Payment appears stuck although PayPal shows it as paid | State machine | The execution was never started for that `provider_ref` | Start it manually with the payload described in step 3 above |

## Configuration Model

The only environment variable a Lambda should need for secret material is
`SERVICE_SECRET_ARN`. Values are resolved at runtime through
`src/shared/config/secrets.py`. Both `paypal_client` and the database engine
read the secret first and fall back to environment variables.

Because of this design, an **empty or malformed value inside the secret is
more dangerous than a missing key**. A missing key is invisible to the
presence check, so the system falls back to the per-function environment
variable (if set). An empty or wrong value passes the presence check and
surfaces only at runtime, in whichever function lacks the fallback.

## Open Items

- Values inside the `order-service/db` secret need correcting.
- The `events:PutEvents` permission is owned by the account administrator.
- Per-function environment variables set by hand on 26 July must be removed
  only after the secret is verified working.
