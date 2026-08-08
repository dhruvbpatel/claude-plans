"""Deterministic / scripted debate provider (Phase 4).

Streams the beat's authored ``scriptedLines`` followed by generated argument
lines: for each available option an "ally" NPC makes the case using the
option's ``pros`` and a "skeptic" NPC pushes back with its ``cons``.
Qualitative pros/cons only — raw KPI deltas never reach the debate.

Pacing between lines comes from ``DEBATE_DELAY_MS`` (default 600ms);
set it to 0 for headless runs and tests.
"""

from __future__ import annotations

import asyncio
import os
from itertools import cycle
from typing import AsyncIterator

from app.engine.protocols import DebateContext, DebateDelta

# Your side of the table argues the upside; the company side argues the risk.
ALLY_IDS = ("analyst", "partner")
SKEPTIC_IDS = ("gc", "chair", "cfo", "ceo")


def _pick(pool: tuple[str, ...], available: list[str]) -> list[str]:
    picked = [npc for npc in pool if npc in available]
    return picked or available or ["analyst"]


def _sentence(parts: list[str]) -> str:
    text = ". ".join(p.rstrip(".") for p in parts if p)
    return f"{text}." if text else ""


class DeterministicDebate:
    def __init__(self, delay_ms: float | None = None) -> None:
        self._delay_ms = delay_ms

    async def stream(self, ctx: DebateContext) -> AsyncIterator[DebateDelta]:
        delay_ms = (
            self._delay_ms
            if self._delay_ms is not None
            else float(os.getenv("DEBATE_DELAY_MS", "600"))
        )
        delay = max(0.0, delay_ms) / 1000.0

        beat = ctx.get("beat", {})
        options = ctx.get("options", [])
        npcs = list(ctx.get("npcs", []))

        lines: list[DebateDelta] = [
            {"speakerId": line["speakerId"], "text": line["text"]}
            for line in beat.get("scriptedLines", [])
        ]

        allies = cycle(_pick(ALLY_IDS, npcs))
        skeptics = cycle(_pick(SKEPTIC_IDS, npcs))
        for option in options:
            label = option.get("label", option.get("id", "?"))
            pros = _sentence(list(option.get("pros", [])))
            cons = _sentence(list(option.get("cons", [])))
            if pros:
                lines.append(
                    {"speakerId": next(allies), "text": f"Case for '{label}': {pros}"}
                )
            if cons:
                lines.append(
                    {"speakerId": next(skeptics), "text": f"Against '{label}': {cons}"}
                )

        for i, line in enumerate(lines):
            if i and delay:
                await asyncio.sleep(delay)
            if i == len(lines) - 1:
                line["done"] = True
            yield line
