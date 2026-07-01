"""Lambda handler - SQS consumer for inbound payment/delivery events.

Stub for FDS-15. Event routing logic arrives in a later task.
"""


def handler(event, context=None):
    records = event.get("Records", [])
    print(f"Received {len(records)} inbound event record(s)")
    return {"processed": len(records)}
