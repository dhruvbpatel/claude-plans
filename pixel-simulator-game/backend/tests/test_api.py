"""Session API tests (Phase 4) — REST flow with the deterministic provider.

DEBATE_DELAY_MS=0 removes pacing so the BEAT_INTRO -> AWAIT_DECISION
background task finishes almost instantly; tests poll the session snapshot.
"""

from __future__ import annotations

import os
import time

import pytest
from fastapi.testclient import TestClient

os.environ["DEBATE_DELAY_MS"] = "0"

from app.main import app  # noqa: E402

GRADES = {"A", "B", "C", "D", "F"}


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _create(client: TestClient, seed: int = 7) -> dict:
    res = client.post("/sessions", json={"scenarioId": "meridian-activist-01", "seed": seed})
    assert res.status_code == 200
    return res.json()


def _wait_for_phase(client: TestClient, session_id: str, phase: str, timeout: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        snap = client.get(f"/sessions/{session_id}").json()
        if snap["phase"] == phase:
            return snap
        time.sleep(0.02)
    raise AssertionError(f"session never reached phase {phase!r}")


def _target_for(snap: dict) -> str:
    return f"zone:{snap['nextBeat']['zoneId']}"


def _drain(session) -> list:
    events = []
    while not session.queue.empty():
        events.append(session.queue.get_nowait())
    return events


def _wait_settled(client: TestClient, session_id: str, timeout: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        snap = client.get(f"/sessions/{session_id}").json()
        if snap["phase"] in {"EXPLORE", "GAME_END"}:
            return snap
        time.sleep(0.02)
    raise AssertionError(f"session stuck in phase {snap['phase']!r}")


def _play_to_beat(client: TestClient, sid: str, beat_n: int) -> dict:
    """Advance through beats 1..beat_n-1 so the next interact is that beat."""
    for _ in range(beat_n - 1):
        snap = client.get(f"/sessions/{sid}").json()
        client.post(f"/sessions/{sid}/interact", json={"targetId": _target_for(snap)})
        snap = _wait_for_phase(client, sid, "AWAIT_DECISION")
        client.post(
            f"/sessions/{sid}/decide", json={"optionId": snap["options"][0]["id"]}
        )
        _wait_settled(client, sid)
    return client.get(f"/sessions/{sid}").json()


def test_create_session_shape(client):
    data = _create(client)
    assert data["phase"] == "EXPLORE"
    assert data["beatIndex"] == 0
    assert data["kpis"]["stockPrice"] == 42.0
    assert data["flags"] == []
    assert data["nextBeat"]["beatId"] == "beat-1"
    assert data["nextBeat"]["zoneId"] == "trading_floor"


def test_interact_wrong_target_rejected(client):
    data = _create(client)
    res = client.post(
        f"/sessions/{data['sessionId']}/interact", json={"targetId": "zone:press_bay"}
    )
    body = res.json()
    assert body["accepted"] is False
    assert body["phase"] == "EXPLORE"
    assert body["nextBeat"]["zoneId"] == "trading_floor"


def test_interact_activates_beat_and_options_hide_deltas(client):
    data = _create(client)
    sid = data["sessionId"]

    res = client.post(f"/sessions/{sid}/interact", json={"targetId": "zone:trading_floor"})
    body = res.json()
    assert body == {"phase": "BEAT_INTRO", "beatId": "beat-1", "accepted": True}

    snap = _wait_for_phase(client, sid, "AWAIT_DECISION")
    assert len(snap["options"]) == 3
    for option in snap["options"]:
        assert set(option) == {"id", "label", "pros", "cons"}

    # A second interact while awaiting a decision is rejected.
    res = client.post(f"/sessions/{sid}/interact", json={"targetId": "zone:trading_floor"})
    assert res.json()["accepted"] is False


def test_decide_applies_and_returns_to_explore(client):
    data = _create(client)
    sid = data["sessionId"]

    # Deciding outside AWAIT_DECISION is a conflict.
    assert client.post(f"/sessions/{sid}/decide", json={"optionId": "1a"}).status_code == 409

    client.post(f"/sessions/{sid}/interact", json={"targetId": "zone:trading_floor"})
    _wait_for_phase(client, sid, "AWAIT_DECISION")

    assert (
        client.post(f"/sessions/{sid}/decide", json={"optionId": "nope"}).status_code == 400
    )

    res = client.post(f"/sessions/{sid}/decide", json={"optionId": "1a"})
    body = res.json()
    assert body["phase"] == "EXPLORE"
    assert body["outcome"] == "playing"
    assert body["kpis"]["ownershipPct"] == 8.5
    assert body["consequence"]

    snap = client.get(f"/sessions/{sid}").json()
    assert snap["beatIndex"] == 1
    assert snap["nextBeat"]["beatId"] == "beat-2"


def test_npc_trigger_also_activates_beat(client):
    data = _create(client)
    sid = data["sessionId"]
    res = client.post(f"/sessions/{sid}/interact", json={"targetId": "npc:analyst"})
    assert res.json()["accepted"] is True


def test_full_nine_beat_run_headless(client):
    data = _create(client, seed=42)
    sid = data["sessionId"]

    for _ in range(9):
        snap = client.get(f"/sessions/{sid}").json()
        res = client.post(
            f"/sessions/{sid}/interact", json={"targetId": _target_for(snap)}
        )
        assert res.json()["accepted"] is True

        snap = _wait_for_phase(client, sid, "AWAIT_DECISION")
        assert snap["options"], "expected at least one available option"
        res = client.post(
            f"/sessions/{sid}/decide", json={"optionId": snap["options"][0]["id"]}
        )
        assert res.status_code == 200
        _wait_settled(client, sid)

    snap = client.get(f"/sessions/{sid}").json()
    assert snap["phase"] == "GAME_END"
    assert snap["outcome"] in {"won", "lost"}
    assert snap["beatIndex"] == 9


def test_event_queue_sequence_and_sse_format(client):
    """The session queue buffers the full SSE event sequence for a beat.

    (The live infinite stream is exercised end-to-end via curl/browser; the
    TestClient can't close an infinite StreamingResponse without hanging.)
    """
    from app.api.sessions import SESSIONS, _format_sse

    data = _create(client)
    sid = data["sessionId"]
    client.post(f"/sessions/{sid}/interact", json={"targetId": "zone:trading_floor"})
    _wait_for_phase(client, sid, "AWAIT_DECISION")

    session = SESSIONS[sid]
    events = []
    while not session.queue.empty():
        events.append(session.queue.get_nowait())
    types = [t for t, _ in events]

    assert {"phase", "kpi_patch", "next_beat", "beat", "debate_delta",
            "debate_complete", "options"} <= set(types)
    # Ordering: debate deltas come after the beat intro and before options.
    assert types.index("beat") < types.index("debate_delta") < types.index("options")

    options_payload = dict(events[types.index("options")][1])
    for option in options_payload["options"]:
        assert "deltas" not in option

    delta_payload = dict(events[types.index("debate_delta")][1])
    wire = _format_sse("debate_delta", delta_payload)
    assert wire.startswith("event: debate_delta\ndata: {")
    assert wire.endswith("}\n\n")


def test_boardroom_options_before_debate(client):
    from app.api.sessions import SESSIONS

    data = _create(client, seed=1)
    sid = data["sessionId"]
    _play_to_beat(client, sid, 4)
    _drain(SESSIONS[sid])

    client.post(f"/sessions/{sid}/interact", json={"targetId": "zone:boardroom"})
    _wait_for_phase(client, sid, "AWAIT_DECISION")

    events = _drain(SESSIONS[sid])
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
    _drain(SESSIONS[sid])

    client.post(f"/sessions/{sid}/interact", json={"targetId": "zone:boardroom"})
    _wait_for_phase(client, sid, "AWAIT_DECISION")
    res = client.post(f"/sessions/{sid}/decide", json={"optionId": "4a"})
    assert res.status_code == 200
    _wait_settled(client, sid)

    session = SESSIONS[sid]
    last = session.state["history"][-1]
    assert last["optionId"] == "4b"
    assert last["motionId"] == "4a"
    assert last["ballots"]["cfo"] == "4a"
    assert last["ballots"]["chair"] == "4b"

    events = _drain(session)
    types = [t for t, _ in events]
    assert types.index("convene") < types.index("debate_delta") < types.index("board_vote")
    assert types.index("board_vote") < types.index("kpi_patch")
    vote = dict(events[types.index("board_vote")][1])
    assert vote["motionId"] == "4a"
    assert vote["winningOptionId"] == "4b"
    assert "deltas" not in vote
    for row in vote["votes"]:
        assert "deltas" not in row
