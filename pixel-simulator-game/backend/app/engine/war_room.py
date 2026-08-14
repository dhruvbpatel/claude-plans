"""Deterministic 6-seat war room: ownership scoring, chair synthesis, forced dissent."""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.engine.protocols import (
    WarRoomChair,
    WarRoomContext,
    WarRoomDissent,
    WarRoomResult,
    WarRoomSeatVote,
)

UP_METRICS = {
    "cash",
    "margin",
    "sharePrice",
    "revenue",
    "marketShare",
    "innovation",
    "morale",
    "reputation",
    "confidence",
}
DOWN_METRICS = {"debt", "integrationRisk", "regulatoryRisk"}


def _score(owns: set[str], card: dict[str, Any]) -> float:
    total = 0.0
    for metric, delta in (card.get("deltas") or {}).items():
        if metric not in owns:
            continue
        weight = -1.0 if metric in DOWN_METRICS else 1.0
        total += weight * float(delta)
    return total


def _ranked(owns: set[str], hand: list[dict[str, Any]]) -> list[str]:
    scored = [(_score(owns, card), i, str(card["id"])) for i, card in enumerate(hand)]
    scored.sort(key=lambda row: (-row[0], row[1]))
    return [row[2] for row in scored]


class DeterministicWarRoom:
    def __init__(self, scenario: dict[str, Any] | None = None) -> None:
        self._scenario = scenario or {}

    def convene(self, ctx: WarRoomContext) -> WarRoomResult:
        hand = [c for c in (ctx.get("hand") or []) if c.get("id")]
        ids = [str(c["id"]) for c in hand]
        first_id = ids[0] if ids else ""
        cfg_seats = list(
            ctx.get("seats")
            or (self._scenario.get("warRoom") or {}).get("seats")
            or []
        )
        if not cfg_seats:
            cfg_seats = [{"id": "cfo", "name": "CFO", "owns": []}]

        rankings: dict[str, list[str]] = {}
        seats: list[WarRoomSeatVote] = []
        for seat in cfg_seats:
            owns = set(seat.get("owns") or [])
            ranked = _ranked(owns, hand) or [first_id]
            rankings[str(seat["id"])] = ranked
            preferred = ranked[0] if ranked else first_id
            label = next((c.get("label", preferred) for c in hand if c["id"] == preferred), preferred)
            seats.append(
                {
                    "seatId": str(seat["id"]),
                    "preferredCardId": preferred,
                    "rationale": f"I back '{label}'.",
                    "concern": "",
                }
            )

        if (
            len(ids) >= 2
            and seats
            and len({s["preferredCardId"] for s in seats}) == 1
        ):
            def gap(seat_id: str) -> tuple[float, int]:
                ranked = rankings.get(seat_id) or ids
                if len(ranked) < 2:
                    return (999.0, 0)
                owns = set(
                    next(s for s in cfg_seats if str(s["id"]) == seat_id).get("owns") or []
                )
                first = next(c for c in hand if c["id"] == ranked[0])
                second = next(c for c in hand if c["id"] == ranked[1])
                return (_score(owns, first) - _score(owns, second), ids.index(ranked[0]))

            flip_id = min((s["seatId"] for s in seats), key=gap)
            ranked = rankings.get(flip_id) or ids
            second = ranked[1] if len(ranked) > 1 else ids[1]
            for seat in seats:
                if seat["seatId"] == flip_id:
                    seat["preferredCardId"] = second
                    seat["concern"] = "Forced dissent: the room cannot be unanimous."
                    seat["rationale"] = f"I dissent in favor of '{second}'."
                    break

        tally = dict(Counter(s["preferredCardId"] for s in seats if s["preferredCardId"]))
        winner = first_id
        if tally:
            best = max(tally.values())
            tied = [cid for cid, n in tally.items() if n == best]
            winner = next((cid for cid in ids if cid in tied), tied[0])
        top = tally.get(winner, 0)
        if top >= 5:
            confidence = "high"
        elif top >= 3:
            confidence = "moderate"
        else:
            confidence = "low"
        dissents: list[WarRoomDissent] = [
            {
                "seatId": s["seatId"],
                "preferredCardId": s["preferredCardId"],
                "concern": s.get("concern") or f"Prefers {s['preferredCardId']}.",
            }
            for s in seats
            if s["preferredCardId"] != winner
        ]
        chair: WarRoomChair = {
            "recommendedCardId": winner,
            "tally": tally,
            "dissents": dissents,
            "confidence": confidence,
        }
        return {"seats": seats, "chair": chair}


class SwarmWarRoom(DeterministicWarRoom):
    """Documented swarm slot. Delegates to deterministic this effort."""
