"""Schema/content validation for meridian-activist-01.json against SPEC.md."""

from __future__ import annotations

KPI_KEYS = {"stockPrice", "boardResistance", "ownershipPct", "warChest", "mediaHeat"}
NPC_IDS = {"ceo", "cfo", "gc", "chair", "analyst", "partner"}
ZONE_IDS = {
    "lobby",
    "trading_floor",
    "war_room",
    "ceo_office",
    "cfo_office",
    "gc_office",
    "boardroom",
    "press_bay",
}


def _all_options(beat):
    if beat.get("curveball"):
        return [o for v in beat["variants"] for o in v["options"]]
    return beat["options"]


def test_top_level_shape(scenario):
    assert scenario["id"] == "meridian-activist-01"
    assert set(scenario["kpis"]) == KPI_KEYS
    assert set(scenario["npcs"]) == NPC_IDS
    assert set(scenario["zones"]) == ZONE_IDS
    assert scenario["winCondition"]["kpi"] in KPI_KEYS
    assert all(c["kpi"] in KPI_KEYS for c in scenario["loseConditions"])


def test_nine_beats_in_order(scenario):
    beats = scenario["beats"]
    assert len(beats) == 9
    assert [b["id"] for b in beats] == [f"beat-{i}" for i in range(1, 10)]
    assert [b["n"] for b in beats] == list(range(1, 10))


def test_beat_zone_and_npc_ids(scenario):
    for beat in scenario["beats"]:
        assert beat["zoneId"] in ZONE_IDS, beat["id"]
        assert beat["npcId"] in NPC_IDS, beat["id"]
        for line in beat["scriptedLines"]:
            assert line["speakerId"] in NPC_IDS, beat["id"]
        assert beat["situation"]
        assert beat["debateTopic"]


def test_plan_beat_locations(scenario):
    """Zones must match the 9-beat outline in the plan/SPEC."""
    expected = {
        "beat-1": "trading_floor",
        "beat-2": "ceo_office",
        "beat-3": "press_bay",
        "beat-4": "boardroom",
        "beat-5": "cfo_office",
        "beat-7": "boardroom",
        "beat-8": "war_room",
        "beat-9": "boardroom",
    }
    zones = {b["id"]: b["zoneId"] for b in scenario["beats"]}
    for beat_id, zone in expected.items():
        assert zones[beat_id] == zone


def test_option_counts_and_shape(scenario):
    for beat in scenario["beats"]:
        pools = (
            [v["options"] for v in beat["variants"]]
            if beat.get("curveball")
            else [beat["options"]]
        )
        for pool in pools:
            assert 2 <= len(pool) <= 4, beat["id"]
        for option in _all_options(beat):
            assert option["label"]
            assert option["pros"] and option["cons"]
            assert option["consequence"]
            assert set(option["deltas"]) <= KPI_KEYS
            assert isinstance(option["requires"], list)
            assert isinstance(option["unlocks"], list)


def test_option_ids_unique_across_scenario(scenario):
    ids = [o["id"] for b in scenario["beats"] for o in _all_options(b)]
    assert len(ids) == len(set(ids))


def test_exactly_one_curveball_with_variants(scenario):
    curveballs = [b for b in scenario["beats"] if b.get("curveball")]
    assert len(curveballs) == 1
    beat = curveballs[0]
    assert beat["id"] == "beat-6"
    assert len(beat["variants"]) >= 2
    for variant in beat["variants"]:
        assert variant["id"] and variant["title"] and variant["situation"]
        assert set(variant["eventDeltas"]) <= KPI_KEYS
        assert len(variant["options"]) >= 2


def test_every_beat_has_an_ungated_option(scenario):
    """No soft-locks: each beat (and each curveball variant) must offer at
    least one option with no ``requires`` flags."""
    for beat in scenario["beats"]:
        pools = (
            [v["options"] for v in beat["variants"]]
            if beat.get("curveball")
            else [beat["options"]]
        )
        for pool in pools:
            assert any(not o["requires"] for o in pool), beat["id"]


VOTERS = ("chair", "ceo", "cfo", "gc")


def test_boardroom_beats_have_authored_ballots(scenario):
    expected = {
        "beat-4": {"chair": "4b", "ceo": "4b", "cfo": "4a", "gc": "4b"},
        "beat-7": {"chair": "7a", "ceo": "7a", "cfo": "7a", "gc": "7b"},
        "beat-9": {"chair": "9c", "ceo": "9c", "cfo": "9c", "gc": "9c"},
    }
    by_id = {b["id"]: b for b in scenario["beats"]}
    for beat in scenario["beats"]:
        if beat["zoneId"] != "boardroom":
            assert "boardVote" not in beat
            continue
        vote = beat["boardVote"]
        assert list(vote["voters"]) == list(VOTERS)
        assert vote["ballots"] == expected[beat["id"]]
        option_ids = {o["id"] for o in beat["options"]}
        assert set(vote["ballots"].values()) <= option_ids
        assert by_id[beat["id"]]["zoneId"] == "boardroom"


def test_all_required_flags_are_unlockable(scenario):
    """Every flag referenced in ``requires`` is unlocked by some earlier beat."""
    unlocked: set[str] = set()
    for beat in scenario["beats"]:
        for option in _all_options(beat):
            for flag in option["requires"]:
                assert flag in unlocked, f"{beat['id']}/{option['id']}: {flag}"
        for option in _all_options(beat):
            unlocked.update(option["unlocks"])
