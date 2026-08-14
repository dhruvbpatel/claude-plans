"""Rival pressure-gauge policy and seeded event-deck replay."""

from __future__ import annotations

from app.engine.events import SeededEventDeck
from app.engine.rival import DeterministicRival


def _rival(threshold=55, **kwargs):
    cfg = {
        "threshold": threshold,
        "defaultPressureDelta": 6,
        "cardPressure": {"acquire_challenger": -8, "retention_package": -4},
        "holdOffNews": "holds",
        "attacks": [
            {
                "id": "injunction",
                "deltas": {"confidence": -5, "reputation": -3},
                "news": "injunction",
                "interrupt": False,
            },
            {
                "id": "nominate_slate",
                "deltas": {},
                "news": "slate",
                "interrupt": True,
                "interruptCardId": "leadership_renewal",
            },
        ],
        "secondaryTriggers": [{"kpi": "confidence", "lt": 45, "attackId": "injunction"}],
    }
    cfg.update(kwargs)
    return DeterministicRival(scenario={"rival": cfg})


def test_pressure_climbs_and_holds_below_threshold():
    rival = _rival()
    state = {"kpis": {"rivalPressure": 20, "confidence": 60}, "firedAttackIds": []}
    resp = rival.respond(state, {"id": "trust_campaign"})
    assert resp["heldOff"] is True
    assert resp["pressure"] == 26
    assert resp["attackId"] is None


def test_acquire_challenger_cools_pressure():
    rival = _rival()
    state = {"kpis": {"rivalPressure": 39, "confidence": 60}, "firedAttackIds": []}
    resp = rival.respond(state, {"id": "acquire_challenger"})
    assert resp["pressure"] == 31
    assert resp["heldOff"] is True


def test_threshold_fires_first_unused_attack():
    rival = _rival()
    state = {"kpis": {"rivalPressure": 50, "confidence": 60}, "firedAttackIds": []}
    resp = rival.respond(state, {"id": "trust_campaign"})  # +6 default → 56
    assert resp["heldOff"] is False
    assert resp["attackId"] == "injunction"
    assert resp["deltas"]["confidence"] == -5
    assert resp["interrupt"] is False


def test_attacks_do_not_repeat():
    rival = _rival()
    state = {
        "kpis": {"rivalPressure": 60, "confidence": 60},
        "firedAttackIds": ["injunction"],
    }
    resp = rival.respond(state, {"id": "cost_reset"})
    assert resp["attackId"] == "nominate_slate"
    assert resp["interrupt"] is True
    assert resp["interruptCardId"] == "leadership_renewal"


def test_secondary_trigger_fires_when_confidence_low():
    rival = _rival()
    state = {"kpis": {"rivalPressure": 20, "confidence": 40}, "firedAttackIds": []}
    resp = rival.respond(state, {"id": "share_buyback"})
    assert resp["attackId"] == "injunction"


def test_event_deck_same_seed_same_sequence():
    scenario = {
        "eventDeck": [
            {"id": "a", "news": "A", "quarterMin": 0, "quarterMax": 7},
            {"id": "b", "news": "B", "quarterMin": 0, "quarterMax": 7},
            {"id": "c", "news": "C", "quarterMin": 0, "quarterMax": 7},
        ]
    }
    deck = SeededEventDeck(scenario=scenario)
    ids_a = [deck.draw({"seed": 8}, q)["id"] for q in range(3)]
    ids_b = [deck.draw({"seed": 8}, q)["id"] for q in range(3)]
    assert ids_a == ids_b
    assert len(set(ids_a)) == 3
