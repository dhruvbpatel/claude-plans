"""Once-per-beat lobby bonus (Phase 6): engine rules + API surface."""

from __future__ import annotations

import time

import pytest

from app.engine.scoring import LOBBY_BONUS_DELTAS


# -- engine ------------------------------------------------------------------


def test_lobby_bonus_applies_deltas_once(engine, scenario):
    state = engine.create(scenario, seed=0)
    bonus = engine.apply_lobby_bonus(state)
    assert bonus is not None
    for kpi, delta in LOBBY_BONUS_DELTAS.items():
        assert bonus["kpis"][kpi] == pytest.approx(state["kpis"][kpi] + delta)
    assert bonus["lobbyClaimedBeats"] == [0]
    # Same beat again -> already claimed.
    assert engine.apply_lobby_bonus(bonus) is None


def test_lobby_bonus_does_not_mutate_input(engine, scenario):
    state = engine.create(scenario, seed=0)
    engine.apply_lobby_bonus(state)
    assert "lobbyClaimedBeats" not in state
    assert state["kpis"] == scenario["kpis"]


def test_lobby_bonus_resets_each_beat(engine, scenario):
    state = engine.create(scenario, seed=0)
    state = engine.apply_lobby_bonus(state)
    state = engine.apply(state, "1a")  # advance to beat 2
    again = engine.apply_lobby_bonus(state)
    assert again is not None
    assert again["lobbyClaimedBeats"] == [0, 1]


def test_lobby_bonus_unavailable_after_game_end(engine, scenario):
    state = engine.create(scenario, seed=0)
    for option_id in ["1c", "2b", "3a", "4c", "5b"]:  # max aggression -> lost
        if state["outcome"] != "playing":
            break
        state = engine.apply(state, option_id)
    assert state["outcome"] == "lost"
    assert engine.apply_lobby_bonus(state) is None


def test_lobby_bonus_deterministic(engine, scenario):
    a = engine.apply_lobby_bonus(engine.create(scenario, seed=42))
    b = engine.apply_lobby_bonus(engine.create(scenario, seed=42))
    assert a == b


# -- API -----------------------------------------------------------------------


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("DEBATE_DELAY_MS", "0")
    monkeypatch.setenv("DEBATE_PROVIDER", "deterministic")
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


def _await_phase(client, session_id: str, phase: str, tries: int = 100) -> dict:
    for _ in range(tries):
        snap = client.get(f"/sessions/{session_id}").json()
        if snap["phase"] == phase:
            return snap
        time.sleep(0.02)
    raise AssertionError(f"session never reached phase {phase!r}")


def test_api_lobby_bonus_once_per_beat(client):
    created = client.post("/sessions", json={"seed": 5}).json()
    sid = created["sessionId"]
    chest = created["kpis"]["warChest"]

    # First lobby visit: bonus granted, no beat activation.
    body = client.post(
        f"/sessions/{sid}/interact", json={"targetId": "zone:lobby"}
    ).json()
    assert body["accepted"] is False
    assert body["lobbyBonus"] == "granted"
    snap = client.get(f"/sessions/{sid}").json()
    assert snap["kpis"]["warChest"] == pytest.approx(
        chest + LOBBY_BONUS_DELTAS["warChest"]
    )

    # Second visit in the same beat: spent, KPIs untouched.
    body = client.post(
        f"/sessions/{sid}/interact", json={"targetId": "zone:lobby"}
    ).json()
    assert body["lobbyBonus"] == "spent"
    snap = client.get(f"/sessions/{sid}").json()
    assert snap["kpis"]["warChest"] == pytest.approx(
        chest + LOBBY_BONUS_DELTAS["warChest"]
    )

    # Play beat 1, then the lobby pays out again.
    body = client.post(
        f"/sessions/{sid}/interact", json={"targetId": "zone:trading_floor"}
    ).json()
    assert body["accepted"] is True
    _await_phase(client, sid, "AWAIT_DECISION")
    client.post(f"/sessions/{sid}/decide", json={"optionId": "1a"})

    body = client.post(
        f"/sessions/{sid}/interact", json={"targetId": "zone:lobby"}
    ).json()
    assert body["lobbyBonus"] == "granted"
