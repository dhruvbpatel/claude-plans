"""Phase 1: config-driven metrics, v2 protocols, env factories. Meridian stays green."""

from __future__ import annotations

import copy

import pytest

from app.engine.factory import (
    create_card_dealer,
    create_event_deck,
    create_rival_policy,
    create_scoring_model,
    create_war_room_provider,
)
from app.engine.metrics import bounds_from_scenario, schema_version
from app.engine.scoring import MeridianScoringEngine, _clamp


MINI_V2 = {
    "id": "mini-v2",
    "schemaVersion": 2,
    "metrics": [
        {"id": "sharePrice", "label": "Share price", "opening": 100, "min": 0, "group": "market"},
        {"id": "cash", "label": "Cash", "opening": 50, "group": "financial"},
        {"id": "morale", "label": "Morale", "opening": 60, "min": 0, "max": 100, "group": "people"},
    ],
    "cards": [
        {
            "id": "trust_campaign",
            "family": "campaign",
            "label": "Win the public narrative",
            "deltas": {"morale": 50},
            "requires": [],
            "unlocks": [],
        },
        {
            "id": "cost_reset",
            "family": "operating",
            "label": "Cut costs",
            "deltas": {"cash": 10},
            "requires": [],
            "unlocks": [],
        },
        {
            "id": "product_bet",
            "family": "product",
            "label": "Product bet",
            "deltas": {"sharePrice": 1},
            "requires": [],
            "unlocks": [],
        },
    ],
    "knockOnRules": [],
    "eventDeck": [
        {
            "id": "sale_thesis",
            "title": "Sale thesis",
            "news": "Rival goes public.",
            "focusMetrics": ["reputation"],
        }
    ],
    "rival": {"threshold": 55, "defaultPressureDelta": 6, "attacks": []},
    "scoring": {"winAt": 110, "weights": {"sharePrice": 100}},
    "warRoom": {
        "chair": "chair",
        "seats": [
            {"id": "cfo", "name": "CFO", "owns": ["cash", "sharePrice"]},
            {"id": "hr", "name": "HR", "owns": ["morale"]},
        ],
    },
}


def test_schema_version_detects_v1_and_v2(scenario):
    assert schema_version(scenario) == 1
    assert schema_version(MINI_V2) == 2
    assert schema_version({"id": "x", "beats": []}) == 1
    assert schema_version({"id": "x", "cards": []}) == 2


def test_v1_bounds_match_meridian_defaults(scenario):
    bounds = bounds_from_scenario(scenario)
    assert bounds["mediaHeat"] == (0.0, 100.0)
    assert bounds["warChest"] == (None, None)
    assert bounds["stockPrice"][0] == 0.0


def test_v2_bounds_come_from_metrics_array():
    bounds = bounds_from_scenario(MINI_V2)
    assert bounds["morale"] == (0, 100)
    assert bounds["cash"] == (None, None)
    assert bounds["sharePrice"] == (0, None)


def test_create_v2_uses_metric_openings():
    engine = MeridianScoringEngine()
    state = engine.create(MINI_V2, seed=3)
    assert state["kpis"] == {"sharePrice": 100, "cash": 50, "morale": 60}
    assert state["openingKpis"] == state["kpis"]
    assert state["scenarioId"] == "mini-v2"
    assert state["seed"] == 3


def test_v2_clamp_uses_metric_max(engine):
    state = engine.create(MINI_V2, seed=0)
    # Meridian apply still expects beats; this test only checks clamp helper
    # wired through bounds_from_scenario.
    bounds = bounds_from_scenario(MINI_V2)
    assert _clamp("morale", 200, bounds) == 100
    assert _clamp("cash", -10, bounds) == -10  # unbounded below


def test_v1_create_still_copies_kpis(engine, scenario):
    state = engine.create(scenario, seed=0)
    assert state["kpis"] == scenario["kpis"]
    assert "openingKpis" not in state or state["openingKpis"] == scenario["kpis"]


def test_factories_unknown_name_falls_back_to_deterministic(monkeypatch):
    monkeypatch.setenv("CARD_DEALER", "not-a-real-provider")
    dealer = create_card_dealer(scenario=MINI_V2)
    assert type(dealer).__name__ == "SeededCardDealer"


def test_card_dealer_does_not_mutate_state():
    dealer = create_card_dealer(scenario=MINI_V2)
    state = {
        "seed": 1,
        "kpis": {"sharePrice": 100, "cash": 50, "morale": 60},
        "flags": [],
        "playedFamilies": [],
        "playedCardIds": [],
        "pendingInterrupt": False,
    }
    snapshot = copy.deepcopy(state)
    ctx = {"quarter": 0, "focusMetrics": ["morale"], "interrupt": False}
    hand = dealer.deal(state, ctx)
    assert state == snapshot
    assert isinstance(hand, list)


def test_rival_policy_does_not_mutate_state():
    rival = create_rival_policy(scenario=MINI_V2)
    state = {"kpis": {"rivalPressure": 20}, "flags": []}
    snapshot = copy.deepcopy(state)
    result = rival.respond(state, {"id": "trust_campaign"})
    assert state == snapshot
    assert "heldOff" in result or "pressure" in result


def test_war_room_convene_does_not_mutate_state():
    provider = create_war_room_provider(scenario=MINI_V2)
    hand = [
        {"id": "trust_campaign", "deltas": {"morale": 5}},
        {"id": "cost_reset", "deltas": {"cash": 10}},
    ]
    state = {"kpis": {"morale": 60, "cash": 50}, "seed": 0}
    snapshot = copy.deepcopy(state)
    result = provider.convene(
        {"state": state, "quarter": 0, "news": "hi", "hand": hand, "interrupt": False}
    )
    assert state == snapshot
    assert "seats" in result
    assert "chair" in result


def test_scoring_model_close_out_does_not_mutate_state():
    model = create_scoring_model(scenario=MINI_V2)
    state = {
        "kpis": {"sharePrice": 110, "cash": 50, "morale": 60},
        "openingKpis": {"sharePrice": 100, "cash": 50, "morale": 60},
        "companyValue": 100,
        "outcome": "playing",
    }
    snapshot = copy.deepcopy(state)
    score = model.close_out(state)
    assert state == snapshot
    assert "composite" in score


def test_event_deck_draw_does_not_mutate_state():
    deck = create_event_deck(scenario=MINI_V2)
    state = {"seed": 4, "kpis": {}, "beatIndex": 0}
    snapshot = copy.deepcopy(state)
    event = deck.draw(state, 0)
    assert state == snapshot
    assert event["id"]
