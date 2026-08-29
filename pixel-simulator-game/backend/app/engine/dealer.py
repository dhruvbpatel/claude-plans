"""Seeded card dealer. Phase 1 stub: first N eligible ids. Phase 2 fills weighting."""

from __future__ import annotations

from typing import Any

from app.engine.protocols import GameState, QuarterContext


class SeededCardDealer:
    def __init__(self, scenario: dict[str, Any] | None = None) -> None:
        self._scenario = scenario or {}

    def deal(self, state: GameState, quarter_ctx: QuarterContext) -> list[str]:
        cards = list(self._scenario.get("cards") or quarter_ctx.get("cards") or [])
        flags = set(state.get("flags") or [])
        played = set(state.get("playedCardIds") or [])
        eligible = [
            c["id"]
            for c in cards
            if c.get("id")
            and set(c.get("requires") or []) <= flags
            and not (c.get("once") and c["id"] in played)
        ]
        n = 4 if quarter_ctx.get("interrupt") else 3
        extra = quarter_ctx.get("interruptCardId")
        hand = eligible[:n]
        if extra and extra in eligible and extra not in hand:
            if len(hand) < n:
                hand.append(extra)
            else:
                hand[-1] = extra
        return hand
