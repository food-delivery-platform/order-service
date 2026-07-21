"""Structural tests for the payment-confirmation state machine ASL (FDS-27 P2-C10 / P2-C12).

Validates that the ASL definition is well-formed and internally consistent:
all ``StartAt``, ``Next``, ``Default``, and Choice targets reference real states,
and every ``Task`` uses the expected ``function:`` placeholder Resource.
"""

from __future__ import annotations

import json
from pathlib import Path

ASL_PATH = (
    Path(__file__).parent.parent
    / "orchestration"
    / "payment-confirmation-state-machine.asl.json"
)

EXPECTED_FUNCTION_RESOURCES = {
    "function:verify_payment",
    "function:mark_payment_result",
    "function:publish_order_event",
}


def _load() -> dict:
    with open(ASL_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Test 1: valid JSON (implicitly tested by _load, but make it explicit)
# ---------------------------------------------------------------------------


def test_asl_is_valid_json():
    """The file must parse as JSON (no syntax errors)."""
    data = _load()
    assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# Test 2: StartAt references an existing state
# ---------------------------------------------------------------------------


def test_start_at_exists_in_states():
    data = _load()
    assert "StartAt" in data, "ASL must have a StartAt key"
    assert "States" in data, "ASL must have a States key"
    assert data["StartAt"] in data["States"], (
        f"StartAt '{data['StartAt']}' not found in States"
    )


# ---------------------------------------------------------------------------
# Test 3: every Next / Default / Choice target exists in States
# ---------------------------------------------------------------------------


def _collect_targets(data: dict) -> list[tuple[str, str]]:
    """Walk the ASL and collect every (state_name, target_name) pair.

    Covers:
      * ``Next``, ``Default`` on states
      * ``Next`` inside ``Catch`` blocks
      * ``Next`` inside Choice ``Choices``
    """
    targets: list[tuple[str, str]] = []
    states: dict = data.get("States", {})

    for state_name, state_def in states.items():
        # Direct Next
        if "Next" in state_def:
            targets.append((state_name, state_def["Next"]))

        # Default on Choice states
        if "Default" in state_def:
            targets.append((state_name, state_def["Default"]))

        # Next inside Catch blocks
        for catcher in state_def.get("Catch", []):
            if "Next" in catcher:
                targets.append((state_name, catcher["Next"]))

        # Next inside Choices array
        for choice in state_def.get("Choices", []):
            if "Next" in choice:
                targets.append((state_name, choice["Next"]))

    return targets


def test_all_targets_exist():
    data = _load()
    states = data.get("States", {})
    targets = _collect_targets(data)

    assert len(targets) > 0, "Expected at least one Next/Default/Choice target"

    for src, tgt in targets:
        assert tgt in states, f"'{src}' references '{tgt}' which is not in States"


# ---------------------------------------------------------------------------
# Test 4: every Task Resource is a ``function:`` placeholder
# ---------------------------------------------------------------------------


def _collect_task_resources(data: dict) -> list[str]:
    """Return every Resource value from Task states, in order."""
    resources: list[str] = []
    for state_def in data.get("States", {}).values():
        if state_def.get("Type") == "Task":
            resources.append(state_def["Resource"])
    return resources


def test_task_resources_are_function_placeholders():
    data = _load()
    resources = _collect_task_resources(data)

    assert len(resources) == 3, "Expected exactly 3 Task states"

    for resource in resources:
        # Must contain one of the expected function:<name> patterns
        matched = any(expected in resource for expected in EXPECTED_FUNCTION_RESOURCES)
        assert matched, (
            f"Resource '{resource}' does not contain any of {EXPECTED_FUNCTION_RESOURCES}"
        )
