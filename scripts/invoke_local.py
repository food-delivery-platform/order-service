"""Invoke a Lambda handler locally.

Usage:
    python scripts/invoke_local.py <handler_name> [event_file.json]

Example:
    python scripts/invoke_local.py health
    python scripts/invoke_local.py create_order events/create-order.json
"""

import importlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    handler_name = sys.argv[1]
    event = {}
    if len(sys.argv) > 2:
        with open(sys.argv[2], encoding="utf-8") as fh:
            event = json.load(fh)
    module = importlib.import_module(f"src.lambdas.{handler_name}.handler")
    print(json.dumps(module.handler(event, None), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
