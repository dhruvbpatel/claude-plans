"""Seeded situation-weighted card dealer (spec §8.2)."""

from __future__ import annotations

import random
from typing import Any

from app.engine.protocols import GameState, QuarterContext


class SeededCardDealer:
    def __init__(self, scenario: dict[str, Any] | None = None) -> None:
        self._scenario = scenario or {}

    def deal(self, state: GameState, quarter_ctx: QuarterContext) -> list[str]:
        cards = list(self._scenario.get("cards") or quarter_ctx.get("cards") or [])
        flags = set(state.get("flags") or [])
        played_ids = set(state.get("playedCardIds") or [])
        played_families = set(state.get("playedFamilies") or [])
        quarter = int(quarter_ctx.get("quarter") or 0)
        rng = random.Random(int(state.get("seed") or 0) * 1009 + quarter + 17)
        focus = set(quarter_ctx.get("focusMetrics") or [])

        def eligible(card: dict[str, Any]) -> bool:
            if not card.get("id"):
                return False
            if card.get("once") and card["id"] in played_ids:
                return False
            return set(card.get("requires") or []) <= flags

        pool = [c for c in cards if eligible(c)]

        def weight(card: dict[str, Any]) -> int:
            keys = set((card.get("deltas") or {}).keys())
            return 3 if keys & focus else 1

        hand: list[str] = []
        unused_fams = sorted(
            {c.get("family") for c in pool if c.get("family") and c["family"] not in played_families}
        )
        if unused_fams:
            fam = rng.choice(unused_fams)
            fam_cards = [c for c in pool if c.get("family") == fam]
            if fam_cards:
                hand.append(rng.choice(fam_cards)["id"])

        def remaining() -> list[dict[str, Any]]:
            held = set(hand)
            return [c for c in pool if c["id"] not in held]

        while len(hand) < 3:
            left = remaining()
            if not left:
                break
            weights = [weight(c) for c in left]
            pick = rng.choices(left, weights=weights, k=1)[0]
            hand.append(pick["id"])

        if quarter_ctx.get("interrupt"):
            extra = quarter_ctx.get("interruptCardId")
            left = remaining()
            if extra and extra not in hand and any(c["id"] == extra for c in pool):
                hand.append(str(extra))
            elif left:
                weights = [weight(c) for c in left]
                hand.append(rng.choices(left, weights=weights, k=1)[0]["id"])

        return hand
