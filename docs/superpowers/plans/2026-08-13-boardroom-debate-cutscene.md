# Boardroom Debate Cutscene Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On boardroom beats (zoneId `boardroom`), the player submits a motion first, agents sit at the table and speak one keypress at a time, the board’s authored vote applies scoring, then agents walk back to their desks.

**Architecture:** `ScoringEngine.apply` stays unchanged. A new `BoardVoteResolver` plugin picks the winning option id. Session API branches on `beat["zoneId"] == "boardroom"`: cards before debate, `decide` stores `motionId`, streams debate, resolves the vote, then `apply(winner)`. Phaser gathers/dismisses from seat data in `officeMap.ts` and key-gates buffered lines. React shows a label-only vote overlay.

**Tech Stack:** FastAPI + pytest (backend), Phaser 3 + React + TypeScript (frontend), existing SSE/event bus.

**Spec:** `docs/superpowers/specs/2026-08-13-boardroom-debate-cutscene-design.md`

## Global Constraints

- Boardroom detection is `beat["zoneId"] == "boardroom"` — never hard-code beat-4/7/9 ids in runtime code.
- `ScoringEngine.apply` signature and KPI math do not change.
- Cards, bubbles, and the vote overlay never include raw deltas.
- Voters are only `chair`, `ceo`, `cfo`, `gc`. Analyst and partner speak, do not vote.
- Authored ballots: beat-4 `chair/ceo/gc=4b, cfo=4a`; beat-7 `chair/ceo/cfo=7a, gc=7b`; beat-9 all `9c`.
- Tie (2–2 or 1–1–1–1) → Chair’s remaining ballot, `tieBrokenBy == "chair"`.
- `BOARD_VOTE_RESOLVER` default `authored`; unknown → authored; non-authored failure falls back to authored once; authored failure → first available option.
- Non-boardroom loop unchanged: interact → debate → cards → `apply(player pick)`.
- No skip-all, no second Phaser scene, no delta retune.
- Workdir for backend commands: `pixel-simulator-game/backend`. Frontend: `pixel-simulator-game/frontend`.
- Tests: `DEBATE_DELAY_MS=0` already set in `tests/test_api.py`.

## File map

| File | Responsibility |
|------|----------------|
| `pixel-simulator-game/backend/app/engine/protocols.py` | `motionId` on `DebateContext`; `BoardVote`, `BoardVoteResolver` |
| `pixel-simulator-game/backend/app/engine/board_vote.py` | Authored resolver, majority, factory, SSE payload helper |
| `pixel-simulator-game/backend/tests/test_board_vote.py` | Unit tests for resolver + factory |
| `pixel-simulator-game/backend/scenarios/meridian-activist-01.json` | `boardVote` on boardroom beats |
| `pixel-simulator-game/backend/tests/test_scenario.py` | Schema for `boardVote` |
| `pixel-simulator-game/backend/app/api/sessions.py` | Boardroom phase branch |
| `pixel-simulator-game/backend/app/providers/deterministic.py` | Chair motion preface |
| `pixel-simulator-game/backend/tests/test_api.py` | Boardroom event order + history |
| `pixel-simulator-game/backend/tests/test_providers.py` | Motion preface line |
| `pixel-simulator-game/frontend/src/game/officeMap.ts` | `BOARD_SEATS`, camera target |
| `pixel-simulator-game/frontend/src/game/OfficeScene.ts` | Convene, key-gate, dismiss |
| `pixel-simulator-game/frontend/src/game/eventBus.ts` | `CONVENE`, `BOARD_VOTE` |
| `pixel-simulator-game/frontend/src/net/session.ts` | Forward new SSE events |
| `pixel-simulator-game/frontend/src/ui/BoardVoteOverlay.tsx` | Vote recap |
| `pixel-simulator-game/frontend/src/App.tsx` / `App.css` | Mount overlay + styles |
| `pixel-simulator-game/SPEC.md` | Phases + events |

---

### Task 1: Board vote resolver

**Files:**
- Create: `pixel-simulator-game/backend/app/engine/board_vote.py`
- Modify: `pixel-simulator-game/backend/app/engine/protocols.py`
- Test: `pixel-simulator-game/backend/tests/test_board_vote.py`

**Interfaces:**
- Consumes: `DebateContext` (existing); `available` options as `list[dict]` with `id` / `label`
- Produces: `BoardVote` TypedDict; `AuthoredBoardVote.resolve(ctx) -> BoardVote`; `create_board_vote_resolver(name: str | None = None) -> BoardVoteResolver`; `safe_resolve(resolver, ctx) -> BoardVote`; `public_board_vote(vote, options, motion_id, motion_label) -> dict`

- [ ] **Step 1: Write the failing tests**

Create `pixel-simulator-game/backend/tests/test_board_vote.py`:

```python
"""Authored board-vote resolver: majority, ties, gates, factory fallback."""

from __future__ import annotations

import pytest

from app.engine.board_vote import (
    AuthoredBoardVote,
    create_board_vote_resolver,
    public_board_vote,
    safe_resolve,
)


def _ctx(ballots: dict[str, str], options: list[dict], motion_id: str = "4a") -> dict:
    return {
        "motionId": motion_id,
        "options": options,
        "beat": {
            "id": "beat-4",
            "zoneId": "boardroom",
            "boardVote": {
                "voters": ["chair", "ceo", "cfo", "gc"],
                "ballots": ballots,
            },
        },
    }


OPTS = [
    {"id": "4a", "label": "Demand two board seats"},
    {"id": "4b", "label": "Demand a formal strategic review"},
    {"id": "4c", "label": "Demand both seats and a review"},
]


def test_majority_3_1():
    vote = AuthoredBoardVote().resolve(
        _ctx({"chair": "4b", "ceo": "4b", "cfo": "4a", "gc": "4b"}, OPTS)
    )
    assert vote["winningOptionId"] == "4b"
    assert vote["ballots"] == {"chair": "4b", "ceo": "4b", "cfo": "4a", "gc": "4b"}
    assert not vote.get("tieBrokenBy")


def test_tie_2_2_chair_breaks():
    vote = AuthoredBoardVote().resolve(
        _ctx({"chair": "4b", "ceo": "4b", "cfo": "4a", "gc": "4a"}, OPTS)
    )
    assert vote["winningOptionId"] == "4b"
    assert vote["tieBrokenBy"] == "chair"


def test_tie_1_1_1_1_chair_breaks():
    opts = OPTS + [{"id": "4d", "label": "Pass"}]
    vote = AuthoredBoardVote().resolve(
        _ctx({"chair": "4a", "ceo": "4b", "cfo": "4c", "gc": "4d"}, opts)
    )
    assert vote["winningOptionId"] == "4a"
    assert vote["tieBrokenBy"] == "chair"


def test_gated_ballot_dropped():
    available = [OPTS[0], OPTS[1]]  # 4c gated out
    vote = AuthoredBoardVote().resolve(
        _ctx({"chair": "4c", "ceo": "4b", "cfo": "4b", "gc": "4a"}, available)
    )
    assert "chair" not in vote["ballots"]
    assert vote["winningOptionId"] == "4b"
    assert not vote.get("tieBrokenBy")


def test_all_ballots_invalid_uses_first_available():
    vote = AuthoredBoardVote().resolve(
        _ctx({"chair": "nope", "ceo": "nope", "cfo": "nope", "gc": "nope"}, OPTS)
    )
    assert vote["winningOptionId"] == "4a"
    assert vote["ballots"] == {}
    assert not vote.get("tieBrokenBy")


def test_factory_unknown_name_returns_authored(monkeypatch):
    monkeypatch.setenv("BOARD_VOTE_RESOLVER", "not-a-real-resolver")
    resolver = create_board_vote_resolver()
    assert isinstance(resolver, AuthoredBoardVote)


def test_safe_resolve_falls_back_when_resolver_raises():
    class Boom:
        def resolve(self, ctx):
            raise RuntimeError("agentic down")

    vote = safe_resolve(Boom(), _ctx({"chair": "4b", "ceo": "4b", "cfo": "4a", "gc": "4b"}, OPTS))
    assert vote["winningOptionId"] == "4b"


def test_public_payload_has_labels_no_deltas():
    vote = AuthoredBoardVote().resolve(
        _ctx({"chair": "4b", "ceo": "4b", "cfo": "4a", "gc": "4b"}, OPTS)
    )
    payload = public_board_vote(vote, OPTS, "4a", "Demand two board seats")
    assert payload["motionId"] == "4a"
    assert payload["motionLabel"] == "Demand two board seats"
    assert payload["winningOptionId"] == "4b"
    assert payload["winningLabel"] == "Demand a formal strategic review"
    assert "deltas" not in payload
    names = {row["speakerId"]: row["name"] for row in payload["votes"]}
    assert names["gc"] == "General Counsel"
    assert names["chair"] == "Independent Chair"
    for row in payload["votes"]:
        assert "deltas" not in row
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pixel-simulator-game/backend && python -m pytest tests/test_board_vote.py -v`

Expected: FAIL with `ModuleNotFoundError: app.engine.board_vote` (or import error).

- [ ] **Step 3: Add protocol types**

In `pixel-simulator-game/backend/app/engine/protocols.py`, extend `DebateContext` and append:

```python
class DebateContext(TypedDict, total=False):
    state: GameState
    beat: dict[str, Any]
    options: list[Option]
    npcs: list[str]
    motionId: str


class BoardVote(TypedDict, total=False):
    ballots: dict[str, str]
    winningOptionId: str
    tieBrokenBy: str


class BoardVoteResolver(Protocol):
    def resolve(self, ctx: DebateContext) -> BoardVote: ...
```

- [ ] **Step 4: Implement resolver**

Create `pixel-simulator-game/backend/app/engine/board_vote.py`:

```python
"""Pluggable board-vote resolution. Authored majority for this ship.

BOARD_VOTE_RESOLVER=authored (default). Unknown names fall back to authored.
safe_resolve() catches a non-authored resolver failure and retries authored
once. If authored cannot pick a valid winner, use the first available option.
"""

from __future__ import annotations

import logging
import os
from collections import Counter
from typing import Any

from app.engine.protocols import BoardVote, BoardVoteResolver, DebateContext

logger = logging.getLogger(__name__)

DEFAULT_RESOLVER = "authored"
VOTERS = ("chair", "ceo", "cfo", "gc")
VOTER_NAMES = {
    "ceo": "CEO",
    "cfo": "CFO",
    "gc": "General Counsel",
    "chair": "Independent Chair",
}


def _option_ids(ctx: DebateContext) -> list[str]:
    return [str(o.get("id")) for o in ctx.get("options", []) if o.get("id")]


def _label(options: list[dict[str, Any]], option_id: str) -> str:
    for option in options:
        if option.get("id") == option_id:
            return str(option.get("label", option_id))
    return option_id


class AuthoredBoardVote:
    def resolve(self, ctx: DebateContext) -> BoardVote:
        available = _option_ids(ctx)
        raw = (ctx.get("beat") or {}).get("boardVote") or {}
        authored = dict(raw.get("ballots") or {})
        ballots = {
            voter: authored[voter]
            for voter in raw.get("voters", list(VOTERS))
            if voter in authored and authored[voter] in available
        }
        if not available:
            return {"ballots": {}, "winningOptionId": ""}
        if not ballots:
            return {"ballots": {}, "winningOptionId": available[0]}

        counts = Counter(ballots.values())
        top = counts.most_common()
        best_n = top[0][1]
        tied = [opt for opt, n in top if n == best_n]
        result: BoardVote = {"ballots": ballots, "winningOptionId": tied[0]}
        if len(tied) > 1:
            chair_pick = ballots.get("chair")
            if chair_pick in tied:
                result["winningOptionId"] = chair_pick
                result["tieBrokenBy"] = "chair"
            else:
                result["winningOptionId"] = available[0]
                result.pop("tieBrokenBy", None)
        return result


_RESOLVERS: dict[str, type] = {"authored": AuthoredBoardVote}


def create_board_vote_resolver(name: str | None = None) -> BoardVoteResolver:
    key = (name or os.getenv("BOARD_VOTE_RESOLVER", DEFAULT_RESOLVER)).strip().lower()
    cls = _RESOLVERS.get(key)
    if cls is None:
        logger.warning(
            "unknown BOARD_VOTE_RESOLVER=%r; falling back to %r", key, DEFAULT_RESOLVER
        )
        cls = _RESOLVERS[DEFAULT_RESOLVER]
    return cls()


def safe_resolve(resolver: BoardVoteResolver, ctx: DebateContext) -> BoardVote:
    available = _option_ids(ctx)
    fallback_id = available[0] if available else ""

    def _valid(vote: BoardVote) -> bool:
        return bool(vote.get("winningOptionId")) and vote["winningOptionId"] in available

    try:
        vote = resolver.resolve(ctx)
        if _valid(vote):
            return vote
        logger.warning("board vote resolver returned invalid winner %r", vote)
    except Exception:
        logger.warning("board vote resolver failed", exc_info=True)

    if not isinstance(resolver, AuthoredBoardVote):
        authored = AuthoredBoardVote().resolve(ctx)
        if _valid(authored):
            return authored
    return {"ballots": {}, "winningOptionId": fallback_id}


def public_board_vote(
    vote: BoardVote,
    options: list[dict[str, Any]],
    motion_id: str,
    motion_label: str,
) -> dict[str, Any]:
    ballots = vote.get("ballots") or {}
    winner = vote.get("winningOptionId", "")
    payload: dict[str, Any] = {
        "motionId": motion_id,
        "motionLabel": motion_label,
        "votes": [
            {
                "speakerId": voter,
                "name": VOTER_NAMES.get(voter, voter),
                "optionId": option_id,
                "label": _label(options, option_id),
            }
            for voter, option_id in ballots.items()
        ],
        "winningOptionId": winner,
        "winningLabel": _label(options, winner),
    }
    if vote.get("tieBrokenBy"):
        payload["tieBrokenBy"] = vote["tieBrokenBy"]
    return payload
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd pixel-simulator-game/backend && python -m pytest tests/test_board_vote.py -v`

Expected: 8 passed.

- [ ] **Step 6: Commit**

```bash
git add pixel-simulator-game/backend/app/engine/protocols.py \
        pixel-simulator-game/backend/app/engine/board_vote.py \
        pixel-simulator-game/backend/tests/test_board_vote.py
git commit -m "Add pluggable authored board-vote resolver."
```

---

### Task 2: Scenario ballots

**Files:**
- Modify: `pixel-simulator-game/backend/scenarios/meridian-activist-01.json` (beats 4, 7, 9)
- Modify: `pixel-simulator-game/backend/tests/test_scenario.py`

**Interfaces:**
- Consumes: option ids already on those beats
- Produces: each boardroom beat has `boardVote.voters` and `boardVote.ballots`

- [ ] **Step 1: Write the failing schema test**

Append to `pixel-simulator-game/backend/tests/test_scenario.py`:

```python
VOTERS = ("chair", "ceo", "cfo", "gc")


def test_boardroom_beats_have_authored_ballots(scenario):
    expected = {
        "beat-4": {"chair": "4b", "ceo": "4b", "cfo": "4a", "gc": "4b"},
        "beat-7": {"chair": "7a", "ceo": "7a", "cfo": "7a", "gc": "7b"},
        "beat-9": {"chair": "9c", "ceo": "9c", "cfo": "9c", "gc": "9c"},
    }
    by_id = {b["id"]: b for b in scenario["beats"]}
    for beat in scenario["beats"]:
        if beat["zoneId"] != "boardroom":
            assert "boardVote" not in beat
            continue
        vote = beat["boardVote"]
        assert list(vote["voters"]) == list(VOTERS)
        assert vote["ballots"] == expected[beat["id"]]
        option_ids = {o["id"] for o in beat["options"]}
        assert set(vote["ballots"].values()) <= option_ids
        assert by_id[beat["id"]]["zoneId"] == "boardroom"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pixel-simulator-game/backend && python -m pytest tests/test_scenario.py::test_boardroom_beats_have_authored_ballots -v`

Expected: FAIL (`boardVote` missing).

- [ ] **Step 3: Add `boardVote` to beats 4, 7, 9**

Insert immediately after `npcId` (or after `debateTopic`) on each boardroom beat:

Beat 4:

```json
"boardVote": {
  "voters": ["chair", "ceo", "cfo", "gc"],
  "ballots": { "chair": "4b", "ceo": "4b", "cfo": "4a", "gc": "4b" }
},
```

Beat 7:

```json
"boardVote": {
  "voters": ["chair", "ceo", "cfo", "gc"],
  "ballots": { "chair": "7a", "ceo": "7a", "cfo": "7a", "gc": "7b" }
},
```

Beat 9:

```json
"boardVote": {
  "voters": ["chair", "ceo", "cfo", "gc"],
  "ballots": { "chair": "9c", "ceo": "9c", "cfo": "9c", "gc": "9c" }
},
```

- [ ] **Step 4: Run scenario tests**

Run: `cd pixel-simulator-game/backend && python -m pytest tests/test_scenario.py -v`

Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add pixel-simulator-game/backend/scenarios/meridian-activist-01.json \
        pixel-simulator-game/backend/tests/test_scenario.py
git commit -m "Author static board ballots for boardroom beats."
```

---

### Task 3: Session API boardroom loop

**Files:**
- Modify: `pixel-simulator-game/backend/app/api/sessions.py`
- Modify: `pixel-simulator-game/backend/app/providers/deterministic.py`
- Modify: `pixel-simulator-game/backend/tests/test_api.py`
- Modify: `pixel-simulator-game/backend/tests/test_providers.py`

**Interfaces:**
- Consumes: `create_board_vote_resolver()`, `safe_resolve()`, `public_board_vote()`, `AuthoredBoardVote` ballots from scenario
- Produces: boardroom `_run_beat` stops at `AWAIT_DECISION` with options and no debate; `decide` on boardroom runs convene → debate → vote → `apply(winner)` and stamps `motionId` / `ballots` / `tieBrokenBy` on `history[-1]`

- [ ] **Step 1: Write failing API + provider tests**

Append to `pixel-simulator-game/backend/tests/test_api.py`:

```python
def _play_to_beat(client, sid: str, beat_n: int) -> dict:
    """Advance through beats 1..beat_n-1 so the next interact is that beat."""
    for _ in range(beat_n - 1):
        snap = client.get(f"/sessions/{sid}").json()
        client.post(f"/sessions/{sid}/interact", json={"targetId": _target_for(snap)})
        snap = _wait_for_phase(client, sid, "AWAIT_DECISION")
        client.post(
            f"/sessions/{sid}/decide", json={"optionId": snap["options"][0]["id"]}
        )
        _wait_for_phase(client, sid, "EXPLORE")
    return client.get(f"/sessions/{sid}").json()


def test_boardroom_options_before_debate(client):
    from app.api.sessions import SESSIONS

    data = _create(client, seed=1)
    sid = data["sessionId"]
    _play_to_beat(client, sid, 4)

    client.post(f"/sessions/{sid}/interact", json={"targetId": "zone:boardroom"})
    _wait_for_phase(client, sid, "AWAIT_DECISION")

    session = SESSIONS[sid]
    events = []
    while not session.queue.empty():
        events.append(session.queue.get_nowait())
    types = [t for t, _ in events]
    assert "options" in types
    assert "debate_delta" not in types
    for option in dict(events[types.index("options")][1])["options"]:
        assert "deltas" not in option


def test_boardroom_decide_applies_board_winner_not_motion(client):
    from app.api.sessions import SESSIONS

    data = _create(client, seed=1)
    sid = data["sessionId"]
    _play_to_beat(client, sid, 4)

    client.post(f"/sessions/{sid}/interact", json={"targetId": "zone:boardroom"})
    _wait_for_phase(client, sid, "AWAIT_DECISION")
    res = client.post(f"/sessions/{sid}/decide", json={"optionId": "4a"})
    assert res.status_code == 200
    _wait_for_phase(client, sid, "EXPLORE")

    session = SESSIONS[sid]
    last = session.state["history"][-1]
    assert last["optionId"] == "4b"
    assert last["motionId"] == "4a"
    assert last["ballots"]["cfo"] == "4a"
    assert last["ballots"]["chair"] == "4b"
    assert "deltas" not in last.get("ballots", {})

    events = []
    while not session.queue.empty():
        events.append(session.queue.get_nowait())
    types = [t for t, _ in events]
    assert types.index("convene") < types.index("debate_delta") < types.index("board_vote")
    assert types.index("board_vote") < types.index("kpi_patch")
    vote = dict(events[types.index("board_vote")][1])
    assert vote["motionId"] == "4a"
    assert vote["winningOptionId"] == "4b"
    assert "deltas" not in vote
    for row in vote["votes"]:
        assert "deltas" not in row
```

Also update `test_full_nine_beat_run_headless` so each `decide` waits until `EXPLORE` or `GAME_END` (boardroom `decide` may still be finishing apply — with a blocking decide this is already true; keep the wait so either implementation works):

```python
        res = client.post(
            f"/sessions/{sid}/decide", json={"optionId": snap["options"][0]["id"]}
        )
        assert res.status_code == 200
        snap = client.get(f"/sessions/{sid}").json()
        if snap["phase"] not in {"EXPLORE", "GAME_END"}:
            snap = _wait_for_phase(client, sid, "GAME_END" if snap["beatIndex"] == 8 else "EXPLORE")
```

Simpler: after every decide, poll until phase is `EXPLORE` or `GAME_END`:

```python
        res = client.post(
            f"/sessions/{sid}/decide", json={"optionId": snap["options"][0]["id"]}
        )
        assert res.status_code == 200
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            snap = client.get(f"/sessions/{sid}").json()
            if snap["phase"] in {"EXPLORE", "GAME_END"}:
                break
            time.sleep(0.02)
        else:
            raise AssertionError(f"stuck in phase {snap['phase']!r}")
```

Append to `pixel-simulator-game/backend/tests/test_providers.py` in a new test:

```python
def test_deterministic_prefaces_chair_motion(scenario, monkeypatch):
    monkeypatch.setenv("DEBATE_DELAY_MS", "0")
    beat = next(b for b in scenario["beats"] if b["id"] == "beat-4")
    ctx = {
        "state": {"beatIndex": 3, "kpis": dict(scenario["kpis"])},
        "beat": beat,
        "options": beat["options"],
        "npcs": list(scenario["npcs"]),
        "motionId": "4a",
    }
    lines = collect(DeterministicDebate(delay_ms=0), ctx)
    assert lines[0]["speakerId"] == "chair"
    assert "Demand two board seats" in lines[0]["text"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pixel-simulator-game/backend && python -m pytest tests/test_api.py::test_boardroom_options_before_debate tests/test_api.py::test_boardroom_decide_applies_board_winner_not_motion tests/test_providers.py::test_deterministic_prefaces_chair_motion -v`

Expected: FAIL (debate still precedes options; history has `optionId == 4a`; no chair preface).

- [ ] **Step 3: Preface motion in DeterministicDebate**

In `pixel-simulator-game/backend/app/providers/deterministic.py`, after building `lines` from `scriptedLines` and before the option loop, if `ctx.get("motionId")`:

```python
        motion_id = ctx.get("motionId")
        if motion_id:
            motion = next((o for o in options if o.get("id") == motion_id), None)
            label = (motion or {}).get("label") or motion_id
            lines.insert(
                0,
                {"speakerId": "chair", "text": f"The activist proposes '{label}'."},
            )
```

Insert **before** scripted lines are copied, or insert at 0 after the scripted copy — spec says Chair opens with the motion line, then existing scripted lines. Use `insert(0, ...)` after the scripted copy.

- [ ] **Step 4: Branch the session API**

In `pixel-simulator-game/backend/app/api/sessions.py`:

1. Import:

```python
from app.engine.board_vote import create_board_vote_resolver, public_board_vote, safe_resolve
```

2. Add fields on `Session`:

```python
    vote_resolver: Any = field(default_factory=create_board_vote_resolver)
    motion_id: str | None = None
```

(`Any` already imported; or type `BoardVoteResolver`.)

3. Helper:

```python
def _is_boardroom(beat: dict[str, Any]) -> bool:
    return beat.get("zoneId") == "boardroom"
```

4. Replace `_run_beat` so after the `beat` emit + sleep:

```python
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
```

5. Replace `decide` body:

```python
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


async def _decide_boardroom(session: Session, beat: dict[str, Any], motion_id: str) -> dict[str, Any]:
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
```

6. Snapshot: if `session.motion_id` is set, include `"motionId": session.motion_id`.

- [ ] **Step 5: Run backend tests**

Run: `cd pixel-simulator-game/backend && python -m pytest tests/test_api.py tests/test_providers.py tests/test_board_vote.py tests/test_engine.py tests/test_scenario.py tests/test_lobby.py -v`

Expected: all passed. `test_full_nine_beat_run_headless` must still reach `GAME_END`.

- [ ] **Step 6: Commit**

```bash
git add pixel-simulator-game/backend/app/api/sessions.py \
        pixel-simulator-game/backend/app/providers/deterministic.py \
        pixel-simulator-game/backend/tests/test_api.py \
        pixel-simulator-game/backend/tests/test_providers.py
git commit -m "Run boardroom beats as motion-then-vote on the session API."
```

---

### Task 4: Phaser gather, key-gate, dismiss

**Files:**
- Modify: `pixel-simulator-game/frontend/src/game/officeMap.ts`
- Modify: `pixel-simulator-game/frontend/src/game/OfficeScene.ts`
- Modify: `pixel-simulator-game/frontend/src/game/eventBus.ts`
- Modify: `pixel-simulator-game/frontend/src/net/session.ts`

**Interfaces:**
- Consumes: SSE `convene` / `debate_delta` / `board_vote` / `phase` via bus
- Produces: `BOARD_SEATS`, `BOARD_CAMERA`, `PLAYER_GALLERY`; scene modes `wander | convene | seated | dismiss`; key/click advances buffered lines only after `convene`

- [ ] **Step 1: Add seat data**

Append to `pixel-simulator-game/frontend/src/game/officeMap.ts`:

```typescript
export type Face = 'down' | 'left' | 'right' | 'up';

export interface SeatDef {
  x: number;
  y: number;
  face: Face;
}

/** Chair tiles around the existing board table. Tweak here, not in OfficeScene. */
export const BOARD_SEATS: Record<string, SeatDef> = {
  chair: { x: 35, y: 3, face: 'left' },
  ceo: { x: 26, y: 1, face: 'down' },
  cfo: { x: 29, y: 1, face: 'down' },
  gc: { x: 32, y: 1, face: 'down' },
  analyst: { x: 26, y: 5, face: 'up' },
  partner: { x: 29, y: 5, face: 'up' },
};

export const PLAYER_GALLERY: SeatDef = { x: 32, y: 5, face: 'up' };

/** Table-center tile the camera holds on during a meeting. */
export const BOARD_CAMERA = { x: 30, y: 4 };
```

- [ ] **Step 2: Add bus events and SSE forwards**

In `eventBus.ts` add:

```typescript
  CONVENE: 'game:convene',
  BOARD_VOTE: 'game:boardVote',
  DEBATE_LINE: 'game:debateLine',
```

In `session.ts` `connectEvents`:

```typescript
  forward('convene', GameEvents.CONVENE);
  forward('board_vote', GameEvents.BOARD_VOTE);
```

Change the `debate_delta` forward so the scene can distinguish auto-speech vs buffered lines: keep forwarding `debate_delta` → `GameEvents.SPEECH` **and** `GameEvents.DEBATE_LINE` (same payload). OfficeScene decides which to honor.

```typescript
  source.addEventListener('debate_delta', (e) => {
    const payload = JSON.parse((e as MessageEvent).data);
    gameBus.emit(GameEvents.DEBATE_LINE, payload);
    gameBus.emit(GameEvents.SPEECH, payload);
  });
```

- [ ] **Step 3: OfficeScene meeting mode**

In `OfficeScene.ts`:

1. Import `BOARD_SEATS`, `BOARD_CAMERA`, `PLAYER_GALLERY`.
2. Add fields:

```typescript
  private meeting = false;
  private seated = false;
  private lineQueue: { speakerId: string; text: string }[] = [];
  private awaitingAdvance = false;
  private promptText: Phaser.GameObjects.Text | null = null;
```

3. On `GameEvents.CONVENE`: set `meeting = true`, `seated = false`, `lineQueue = []`, `phaseLocked = true`. For each NPC, `target` = seat pixel (`BOARD_SEATS[id].x * TILE + TILE/2`, same for y). Player `moveTo` `PLAYER_GALLERY`. Camera `stopFollow` and `pan(BOARD_CAMERA.x * TILE + TILE/2, BOARD_CAMERA.y * TILE + TILE/2, 700, 'Sine.easeInOut')`.

4. On `GameEvents.SPEECH`: if `this.meeting`, **return** (do not auto-show). Non-meeting: existing `showSpeech`.

5. On `GameEvents.DEBATE_LINE`: if `this.meeting`, push onto `lineQueue`.

6. On `GameEvents.PHASE` `EXPLORE` or `GAME_END`: if `meeting`, start dismiss (targets = each NPC `def.spawn`), `meeting = false`, `seated = false`, `clearBubbles`, hide prompt, `startFollow` player. Existing `EXPLORE` clearBubbles stays.

7. In `updateNpcs`, when `meeting && !seated`: do **not** use the generic `phaseLocked` freeze. Walk toward seat targets. Stuck 1000 ms → snap to seat. When every NPC (and player) is within 4px of seat, set `seated = true`, face each sprite `BOARD_SEATS[id].face` / `PLAYER_GALLERY.face`, show prompt `"Press any key"`.

8. When `meeting && seated`, freeze velocities (same as today’s debate freeze).

9. `updatePlayer`: if `meeting && !seated`, `moveTo` gallery (or set velocity toward it); if seated, velocity 0. `locked` still blocks WASD.

10. Input: in `create`, `this.input.keyboard!.on('keydown', () => this.advanceLine())` and reuse canvas `pointerdown` — if `meeting && seated`, `advanceLine` instead of `tryInteract`.

```typescript
  private advanceLine() {
    if (!this.meeting || !this.seated) return;
    const next = this.lineQueue.shift();
    if (!next) return;
    this.hidePrompt();
    this.showSpeech(next.speakerId, next.text);
  }
```

`showSpeech` during a meeting must **not** pan the camera (guard: `if (!this.meeting) { cam.pan(...) }`).

11. Stuck-snap timeout constant `MEETING_STUCK_MS = 1000` at top of file.

12. Do not start key-advance until seated, even if lines are already queued.

- [ ] **Step 4: Typecheck / build**

Run: `cd pixel-simulator-game/frontend && npm run build`

Expected: success (exit 0).

- [ ] **Step 5: Commit**

```bash
git add pixel-simulator-game/frontend/src/game/officeMap.ts \
        pixel-simulator-game/frontend/src/game/OfficeScene.ts \
        pixel-simulator-game/frontend/src/game/eventBus.ts \
        pixel-simulator-game/frontend/src/net/session.ts
git commit -m "Gather agents at the board table and key-advance debate lines."
```

---

### Task 5: Vote overlay and SPEC

**Files:**
- Create: `pixel-simulator-game/frontend/src/ui/BoardVoteOverlay.tsx`
- Modify: `pixel-simulator-game/frontend/src/App.tsx`
- Modify: `pixel-simulator-game/frontend/src/App.css`
- Modify: `pixel-simulator-game/SPEC.md`

**Interfaces:**
- Consumes: `game:boardVote` payload from Task 3 (`motionLabel`, `votes[]`, `winningLabel`, `tieBrokenBy?`)
- Produces: overlay dismissed on any key or click; no deltas rendered

- [ ] **Step 1: Overlay component**

Create `pixel-simulator-game/frontend/src/ui/BoardVoteOverlay.tsx`:

```tsx
import { useEffect, useState } from 'react';
import { GameEvents, gameBus } from '../game/eventBus';

interface VoteRow {
  speakerId: string;
  name: string;
  optionId: string;
  label: string;
}

interface BoardVotePayload {
  motionId: string;
  motionLabel: string;
  votes: VoteRow[];
  winningOptionId: string;
  winningLabel: string;
  tieBrokenBy?: string;
}

export function BoardVoteOverlay() {
  const [vote, setVote] = useState<BoardVotePayload | null>(null);

  useEffect(() => {
    const unsubs = [
      gameBus.on(GameEvents.BOARD_VOTE, (p) => {
        setVote(p as BoardVotePayload);
      }),
      gameBus.on(GameEvents.PHASE, (p) => {
        const { phase } = p as { phase: string };
        if (phase === 'EXPLORE' || phase === 'GAME_END') setVote(null);
      }),
    ];
    const onKey = () => setVote(null);
    window.addEventListener('keydown', onKey);
    return () => {
      unsubs.forEach((u) => u());
      window.removeEventListener('keydown', onKey);
    };
  }, []);

  if (!vote) return null;

  return (
    <div
      className="option-overlay vote-overlay"
      role="dialog"
      aria-label="Board vote"
      onClick={() => setVote(null)}
    >
      <p className="option-title">Board vote</p>
      <p className="vote-motion">Your motion: {vote.motionLabel}</p>
      <ul className="vote-rows">
        {vote.votes.map((row) => (
          <li key={row.speakerId}>
            <strong>{row.name}</strong> — {row.label}
          </li>
        ))}
      </ul>
      <p className="vote-adopt">The board adopts: {vote.winningLabel}</p>
      {vote.tieBrokenBy === 'chair' ? (
        <p className="vote-tie">Chair breaks the tie.</p>
      ) : null}
      <p className="vote-hint">Press any key</p>
    </div>
  );
}
```

Mount in `App.tsx` next to `OptionCards`:

```tsx
import { BoardVoteOverlay } from './ui/BoardVoteOverlay';
// ...
          <OptionCards />
          <BoardVoteOverlay />
```

Add CSS after `.option-cons li` in `App.css`:

```css
.vote-overlay {
  pointer-events: auto;
}

.vote-motion,
.vote-adopt,
.vote-tie,
.vote-hint {
  margin: 0.25rem 0;
  font-size: 0.8rem;
}

.vote-rows {
  margin: 0.35rem 0;
  padding: 0;
  list-style: none;
  font-size: 0.78rem;
}

.vote-adopt {
  color: #3fd0a4;
  font-weight: 600;
}

.vote-hint {
  color: #8aa0b8;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-size: 0.68rem;
}
```

- [ ] **Step 2: Update SPEC.md**

In `pixel-simulator-game/SPEC.md`:

- Game phases line: add `CONVENE` and `BOARD_VOTE`. Boardroom beats: `EXPLORE` → `BEAT_INTRO` → `AWAIT_DECISION` → `CONVENE` → `DEBATE` → `BOARD_VOTE` → `APPLY` → `EXPLORE` | `GAME_END`.
- `POST /decide`: if current beat `zoneId` is `boardroom`, optionId is the motion; server applies the resolver winner after debate.
- SSE table: add `convene` `{ beatId, motionId }` and `board_vote` `{ motionId, motionLabel, votes, winningOptionId, winningLabel, tieBrokenBy? }` — no deltas.
- Bus table: `game:convene`, `game:boardVote`, `game:debateLine`.
- Soft-lock: also during `CONVENE` / `BOARD_VOTE`.
- Mention `BOARD_VOTE_RESOLVER` and `app/engine/board_vote.py`.

- [ ] **Step 3: Build frontend and run full backend suite**

Run:

```bash
cd pixel-simulator-game/frontend && npm run build
cd ../backend && python -m pytest tests -v
```

Expected: frontend exit 0; backend all passed (81+ new tests).

- [ ] **Step 4: Commit**

```bash
git add pixel-simulator-game/frontend/src/ui/BoardVoteOverlay.tsx \
        pixel-simulator-game/frontend/src/App.tsx \
        pixel-simulator-game/frontend/src/App.css \
        pixel-simulator-game/SPEC.md
git commit -m "Show the board vote recap and document the boardroom loop."
```

---

## Self-review

**Spec coverage**

| Spec section | Task |
|--------------|------|
| §2 / §4 boardroom loop | Task 3 |
| §3 non-boardroom unchanged | Task 3 tests (`test_event_queue_sequence`, `test_decide_applies`) |
| §5 seats / walk-in / camera / key-gate / walk-out | Task 4 |
| §6.1 apply unchanged | Task 3 (calls existing `apply`) |
| §6.2 plugin + fallback | Task 1 |
| §6.3 authored ballots + majority | Tasks 1–2 |
| §6.4 history stamps | Task 3 |
| §6.5 chair motion line | Task 3 |
| §7 overlay + events | Tasks 3–5 |
| §8 failures | Task 1 (`safe_resolve`), Task 4 (stuck-snap) |
| §9 tests | Tasks 1–3 |
| No skip-all / no second scene / no delta retune | honored throughout |

**simulate.py:** left on `engine.apply(player pick)` so published win-rate math is unchanged. Session/API path is what the player sees.

**Placeholder scan:** none.

**Type consistency:** `BoardVote`, `safe_resolve`, `public_board_vote`, `GameEvents.CONVENE` / `BOARD_VOTE` / `DEBATE_LINE` used with the same names in later tasks.
