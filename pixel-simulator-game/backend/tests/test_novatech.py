"""NovaTech scenario shape and a seeded 8-quarter random walk."""

from __future__ import annotations

import json
import random
from pathlib import Path

from app.engine.scoring import MeridianScoringEngine

SCENARIO_PATH = (
    Path(__file__).resolve().parents[1] / "scenarios" / "novatech-proxy-war-01.json"
)


def test_novatech_scenario_shape():
    scenario = json.loads(SCENARIO_PATH.read_text())
    assert scenario["schemaVersion"] == 2
    assert scenario["id"] == "novatech-proxy-war-01"
    assert len(scenario["metrics"]) == 13
    assert len(scenario["cards"]) == 16
    families = {c["family"] for c in scenario["cards"]}
    assert len(families) == 8
    assert len(scenario["eventDeck"]) == 8
    assert scenario["scoring"]["winAt"] == 110


def test_novatech_create_has_thirteen_metrics():
    scenario = json.loads(SCENARIO_PATH.read_text())
    engine = MeridianScoringEngine()
    state = engine.create(scenario, seed=0)
    assert len(state["kpis"]) == 13
    assert state["kpis"]["sharePrice"] == 100
    assert state["kpis"]["rivalPressure"] == 20


def test_novatech_same_seed_replays():
    scenario = json.loads(SCENARIO_PATH.read_text())
    engine = MeridianScoringEngine()

    def play(seed: int):
        rng = random.Random(seed)
        state = engine.create(scenario, seed=seed)
        while state["outcome"] == "playing":
            state = engine.start_quarter(state)
            options = engine.available_options(state)
            state = engine.apply(state, rng.choice(options)["id"])
        return state

    a = play(9)
    b = play(9)
    assert a["history"] == b["history"]
    assert a["kpis"] == b["kpis"]
    assert a["outcome"] == b["outcome"]


def test_novatech_interrupt_quarter_deals_four():
    scenario = json.loads(SCENARIO_PATH.read_text())
    engine = MeridianScoringEngine()
    state = engine.create(scenario, seed=0)
    # Quarters 0 and 1 have no interrupt; quarter 2 (nominate_slate) does.
    for _ in range(2):
        state = engine.start_quarter(state)
        state = engine.apply(state, engine.available_options(state)[0]["id"])
    state = engine.start_quarter(state)
    assert state["interrupt"] is True
    assert len(state["hand"]) == 4
    assert "leadership_renewal" in state["hand"]


def test_novatech_random_walk_terminates():
    scenario = json.loads(SCENARIO_PATH.read_text())
    engine = MeridianScoringEngine()
    rng = random.Random(3)
    state = engine.create(scenario, seed=3)
    while state["outcome"] == "playing":
        state = engine.start_quarter(state)
        options = engine.available_options(state)
        assert options
        state = engine.apply(state, rng.choice(options)["id"])
    assert state["outcome"] in {"won", "lost"}
    assert state["beatIndex"] <= 8
    assert len(state["history"]) == state["beatIndex"]
