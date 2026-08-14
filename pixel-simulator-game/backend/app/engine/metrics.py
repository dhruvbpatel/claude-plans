"""Config-driven metric bounds and scenario schema detection."""

from __future__ import annotations

from typing import Any

# Inclusive (min, max); None = unbounded on that side. Used when a scenario
# has no ``metrics`` array (Meridian v1).
V1_BOUNDS: dict[str, tuple[float | None, float | None]] = {
    "stockPrice": (0.0, None),
    "boardResistance": (0.0, 100.0),
    "ownershipPct": (0.0, 100.0),
    "warChest": (None, None),
    "mediaHeat": (0.0, 100.0),
}


def schema_version(scenario: dict[str, Any]) -> int:
    if scenario.get("schemaVersion") == 2 or "cards" in scenario:
        return 2
    return 1


def bounds_from_scenario(
    scenario: dict[str, Any],
) -> dict[str, tuple[float | None, float | None]]:
    metrics = scenario.get("metrics")
    if metrics:
        return {
            m["id"]: (m.get("min"), m.get("max")) for m in metrics
        }
    return dict(V1_BOUNDS)


def openings_from_scenario(scenario: dict[str, Any]) -> dict[str, float]:
    metrics = scenario.get("metrics")
    if metrics:
        return {m["id"]: float(m["opening"]) for m in metrics}
    return {k: float(v) for k, v in scenario["kpis"].items()}
