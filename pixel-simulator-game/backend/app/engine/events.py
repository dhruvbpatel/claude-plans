"""Seeded event deck. Shuffle at seed; assign one unused event per quarter."""

from __future__ import annotations

import random
from typing import Any

from app.engine.protocols import Event, GameState


class SeededEventDeck:
    def __init__(self, scenario: dict[str, Any] | None = None) -> None:
        self._scenario = scenario or {}

    def _assigned(self, seed: int) -> dict[int, Event]:
        deck = list(self._scenario.get("eventDeck") or [])
        rng = random.Random(seed + 3)
        rng.shuffle(deck)
        used: set[str] = set()
        assigned: dict[int, Event] = {}
        for quarter in range(8):
            for event in deck:
                eid = str(event.get("id") or "")
                if eid in used:
                    continue
                lo = int(event.get("quarterMin", 0))
                hi = int(event.get("quarterMax", 7))
                if lo <= quarter <= hi:
                    assigned[quarter] = dict(event)
                    used.add(eid)
                    break
        return assigned

    def draw(self, state: GameState, quarter: int) -> Event:
        assigned = self._assigned(int(state.get("seed") or 0))
        event = assigned.get(int(quarter))
        if event:
            return dict(event)
        return {
            "id": "quiet",
            "title": "Quiet quarter",
            "news": "",
            "focusMetrics": [],
        }
