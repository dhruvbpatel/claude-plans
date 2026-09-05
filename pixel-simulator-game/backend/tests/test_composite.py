"""Weighted composite scoring: ratios, bands, early failure."""

from __future__ import annotations

import pytest

from app.engine.composite import WeightedComposite


SCORING = {
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
}


def _model():
    return WeightedComposite(scenario={"scoring": SCORING})


def test_worked_example_clears_win_at():
    # Spec close-out illustration ≈ 111.6
    state = {
        "kpis": {
            "sharePrice": 108,
            "confidence": 63,  # 105% of 60
            "morale": 55.8,  # 93% of 60
            "innovation": 82.5,  # 150% of 55
            "reputation": 64.9,  # 118% of 55
            "cash": 800,
        },
        "openingKpis": {
            "sharePrice": 100,
            "confidence": 60,
            "morale": 60,
            "innovation": 55,
            "reputation": 55,
        },
        "companyValue": 112,
        "openingCompanyValue": 100,
    }
    score = _model().close_out(state)
    assert score["composite"] == pytest.approx(111.6, abs=0.2)
    assert score["outcome"] == "won"
    assert score["band"] in {"constructive", "pyrrhic"}


def test_cash_below_zero_is_early_failure():
    state = {
        "kpis": {"cash": -1, "sharePrice": 100, "confidence": 60},
        "openingKpis": {"cash": 800, "sharePrice": 100, "confidence": 60},
    }
    assert _model().early_failure(state) == "cash"
    score = _model().close_out(state)
    assert score["outcome"] == "lost"
    assert score["band"] == "failed"
    assert score["failedOn"] == "cash"


def test_share_price_collapse_is_early_failure():
    state = {
        "kpis": {"cash": 100, "sharePrice": 39, "confidence": 60},
        "openingKpis": {"cash": 800, "sharePrice": 100, "confidence": 60},
    }
    assert _model().early_failure(state) == "price_collapse"


def test_pyrrhic_when_host_is_damaged():
    state = {
        "kpis": {
            "sharePrice": 130,
            "confidence": 80,
            "morale": 40,  # 67% of 60
            "innovation": 40,  # 73% of 55
            "reputation": 55,
        },
        "openingKpis": {
            "sharePrice": 100,
            "confidence": 60,
            "morale": 60,
            "innovation": 55,
            "reputation": 55,
        },
        "companyValue": 130,
        "openingCompanyValue": 100,
    }
    score = _model().close_out(state)
    assert score["composite"] >= 110
    assert score["band"] == "pyrrhic"
    assert score["outcome"] == "won"
