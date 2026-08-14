"""Deterministic 6-seat war room: ownership votes, chair, forced dissent."""

from __future__ import annotations

from app.engine.war_room import DeterministicWarRoom

HAND = [
    {"id": "trust_campaign", "label": "PR", "deltas": {"reputation": 5, "confidence": 4, "cash": -25}},
    {"id": "debt_paydown", "label": "Debt", "deltas": {"cash": -100, "debt": -100, "confidence": 1}},
    {"id": "product_bet", "label": "Product", "deltas": {"innovation": 12, "cash": -150, "margin": -1}},
]

SEATS = [
    {"id": "cfo", "name": "CFO", "owns": ["cash", "debt", "margin", "sharePrice"]},
    {"id": "operator", "name": "Operating Partner", "owns": ["revenue", "marketShare"]},
    {"id": "cto", "name": "Research / CTO", "owns": ["innovation", "integrationRisk"]},
    {"id": "hr", "name": "Talent / HR", "owns": ["morale"]},
    {"id": "gc", "name": "Governance Counsel", "owns": ["regulatoryRisk"]},
    {"id": "comms", "name": "Communications Lead", "owns": ["reputation"]},
]


def _convene(hand=None):
    provider = DeterministicWarRoom(
        scenario={"warRoom": {"chair": "chair", "seats": SEATS}}
    )
    return provider.convene(
        {
            "state": {"kpis": {}, "seed": 0},
            "quarter": 0,
            "news": "headline",
            "hand": hand or HAND,
            "interrupt": False,
        }
    )


def test_six_seats_and_tally_sums_to_six():
    result = _convene()
    assert len(result["seats"]) == 6
    assert sum(result["chair"]["tally"].values()) == 6


def test_cto_prefers_product_bet():
    result = _convene()
    cto = next(s for s in result["seats"] if s["seatId"] == "cto")
    assert cto["preferredCardId"] == "product_bet"


def test_comms_prefers_trust_campaign():
    result = _convene()
    comms = next(s for s in result["seats"] if s["seatId"] == "comms")
    assert comms["preferredCardId"] == "trust_campaign"


def test_never_unanimous():
    # One card is a clear winner on cash for everyone if we only offer buybacks
    # that don't touch owned metrics — force a unanimous first pass with one
    # universally empty-delta dummy plus a second card.
    hand = [
        {"id": "alpha", "label": "A", "deltas": {"reputation": 10}},
        {"id": "beta", "label": "B", "deltas": {"reputation": 1}},
    ]
    result = _convene(hand)
    prefs = {s["preferredCardId"] for s in result["seats"]}
    assert len(prefs) >= 2
    assert result["chair"]["dissents"]


def test_recommended_card_is_in_the_hand():
    result = _convene()
    assert result["chair"]["recommendedCardId"] in {c["id"] for c in HAND}


def test_convene_does_not_write_kpis():
    state = {"kpis": {"cash": 800}, "seed": 1}
    provider = DeterministicWarRoom(scenario={"warRoom": {"seats": SEATS}})
    provider.convene({"state": state, "hand": HAND, "quarter": 0, "news": ""})
    assert state["kpis"]["cash"] == 800
