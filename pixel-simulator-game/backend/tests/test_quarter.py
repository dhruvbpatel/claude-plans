"""v2 quarter pipeline: start_quarter, knock-ons, settle, apply card."""

from __future__ import annotations

import pytest

from app.engine.scoring import MeridianScoringEngine


MINI = {
    "id": "mini-quarter",
    "schemaVersion": 2,
    "maxQuarters": 8,
    "metrics": [
        {"id": "sharePrice", "label": "Share price", "opening": 100, "min": 0, "group": "market"},
        {"id": "confidence", "label": "Confidence", "opening": 60, "min": 0, "max": 100, "group": "market"},
        {"id": "reputation", "label": "Reputation", "opening": 55, "min": 0, "max": 100, "group": "market"},
        {"id": "cash", "label": "Cash", "opening": 800, "group": "financial"},
        {"id": "debt", "label": "Debt", "opening": 300, "min": 0, "group": "financial"},
        {"id": "revenue", "label": "Revenue", "opening": 400, "min": 0, "group": "financial"},
        {"id": "margin", "label": "Margin", "opening": 12, "min": -20, "max": 80, "group": "financial"},
        {"id": "innovation", "label": "Innovation", "opening": 55, "min": 0, "max": 100, "group": "ops"},
        {"id": "marketShare", "label": "Market share", "opening": 18, "min": 0, "max": 100, "group": "ops"},
        {"id": "morale", "label": "Morale", "opening": 60, "min": 0, "max": 100, "group": "people"},
        {"id": "integrationRisk", "label": "Integration risk", "opening": 0, "min": 0, "max": 100, "group": "risk"},
        {"id": "regulatoryRisk", "label": "Regulatory risk", "opening": 20, "min": 0, "max": 100, "group": "risk"},
        {"id": "rivalPressure", "label": "Rival pressure", "opening": 20, "min": 0, "max": 100, "group": "campaign"},
    ],
    "cards": [
        {
            "id": "hurt_morale",
            "family": "people",
            "label": "Hurt morale",
            "pros": ["x"],
            "cons": ["y"],
            "deltas": {"morale": -25},
            "requires": [],
            "unlocks": [],
            "once": False,
            "consequence": "Morale slumps.",
        },
        {
            "id": "boost_innovation",
            "family": "product",
            "label": "Boost innovation",
            "pros": ["x"],
            "cons": ["y"],
            "deltas": {"innovation": 40},
            "requires": [],
            "unlocks": ["inorganic_live"],
            "once": False,
            "consequence": "Labs hum.",
        },
        {
            "id": "noop_cash",
            "family": "capital_return",
            "label": "Hold cash",
            "pros": ["x"],
            "cons": ["y"],
            "deltas": {"cash": 0},
            "requires": [],
            "unlocks": [],
            "once": False,
            "consequence": "Nothing moves.",
        },
        {
            "id": "integration_spike",
            "family": "inorganic",
            "label": "Spike integration",
            "pros": ["x"],
            "cons": ["y"],
            "deltas": {"integrationRisk": 30},
            "requires": [],
            "unlocks": ["inorganic_live"],
            "once": True,
            "consequence": "Systems collide.",
        },
    ],
    "knockOnRules": [
        {
            "id": "morale_collapse",
            "when": {"kpi": "morale", "lt": 40},
            "deltas": {"innovation": -6, "revenue": -40},
            "news": "Morale collapse hits innovation and revenue.",
        },
        {
            "id": "innovation_flywheel",
            "when": {"kpi": "innovation", "gte": 85},
            "deltas": {"confidence": 3},
            "news": "Innovation proof starts lifting confidence on its own.",
        },
        {
            "id": "integration_drag",
            "when": {"kpi": "integrationRisk", "gte": 25},
            "deltas": {"morale": -5, "margin": -0.8},
            "news": "Integration strain drags morale and margin.",
        },
    ],
    "eventDeck": [
        {
            "id": "q0",
            "title": "Q0 news",
            "news": "Opening headline.",
            "quarterMin": 0,
            "quarterMax": 0,
            "focusMetrics": ["morale"],
            "deltas": {},
        }
    ],
    "rival": {"threshold": 55, "defaultPressureDelta": 6, "attacks": []},
    "scoring": {
        "winAt": 110,
        "weights": {
            "sharePrice": 40,
            "companyValue": 20,
            "confidence": 15,
            "morale": 10,
            "innovation": 10,
            "reputation": 5,
        },
        "earlyFailure": [
            {"id": "cash", "kpi": "cash", "lt": 0},
            {"id": "price_collapse", "kpi": "sharePrice", "ltRatioOfOpening": 0.40},
            {"id": "confidence", "kpi": "confidence", "lt": 15},
        ],
        "settle": {
            "interestRateAnnual": 0.05,
            "evMultiple": 8,
            "confidenceToPrice": 0.15,
            "valueToPrice": 0.10,
        },
    },
    "warRoom": {"chair": "chair", "seats": []},
    "npcs": ["chair"],
    "zones": ["war_room"],
}


def _hand(engine, seed, card_id):
    state = engine.start_quarter(engine.create(MINI, seed=seed))
    others = [c["id"] for c in MINI["cards"] if c["id"] != card_id][:2]
    state["hand"] = [card_id, *others]
    return state


def test_start_quarter_deals_hand_and_records_news():
    engine = MeridianScoringEngine()
    state = engine.create(MINI, seed=1)
    assert state.get("hand") in (None, [])
    prepared = engine.start_quarter(state)
    assert state.get("hand") in (None, [])
    assert len(prepared["hand"]) == 3
    assert prepared["lastNews"] == "Opening headline."
    assert engine.available_options(prepared)
    assert all("deltas" in o for o in engine.available_options(prepared))


def test_morale_collapse_knock_on():
    engine = MeridianScoringEngine()
    state = _hand(engine, 0, "hurt_morale")
    before_rev = state["kpis"]["revenue"]
    before_inn = state["kpis"]["innovation"]
    after = engine.apply(state, "hurt_morale")
    # morale 60-25=35 < 40 → innovation -6, revenue -40 (then settle may also move cash)
    assert after["kpis"]["morale"] == pytest.approx(35)
    assert after["kpis"]["innovation"] == pytest.approx(before_inn - 6)
    assert after["kpis"]["revenue"] == pytest.approx(before_rev - 40)
    assert any(h.get("knockOns") for h in after["history"])


def test_innovation_flywheel_knock_on():
    engine = MeridianScoringEngine()
    state = _hand(engine, 0, "boost_innovation")
    before = state["kpis"]["confidence"]
    after = engine.apply(state, "boost_innovation")
    assert after["kpis"]["innovation"] >= 85
    assert after["kpis"]["confidence"] == pytest.approx(before + 3)
    assert "inorganic_live" in after["flags"]


def test_integration_drag_knock_on():
    engine = MeridianScoringEngine()
    state = _hand(engine, 0, "integration_spike")
    after = engine.apply(state, "integration_spike")
    assert after["kpis"]["integrationRisk"] >= 25
    assert after["kpis"]["morale"] == pytest.approx(55)  # 60 - 5
    assert after["kpis"]["margin"] == pytest.approx(11.2)  # 12 - 0.8
    assert "integration_spike" in after["playedCardIds"]


def test_settle_adds_ebitda_minus_interest_to_cash():
    engine = MeridianScoringEngine()
    state = _hand(engine, 0, "noop_cash")
    cash_before = state["kpis"]["cash"]
    # noop card: ebitda = 400 * 0.12 = 48; interest = 300 * 0.05 / 4 = 3.75
    after = engine.apply(state, "noop_cash")
    assert after["kpis"]["cash"] == pytest.approx(cash_before + 48 - 3.75)
    assert after["companyValue"] > 0
    assert after["beatIndex"] == 1
    assert after["hand"] == []


def test_apply_does_not_mutate_input():
    engine = MeridianScoringEngine()
    state = _hand(engine, 0, "noop_cash")
    beat = state["beatIndex"]
    engine.apply(state, "noop_cash")
    assert state["beatIndex"] == beat
    assert state["hand"]
