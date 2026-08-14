"""Session lifecycle, interact/decide, and SSE event stream (Phase 4).

Phase machine per SPEC §4:
    EXPLORE -> BEAT_INTRO -> DEBATE -> AWAIT_DECISION -> APPLY
        -> EXPLORE | GAME_END

Boardroom beats (zoneId == boardroom) skip debate until after decide:
    EXPLORE -> BEAT_INTRO -> AWAIT_DECISION -> CONVENE -> DEBATE
        -> BOARD_VOTE -> APPLY -> EXPLORE | GAME_END

The curveball is beat 6 itself: its seeded variant's situation is revealed at
BEAT_INTRO and its eventDeltas are applied by the engine inside `apply`.

Sessions are in-memory. Each session owns an asyncio.Queue; the SSE endpoint
drains it, so events emitted before the client connects are buffered, not lost.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.engine.metrics import schema_version
from app.engine.board_vote import (
    create_board_vote_resolver,
    public_board_vote,
    safe_resolve,
)
from app.engine.protocols import BoardVoteResolver, DebateProvider, GameState, Option
from app.engine.scoring import LOBBY_BONUS_NEWS, MeridianScoringEngine
from app.providers.factory import create_debate_provider

SCENARIOS_DIR = Path(__file__).resolve().parents[2] / "scenarios"
DEFAULT_SCENARIO_ID = "meridian-activist-01"

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _pacing_delay() -> float:
    """Seconds between streamed events; DEBATE_DELAY_MS=0 for headless tests."""
    return max(0.0, float(os.getenv("DEBATE_DELAY_MS", "600"))) / 1000.0


def _load_scenario(scenario_id: str) -> dict[str, Any]:
    path = SCENARIOS_DIR / f"{scenario_id}.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"unknown scenario {scenario_id!r}")
    return json.loads(path.read_text())


def _is_boardroom(beat: dict[str, Any]) -> bool:
    return beat.get("zoneId") == "boardroom"


def _public_options(options: list[Option]) -> list[dict[str, Any]]:
    """Card payload for the client: label + pros/cons only, NEVER deltas."""
    return [
        {
            "id": o["id"],
            "label": o.get("label", ""),
            "pros": list(o.get("pros", [])),
            "cons": list(o.get("cons", [])),
        }
        for o in options
    ]


@dataclass
class Session:
    id: str
    engine: MeridianScoringEngine
    scenario: dict[str, Any]
    state: GameState
    provider: DebateProvider
    vote_resolver: BoardVoteResolver = field(default_factory=create_board_vote_resolver)
    phase: str = "EXPLORE"
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    beat_task: asyncio.Task | None = None
    motion_id: str | None = None

    def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        self.queue.put_nowait((event_type, payload))

    def set_phase(self, phase: str) -> None:
        self.phase = phase
        self.emit("phase", {"phase": phase})

    def current_beat(self) -> dict[str, Any] | None:
        if schema_version(self.scenario) == 2:
            if self.state.get("outcome") != "playing":
                return None
            max_q = int(self.scenario.get("maxQuarters") or 8)
            if self.state["beatIndex"] >= max_q:
                return None
            n = int(self.state["beatIndex"]) + 1
            return {
                "id": f"quarter-{n}",
                "n": n,
                "title": f"Quarter {n}",
                "zoneId": "war_room",
                "npcId": "chair",
                "situation": self.state.get("lastNews") or "The war room is waiting.",
            }
        beats = self.scenario["beats"]
        index = self.state["beatIndex"]
        return beats[index] if index < len(beats) else None

    def selected_variant(self, beat: dict[str, Any]) -> dict[str, Any] | None:
        if not beat.get("curveball"):
            return None
        variant_id = self.state.get("curveballVariantId")
        return next((v for v in beat["variants"] if v["id"] == variant_id), None)

    def next_beat_hint(self) -> dict[str, Any] | None:
        beat = self.current_beat()
        if beat is None or self.state.get("outcome") != "playing":
            return None
        return {
            "beatId": beat["id"],
            "n": beat["n"],
            "title": beat["title"],
            "zoneId": beat["zoneId"],
            "npcId": beat.get("npcId"),
        }


SESSIONS: dict[str, Session] = {}


def _get_session(session_id: str) -> Session:
    session = SESSIONS.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"unknown session {session_id!r}")
    return session


# -- request/response models ---------------------------------------------------


class CreateSessionRequest(BaseModel):
    scenarioId: str = DEFAULT_SCENARIO_ID
    seed: Optional[int] = None


class InteractRequest(BaseModel):
    targetId: str
    beatId: Optional[str] = None


class DecideRequest(BaseModel):
    optionId: str


# -- routes ---------------------------------------------------------------------


@router.post("")
async def create_session(req: CreateSessionRequest) -> dict[str, Any]:
    scenario = _load_scenario(req.scenarioId)
    seed = req.seed if req.seed is not None else random.randrange(2**31)

    engine = MeridianScoringEngine()
    state = engine.create(scenario, seed=seed)

    session = Session(
        id=str(uuid.uuid4()),
        engine=engine,
        scenario=scenario,
        state=state,
        provider=create_debate_provider(),
    )
    SESSIONS[session.id] = session

    # Buffered for the SSE client that connects right after this call.
    session.emit("phase", {"phase": session.phase})
    session.emit("kpi_patch", {"kpis": dict(state["kpis"])})
    hint = session.next_beat_hint()
    if hint:
        session.emit("next_beat", hint)

    return {
        "sessionId": session.id,
        "phase": session.phase,
        "beatIndex": state["beatIndex"],
        "kpis": dict(state["kpis"]),
        "flags": list(state["flags"]),
        "seed": seed,
        "nextBeat": hint,
    }


@router.get("/{session_id}")
async def get_session(session_id: str) -> dict[str, Any]:
    session = _get_session(session_id)
    state = session.state
    snapshot: dict[str, Any] = {
        "sessionId": session.id,
        "phase": session.phase,
        "beatIndex": state["beatIndex"],
        "kpis": dict(state["kpis"]),
        "flags": list(state["flags"]),
        "outcome": state.get("outcome", "playing"),
        "nextBeat": session.next_beat_hint(),
    }
    if session.phase == "AWAIT_DECISION":
        snapshot["options"] = _public_options(
            session.engine.available_options(state)
        )
    if session.motion_id:
        snapshot["motionId"] = session.motion_id
    return snapshot


@router.post("/{session_id}/interact")
async def interact(session_id: str, req: InteractRequest) -> dict[str, Any]:
    session = _get_session(session_id)
    beat = session.current_beat()

    if session.phase != "EXPLORE" or beat is None:
        return {"phase": session.phase, "beatId": None, "accepted": False}

    hint = session.next_beat_hint()
    triggers = {f"zone:{beat['zoneId']}"}
    if beat.get("npcId"):
        triggers.add(f"npc:{beat['npcId']}")

    # Once-per-beat lobby bonus (Phase 6): deterministic, engine-side.
    if (
        req.targetId == "zone:lobby"
        and "zone:lobby" not in triggers
        and schema_version(session.scenario) != 2
    ):
        bonus_state = session.engine.apply_lobby_bonus(session.state)
        if bonus_state is not None:
            session.state = bonus_state
            session.emit("kpi_patch", {"kpis": dict(bonus_state["kpis"])})
            session.emit("news", {"text": LOBBY_BONUS_NEWS})
        return {
            "phase": session.phase,
            "beatId": None,
            "accepted": False,
            "lobbyBonus": "granted" if bonus_state is not None else "spent",
            "nextBeat": hint,
        }

    if (req.beatId and req.beatId != beat["id"]) or req.targetId not in triggers:
        return {
            "phase": session.phase,
            "beatId": beat["id"],
            "accepted": False,
            "nextBeat": hint,
        }

    session.set_phase("BEAT_INTRO")
    session.beat_task = asyncio.create_task(_run_beat(session, beat))
    return {"phase": "BEAT_INTRO", "beatId": beat["id"], "accepted": True}


async def _run_beat(session: Session, beat: dict[str, Any]) -> None:
    """BEAT_INTRO -> DEBATE (streamed) -> AWAIT_DECISION."""
    delay = _pacing_delay()
    try:
        if schema_version(session.scenario) == 2:
            session.state = session.engine.start_quarter(session.state)
            beat = session.current_beat() or beat
            news = session.state.get("lastNews")
            if news:
                session.emit("news", {"text": news})

        variant = session.selected_variant(beat)
        situation = beat.get("situation", "")
        if variant:
            situation = f"{situation} {variant.get('situation', '')}".strip()
            session.emit("news", {"text": f"BREAKING: {variant.get('title', 'Market shock')}"})

        session.emit(
            "beat",
            {
                "beatId": beat["id"],
                "n": beat["n"],
                "title": variant.get("title", beat["title"]) if variant else beat["title"],
                "situation": situation,
                "zoneId": beat["zoneId"],
                "npcId": beat.get("npcId"),
            },
        )
        await asyncio.sleep(delay)

        options = session.engine.available_options(session.state)
        if _is_boardroom(beat):
            session.set_phase("AWAIT_DECISION")
            session.emit("options", {"options": _public_options(options)})
            return

        session.set_phase("DEBATE")
        ctx = {
            "state": session.state,
            "beat": beat,
            "options": options,
            "npcs": list(session.scenario.get("npcs", [])),
        }
        async for delta in session.provider.stream(ctx):
            session.emit(
                "debate_delta",
                {"speakerId": delta.get("speakerId", ""), "text": delta.get("text", "")},
            )
        session.emit("debate_complete", {})

        session.set_phase("AWAIT_DECISION")
        session.emit("options", {"options": _public_options(options)})
    except Exception as exc:  # noqa: BLE001 — keep the session playable
        session.set_phase("EXPLORE")
        session.emit("news", {"text": f"(beat aborted: {exc})"})


@router.post("/{session_id}/decide")
async def decide(session_id: str, req: DecideRequest) -> dict[str, Any]:
    session = _get_session(session_id)
    if session.phase != "AWAIT_DECISION":
        raise HTTPException(
            status_code=409,
            detail=f"cannot decide in phase {session.phase!r}",
        )

    beat = session.current_beat()
    if beat is not None and _is_boardroom(beat):
        return await _decide_boardroom(session, beat, req.optionId)

    try:
        new_state = session.engine.apply(session.state, req.optionId)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _finish_apply(session, new_state)


async def _decide_boardroom(
    session: Session, beat: dict[str, Any], motion_id: str
) -> dict[str, Any]:
    options = session.engine.available_options(session.state)
    if not any(o.get("id") == motion_id for o in options):
        raise HTTPException(status_code=400, detail=f"unknown option {motion_id!r}")

    session.motion_id = motion_id
    motion_label = next(o.get("label", motion_id) for o in options if o.get("id") == motion_id)

    session.set_phase("CONVENE")
    session.emit("convene", {"beatId": beat["id"], "motionId": motion_id})

    session.set_phase("DEBATE")
    ctx = {
        "state": session.state,
        "beat": beat,
        "options": options,
        "npcs": list(session.scenario.get("npcs", [])),
        "motionId": motion_id,
    }
    async for delta in session.provider.stream(ctx):
        session.emit(
            "debate_delta",
            {"speakerId": delta.get("speakerId", ""), "text": delta.get("text", "")},
        )
    session.emit("debate_complete", {})

    vote = safe_resolve(session.vote_resolver, ctx)
    session.set_phase("BOARD_VOTE")
    session.emit("board_vote", public_board_vote(vote, options, motion_id, motion_label))

    try:
        new_state = session.engine.apply(session.state, vote["winningOptionId"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    last = new_state["history"][-1]
    last["motionId"] = motion_id
    last["ballots"] = dict(vote.get("ballots") or {})
    if vote.get("tieBrokenBy"):
        last["tieBrokenBy"] = vote["tieBrokenBy"]

    session.motion_id = None
    return _finish_apply(session, new_state)


def _finish_apply(session: Session, new_state: GameState) -> dict[str, Any]:
    session.set_phase("APPLY")
    session.state = new_state
    last = new_state["history"][-1]
    consequence = last.get("consequence", "")

    session.emit("kpi_patch", {"kpis": dict(new_state["kpis"])})
    if consequence:
        session.emit("news", {"text": consequence})
    for knock in last.get("knockOns") or []:
        text = knock.get("news")
        if text:
            session.emit("news", {"text": text})
    rival_news = last.get("rivalNews")
    if rival_news:
        session.emit("news", {"text": rival_news})

    outcome = new_state.get("outcome", "playing")
    if outcome == "playing":
        session.set_phase("EXPLORE")
        hint = session.next_beat_hint()
        if hint:
            session.emit("next_beat", hint)
    else:
        session.set_phase("GAME_END")
        summary = session.engine.summary(new_state)
        session.emit(
            "game_end",
            {"outcome": outcome, "grade": summary["grade"], "summary": summary},
        )

    return {
        "phase": session.phase,
        "kpis": dict(new_state["kpis"]),
        "consequence": consequence,
        "outcome": outcome,
    }


def _format_sse(event_type: str, payload: dict[str, Any]) -> str:
    return f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"


@router.get("/{session_id}/events")
async def events(session_id: str) -> StreamingResponse:
    session = _get_session(session_id)

    async def stream():
        yield "retry: 2000\n\n"
        while True:
            try:
                event_type, payload = await asyncio.wait_for(
                    session.queue.get(), timeout=15.0
                )
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
                continue
            yield _format_sse(event_type, payload)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
