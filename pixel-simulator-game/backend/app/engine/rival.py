"""Deterministic rival. Phase 1: hold off. Phase 3 fills the pressure table."""

from __future__ import annotations

from typing import Any

from app.engine.protocols import GameState, RivalResponse


class DeterministicRival:
    def __init__(self, scenario: dict[str, Any] | None = None) -> None:
        self._scenario = scenario or {}

    def respond(self, state: GameState, played_card: dict[str, Any]) -> RivalResponse:
        kpis = state.get("kpis") or {}
        pressure = float(kpis.get("rivalPressure", 0))
        cfg = self._scenario.get("rival") or {}
        return {
            "pressure": pressure,
            "attackId": None,
            "deltas": {},
            "news": str(cfg.get("holdOffNews") or "The rival watches and holds off."),
            "interrupt": False,
            "heldOff": True,
        }
