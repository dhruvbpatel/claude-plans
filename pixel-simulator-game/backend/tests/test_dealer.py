"""Seeded CardDealer: unused-family, situation weights, interrupt 4th, replay."""

from __future__ import annotations

import copy

from app.engine.dealer import SeededCardDealer

CARDS = [
    {"id": "a1", "family": "fa", "deltas": {"morale": 1}, "requires": [], "once": False},
    {"id": "a2", "family": "fa", "deltas": {"cash": 1}, "requires": [], "once": False},
    {"id": "b1", "family": "fb", "deltas": {"innovation": 1}, "requires": [], "once": False},
    {"id": "b2", "family": "fb", "deltas": {"sharePrice": 1}, "requires": [], "once": False},
    {"id": "c1", "family": "fc", "deltas": {"morale": 5}, "requires": [], "once": False},
    {"id": "c2", "family": "fc", "deltas": {"debt": 1}, "requires": [], "once": False},
    {"id": "once_x", "family": "fd", "deltas": {"cash": 1}, "requires": [], "once": True},
    {"id": "gated", "family": "fe", "deltas": {"cash": 1}, "requires": ["need_flag"], "once": False},
]


def _dealer():
    return SeededCardDealer(scenario={"cards": CARDS})


def _state(**kwargs):
    base = {
        "seed": 11,
        "flags": [],
        "playedCardIds": [],
        "playedFamilies": [],
        "kpis": {},
    }
    base.update(kwargs)
    return base


def test_deal_three_cards_by_default():
    hand = _dealer().deal(_state(), {"quarter": 0, "focusMetrics": [], "interrupt": False})
    assert len(hand) == 3
    assert len(set(hand)) == 3


def test_interrupt_deals_four_including_forced_card():
    hand = _dealer().deal(
        _state(),
        {
            "quarter": 0,
            "focusMetrics": [],
            "interrupt": True,
            "interruptCardId": "c1",
        },
    )
    assert len(hand) == 4
    assert "c1" in hand


def test_same_seed_and_quarter_reproduces_hand():
    ctx = {"quarter": 2, "focusMetrics": ["morale"], "interrupt": False}
    a = _dealer().deal(_state(seed=42), ctx)
    b = _dealer().deal(_state(seed=42), ctx)
    assert a == b


def test_unused_family_forced_into_hand():
    state = _state(playedFamilies=["fa", "fb", "fc"])
    hand = _dealer().deal(state, {"quarter": 1, "focusMetrics": [], "interrupt": False})
    families = {c["family"] for c in CARDS if c["id"] in hand}
    assert "fd" in families or "fe" in families


def test_once_and_requires_exclude_cards():
    state = _state(playedCardIds=["once_x"], flags=[])
    hand = _dealer().deal(state, {"quarter": 0, "focusMetrics": [], "interrupt": False})
    assert "once_x" not in hand
    assert "gated" not in hand


def test_deal_does_not_mutate_state():
    state = _state()
    snap = copy.deepcopy(state)
    _dealer().deal(state, {"quarter": 0, "focusMetrics": ["morale"], "interrupt": False})
    assert state == snap
