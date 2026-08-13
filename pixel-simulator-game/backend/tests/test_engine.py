"""MeridianScoringEngine unit tests: deltas, gates, win/lose, curveball, full runs."""

from __future__ import annotations

import random

import pytest

# Canonical paths through the shipped scenario (option ids per beat 1-9;
# beat 6 is the curveball and gets resolved dynamically in the helpers).
PROXY_PATH = ["1a", "2a", "3a", "4b", "5b", None, "7b", "8a", "9a"]
SETTLEMENT_PATH = ["1a", "2a", "3b", "4a", "5a", None, "7a", "8b", "9b"]


def play(engine, scenario, path, seed=0, curveball_pick="first"):
    """Apply a scripted path; ``None`` entries pick a curveball option."""
    state = engine.create(scenario, seed=seed)
    for option_id in path:
        if state["outcome"] != "playing":
            break
        if option_id is None:
            options = engine.available_options(state)
            if curveball_pick == "min_stock":
                option_id = min(
                    options, key=lambda o: o["deltas"].get("stockPrice", 0)
                )["id"]
            else:
                option_id = options[0]["id"]
        state = engine.apply(state, option_id)
    return state


# -- create ----------------------------------------------------------------


def test_create_initial_state(engine, scenario):
    state = engine.create(scenario, seed=7)
    assert state["scenarioId"] == "meridian-activist-01"
    assert state["phase"] == "EXPLORE"
    assert state["beatIndex"] == 0
    assert state["kpis"] == scenario["kpis"]
    assert state["flags"] == []
    assert state["history"] == []
    assert state["outcome"] == "playing"
    assert state["seed"] == 7
    assert state["curveballVariantId"] in {
        v["id"] for b in scenario["beats"] if b.get("curveball") for v in b["variants"]
    }


# -- delta application -----------------------------------------------------


def test_apply_deltas_from_scenario(engine, scenario):
    state = engine.create(scenario, seed=0)
    new = engine.apply(state, "1a")
    d = scenario["beats"][0]["options"][0]["deltas"]
    for kpi, delta in d.items():
        assert new["kpis"][kpi] == pytest.approx(scenario["kpis"][kpi] + delta)
    assert new["beatIndex"] == 1
    assert new["flags"] == ["stake_built"]
    assert len(new["history"]) == 1
    assert new["history"][0]["optionId"] == "1a"
    assert new["history"][0]["consequence"]


def test_apply_does_not_mutate_input_state(engine, scenario):
    state = engine.create(scenario, seed=0)
    before = {**state, "kpis": dict(state["kpis"]), "flags": list(state["flags"])}
    engine.apply(state, "1a")
    assert state["kpis"] == before["kpis"]
    assert state["beatIndex"] == 0
    assert state["flags"] == []
    assert state["history"] == []


def test_kpi_clamping(engine):
    mini = {
        "id": "mini-clamp",
        "kpis": {
            "stockPrice": 42.0,
            "boardResistance": 55,
            "ownershipPct": 6.5,
            "warChest": 120,
            "mediaHeat": 95,
        },
        "winCondition": {"kpi": "stockPrice", "gte": 60},
        "loseConditions": [{"kpi": "boardResistance", "gte": 100}],
        "beats": [
            {
                "id": "b1",
                "curveball": False,
                "options": [
                    {
                        "id": "x",
                        "label": "x",
                        "deltas": {"mediaHeat": 50, "boardResistance": -80},
                        "requires": [],
                        "unlocks": [],
                    }
                ],
            }
        ],
    }
    state = engine.create(mini)
    new = engine.apply(state, "x")
    assert new["kpis"]["mediaHeat"] == 100  # clamped at ceiling
    assert new["kpis"]["boardResistance"] == 0  # clamped at floor


# -- flag gates ------------------------------------------------------------


def test_gated_option_hidden_and_rejected(engine, scenario):
    # Beat 3's "hold fire" (3c) requires private_diplomacy, unlocked only by 2a.
    state = engine.create(scenario, seed=0)
    state = engine.apply(state, "1a")
    state = engine.apply(state, "2b")  # hardline, not private_diplomacy

    ids = {o["id"] for o in engine.available_options(state)}
    assert ids == {"3a", "3b"}
    with pytest.raises(ValueError, match="gated"):
        engine.apply(state, "3c")


def test_unlock_opens_gated_option(engine, scenario):
    state = engine.create(scenario, seed=0)
    state = engine.apply(state, "1a")
    state = engine.apply(state, "2a")  # unlocks private_diplomacy

    assert "private_diplomacy" in state["flags"]
    ids = {o["id"] for o in engine.available_options(state)}
    assert "3c" in ids


def test_unknown_option_rejected(engine, scenario):
    state = engine.create(scenario, seed=0)
    with pytest.raises(ValueError, match="unknown option"):
        engine.apply(state, "9z")


def test_every_beat_reachable_without_flags(engine, scenario):
    """No soft-lock: at least one option must be available at every beat."""
    state = engine.create(scenario, seed=0)
    while state["outcome"] == "playing":
        options = engine.available_options(state)
        assert options, f"no options available at beatIndex {state['beatIndex']}"
        # Always take an ungated option to simulate the least-flagged run.
        ungated = [o for o in options if not o.get("requires")]
        assert ungated, f"beatIndex {state['beatIndex']} has only gated options"
        state = engine.apply(state, ungated[0]["id"])


# -- win / lose ------------------------------------------------------------


@pytest.mark.parametrize("seed", range(6))
def test_proxy_path_wins_any_seed(engine, scenario, seed):
    state = play(engine, scenario, PROXY_PATH, seed=seed)
    assert state["outcome"] == "won"
    assert state["kpis"]["stockPrice"] >= 60
    assert state["phase"] == "GAME_END"
    assert state["beatIndex"] == 9


@pytest.mark.parametrize("seed", range(6))
def test_settlement_path_wins_any_seed(engine, scenario, seed):
    state = play(engine, scenario, SETTLEMENT_PATH, seed=seed)
    assert state["outcome"] == "won"
    assert state["kpis"]["stockPrice"] >= 60


def test_max_aggression_loses_on_board_resistance(engine, scenario):
    state = play(engine, scenario, ["1c", "2b", "3a", "4c", "5b"], seed=0)
    assert state["outcome"] == "lost"
    assert state["kpis"]["boardResistance"] >= 100
    assert state["phase"] == "GAME_END"
    assert state["beatIndex"] == 5  # ended mid-campaign, before the curveball
    assert engine.available_options(state) == []
    with pytest.raises(ValueError, match="already ended"):
        engine.apply(state, "7a")


def test_passive_path_falls_short_of_target(engine, scenario):
    # Pin a seed whose curveball is the earnings miss so the weak run is
    # deterministic; the timid path then cannot reach stockPrice 60.
    seed = next(
        s
        for s in range(100)
        if engine.create(scenario, seed=s)["curveballVariantId"] == "cv-earnings-miss"
    )
    path = ["1b", "2c", "3b", "4b", "5c", None, "7b", "8b", "9c"]
    state = play(engine, scenario, path, seed=seed, curveball_pick="min_stock")
    assert state["outcome"] == "lost"
    assert state["kpis"]["stockPrice"] < 60
    assert state["beatIndex"] == 9  # finished the campaign but missed the target


def test_war_chest_depletion_loses(engine):
    mini = {
        "id": "mini-warchest",
        "kpis": {
            "stockPrice": 42.0,
            "boardResistance": 55,
            "ownershipPct": 6.5,
            "warChest": 10,
            "mediaHeat": 20,
        },
        "winCondition": {"kpi": "stockPrice", "gte": 60},
        "loseConditions": [
            {"kpi": "boardResistance", "gte": 100},
            {"kpi": "warChest", "lte": 0},
        ],
        "beats": [
            {
                "id": "b1",
                "curveball": False,
                "options": [
                    {
                        "id": "burn",
                        "label": "burn",
                        "deltas": {"warChest": -10},
                        "requires": [],
                        "unlocks": [],
                    }
                ],
            },
            {"id": "b2", "curveball": False, "options": []},
        ],
    }
    state = engine.create(mini)
    state = engine.apply(state, "burn")
    assert state["kpis"]["warChest"] == 0
    assert state["outcome"] == "lost"


# -- seeded curveball ------------------------------------------------------


def test_curveball_same_seed_reproduces_run(engine, scenario):
    a = play(engine, scenario, PROXY_PATH, seed=1234)
    b = play(engine, scenario, PROXY_PATH, seed=1234)
    assert a == b
    assert a["curveballVariantId"] == b["curveballVariantId"]


def test_curveball_seed_covers_all_variants(engine, scenario):
    variants = {
        engine.create(scenario, seed=s)["curveballVariantId"] for s in range(30)
    }
    expected = {
        v["id"] for b in scenario["beats"] if b.get("curveball") for v in b["variants"]
    }
    assert variants == expected


def test_curveball_event_deltas_applied(engine, scenario):
    state = engine.create(scenario, seed=0)
    for option_id in PROXY_PATH[:5]:
        state = engine.apply(state, option_id)

    beat6 = scenario["beats"][5]
    assert beat6["curveball"] is True
    variant = next(
        v for v in beat6["variants"] if v["id"] == state["curveballVariantId"]
    )
    option = variant["options"][0]

    from app.engine.scoring import _clamp

    before = dict(state["kpis"])
    after = engine.apply(state, option["id"])
    for kpi in before:
        raw = (
            before[kpi]
            + variant.get("eventDeltas", {}).get(kpi, 0)
            + option["deltas"].get(kpi, 0)
        )
        assert after["kpis"][kpi] == pytest.approx(_clamp(kpi, raw))

    entry = after["history"][-1]
    assert entry["eventDeltas"] == variant["eventDeltas"]
    assert entry["curveballVariantId"] == variant["id"]


# -- summary / scorecard ---------------------------------------------------


def test_summary_won_grades(engine, scenario):
    state = play(engine, scenario, PROXY_PATH, seed=0)
    s = engine.summary(state)
    assert s["outcome"] == "won"
    assert s["grade"] in {"A", "B", "C"}
    assert s["beatIndex"] == 9
    assert len(s["history"]) == 9
    assert s["kpis"] == state["kpis"]


def test_summary_lost_grades(engine, scenario):
    state = play(engine, scenario, ["1c", "2b", "3a", "4c", "5b"], seed=0)
    assert engine.summary(state)["grade"] == "F"  # lose condition blowout


def test_summary_in_progress(engine, scenario):
    state = engine.create(scenario, seed=0)
    assert engine.summary(state)["grade"] == "-"
    assert engine.summary(state)["outcome"] == "playing"


# -- headless full runs ----------------------------------------------------


@pytest.mark.parametrize("seed", range(10))
def test_headless_random_full_run(engine, scenario, seed):
    """A seeded random walk always terminates with a definite outcome."""
    rng = random.Random(seed)
    state = engine.create(scenario, seed=seed)
    applies = 0
    while state["outcome"] == "playing":
        options = engine.available_options(state)
        assert options
        state = engine.apply(state, rng.choice(options)["id"])
        applies += 1
        assert applies <= 9

    assert state["outcome"] in {"won", "lost"}
    assert state["phase"] == "GAME_END"
    assert len(state["history"]) == applies
    summary = engine.summary(state)
    assert summary["grade"] in {"A", "B", "C", "D", "F"}
    # Replaying the identical walk reproduces the identical end state.
    rng2 = random.Random(seed)
    replay = engine.create(scenario, seed=seed)
    while replay["outcome"] == "playing":
        replay = engine.apply(
            replay, rng2.choice(engine.available_options(replay))["id"]
        )
    assert replay == state
