"""Shared input-validation decorator for Step Functions Lambda handlers (FDS-27 part2).

Wraps a Pydantic ``model_validate`` call so every SM-task handler doesn't
repeat the same try/except boilerplate.
"""

from __future__ import annotations

import functools

from pydantic import ValidationError

from src.shared.errors.app_error import AppError


def validated_input(model):
    """Validate the Lambda event against a Pydantic model.

    On success the wrapped handler receives the parsed model instead of the
    raw event. On failure raises AppError(400, "INVALID_INPUT").
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(event, context=None):
            try:
                data = model.model_validate(event)
            except ValidationError as exc:
                raise AppError(400, "INVALID_INPUT", str(exc)) from exc
            return func(data, context)

        return wrapper

    return decorator
