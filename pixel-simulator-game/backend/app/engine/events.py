"""Seeded event deck. Phase 1: first matching event. Phase 3 fills shuffle."""

from __future__ import annotations

from typing import Any

from app.engine.protocols import Event, GameState


class SeededEventDeck:
    def __init__(self, scenario: dict[str, Any] | None = None) -> None:
        self._scenario = scenario or {}

    def draw(self, state: GameState, quarter: int) -> Event:
        deck = list(self._scenario.get("eventDeck") or [])
        if not deck:
            return {"id": "quiet", "title": "Quiet quarter", "news": "", "focusMetrics": []}
        for event in deck:
            lo = int(event.get("quarterMin", 0))
            hi = int(event.get("quarterMax", 7))
            if lo <= quarter <= hi:
                return dict(event)
        return dict(deck[quarter % len(deck)])
