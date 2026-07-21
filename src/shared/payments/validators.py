"""Shared PayPal-ID format validator (FDS-27 part2).

PayPal order/capture IDs are alphanumeric tokens, e.g. ``5O190127TN364715T``.
They are NOT UUIDs — do not treat them as such.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

# PayPal order/capture IDs are alphanumeric tokens. Kept permissive
# (length 5..36, alphanumeric) so we reject junk without rejecting valid
# PayPal IDs, whose exact format PayPal does not contractually guarantee.
PaypalId = Annotated[str, Field(min_length=5, max_length=36, pattern=r"^[A-Za-z0-9]+$")]
