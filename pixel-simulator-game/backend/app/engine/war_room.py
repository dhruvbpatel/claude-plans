"""Deterministic war room. Phase 1 stub: first-card pick. Phase 4 fills seats."""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.engine.protocols import (
    GameState,
    WarRoomChair,
    WarRoomContext,
    WarRoomResult,
    WarRoomSeatVote,
)


class DeterministicWarRoom:
    def __init__(self, scenario: dict[str, Any] | None = None) -> None:
        self._scenario = scenario or {}

    def convene(self, ctx: WarRoomContext) -> WarRoomResult:
        hand = list(ctx.get("hand") or [])
        first_id = str(hand[0]["id"]) if hand and hand[0].get("id") else ""
        cfg_seats = list(
            (ctx.get("seats") or (self._scenario.get("warRoom") or {}).get("seats") or [])
        )
        if not cfg_seats:
            cfg_seats = [{"id": "cfo", "name": "CFO", "owns": []}]
        seats: list[WarRoomSeatVote] = []
        for seat in cfg_seats:
            seats.append(
                {
                    "seatId": str(seat["id"]),
                    "preferredCardId": first_id,
                    "rationale": "Phase 1 stub: first card in the hand.",
                    "concern": "",
                }
            )
        tally = dict(Counter(s["preferredCardId"] for s in seats if s["preferredCardId"]))
        chair: WarRoomChair = {
            "recommendedCardId": first_id,
            "tally": tally,
            "dissents": [],
            "confidence": "low",
        }
        return {"seats": seats, "chair": chair}
