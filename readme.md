# order-service

Order Service for the Food Delivery Platform.

Owns the canonical order lifecycle: creation, payment orchestration,
restaurant confirmation, delivery tracking and order status.

- Runtime: Python (AWS Lambda)
- Storage: Supabase (canonical) + DynamoDB (live status)
- Messaging: SNS FIFO (outbound) + SQS FIFO (inbound)

## Status
🚧 Work in progress — FDS-15 (project init).