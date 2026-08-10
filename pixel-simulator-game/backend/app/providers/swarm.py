"""Swarm / line-graph debate stub (Phase 5) — TEAMMATE INTEGRATION POINT.

Teammates: implement ``SwarmDebate.stream`` to this signature (see SPEC.md §9)
and set ``DEBATE_PROVIDER=swarm``. Nothing else in the tree needs to change —
the session API, SSE pipe, and frontend already consume this shape.

Contract
--------

    async def stream(self, ctx: DebateContext) -> AsyncIterator[DebateDelta]

``ctx`` (all keys optional, see ``app/engine/protocols.py``):

    state    GameState snapshot (read-only — do NOT mutate or score from it)
    beat     current beat dict: id, n, title, situation, debateTopic,
             scriptedLines, zoneId, npcId
    options  available options: id, label, pros, cons (deltas are present but
             MUST NOT influence what your agents say — qualitative flavor only)
    npcs     valid speaker ids: ceo, cfo, gc, chair, analyst, partner

Expected mapping from line-graph orchestration events to ``DebateDelta``:

    node/agent utterance or token chunk
        -> {"speakerId": "<npc id>", "text": "<utterance or chunk>"}
    graph complete (final node drained)
        -> set {"done": True} on the last delta (optional; the session loop
           also closes the debate when the iterator is exhausted)
    internal events (routing, tool calls, scratchpads)
        -> do not emit; only player-visible dialogue goes on the wire

Hard rules:

- Scoring stays in ``ScoringEngine``. Never compute or emit KPI deltas from
  the swarm; the only KPI path is ``ScoringEngine.apply`` after the player
  decides via the session API.
- ``speakerId`` must be one of ``ctx["npcs"]`` or the frontend cannot place
  the speech bubble.

The fake stream below emits a plausible multi-agent debate so the ``swarm``
provider is playable end-to-end before the real orchestration lands. Pacing
follows ``DEBATE_DELAY_MS`` (default 600ms; 0 for headless tests).
"""

from __future__ import annotations

import asyncio
import os
from typing import AsyncIterator

from app.engine.protocols import DebateContext, DebateDelta

# (speaker, template) — templates may use {topic}, {n_options}, {first_label}.
_FAKE_SCRIPT: list[tuple[str, str]] = [
    ("partner", "Swarm sync. I want every agent's read on {topic} before we commit."),
    ("analyst", "Graph fanned out: {n_options} branches under evaluation, starting with '{first_label}'."),
    ("cfo", "Finance node keeps flagging balance-sheet strain on the aggressive branch."),
    ("gc", "Counsel node: disclosure risk propagates fast if this goes public early."),
    ("chair", "The board will not converge on anything that looks like a hostile squeeze."),
    ("ceo", "Management's position is unchanged — the plan is working. Convince the room otherwise."),
    ("partner", "Branches argued. Consensus is yours to call — we only surface the trade-offs."),
]


class SwarmDebate:
    """Fake multi-agent stream standing in for teammate line-graph orchestration.

    Replace ``stream`` (keep the signature!) with the real swarm; everything
    upstream and downstream already speaks this contract.
    """

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
        topic = beat.get("debateTopic") or beat.get("title") or "the current move"
        first_label = options[0].get("label", "?") if options else "?"

        lines: list[DebateDelta] = []
        for speaker, template in _FAKE_SCRIPT:
            if npcs and speaker not in npcs:
                continue
            lines.append(
                {
                    "speakerId": speaker,
                    "text": template.format(
                        topic=topic, n_options=len(options), first_label=first_label
                    ),
                }
            )

        for i, line in enumerate(lines):
            if i and delay:
                await asyncio.sleep(delay)
            if i == len(lines) - 1:
                line["done"] = True
            yield line
