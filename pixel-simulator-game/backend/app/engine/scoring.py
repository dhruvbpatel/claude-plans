"""MeridianScoringEngine — pure, deterministic scoring state machine (Phase 2).

Implements the ``ScoringEngine`` protocol from ``app.engine.protocols``:

    create(scenario, seed=0)      -> GameState
    available_options(state)      -> list[Option]   (requires-flag filtered)
    apply(state, option_id)       -> GameState      (new state; input untouched)
    summary(state)                -> Summary        (scorecard data)

Rules:
- No LLM involvement: all KPI math comes from authored ``deltas`` in the
  scenario JSON.
- The curveball beat (``"curveball": true``) carries ``variants``; one variant
  is picked deterministically from the session seed at ``create`` time and
  stored on the state as ``curveballVariantId``. Its ``eventDeltas`` are
  applied before the chosen option's deltas on that beat.
- Lose conditions are checked after every apply; the win condition is checked
  once the final beat has been applied. Lose takes precedence over win.
"""

from __future__ import annotations

import copy
import random
from typing import Any

from app.engine.metrics import V1_BOUNDS, bounds_from_scenario, openings_from_scenario, schema_version
from app.engine.protocols import GameState, Option, Scenario, Summary

KPI_KEYS = ("stockPrice", "boardResistance", "ownershipPct", "warChest", "mediaHeat")
KPI_BOUNDS = V1_BOUNDS

OUTCOME_PLAYING = "playing"
OUTCOME_WON = "won"
OUTCOME_LOST = "lost"

# Once-per-beat lobby bonus (Phase 6): working the lobby between beats tops up
# the war chest a little. Authored + deterministic, applied via
# ``apply_lobby_bonus`` — never touches the stock-price balance.
LOBBY_BONUS_DELTAS: dict[str, float] = {"warChest": 5.0}
LOBBY_BONUS_NEWS = (
    "Lobby chatter pays off: a friendly LP tops up the war chest (+$5M)."
)


def _clamp(
    kpi: str,
    value: float,
    bounds: dict[str, tuple[float | None, float | None]] | None = None,
) -> float:
    table = bounds if bounds is not None else KPI_BOUNDS
    lo, hi = table.get(kpi, (None, None))
    if lo is not None:
        value = max(lo, value)
    if hi is not None:
        value = min(hi, value)
    return round(value, 2)


class MeridianScoringEngine:
    """Deterministic authored-delta scoring engine for activist scenarios."""

    def __init__(self) -> None:
        self._scenarios: dict[str, Scenario] = {}

    # -- protocol ------------------------------------------------------------

    def create(self, scenario: Scenario, seed: int = 0) -> GameState:
        scenario_id = scenario["id"]
        self._scenarios[scenario_id] = scenario

        kpis = openings_from_scenario(scenario)
        state: GameState = {
            "scenarioId": scenario_id,
            "phase": "EXPLORE",
            "beatIndex": 0,
            "kpis": dict(kpis),
            "flags": [],
            "history": [],
            "seed": seed,
            "outcome": OUTCOME_PLAYING,
        }
        if schema_version(scenario) == 2:
            state["openingKpis"] = dict(kpis)

        variant_id = self._pick_curveball_variant(scenario, seed)
        if variant_id is not None:
            state["curveballVariantId"] = variant_id
        return state

    def available_options(self, state: GameState) -> list[Option]:
        if state.get("outcome", OUTCOME_PLAYING) != OUTCOME_PLAYING:
            return []
        beat = self._current_beat(state)
        if beat is None:
            return []
        flags = set(state.get("flags", []))
        options = self._beat_options(state, beat)
        return [o for o in options if set(o.get("requires", [])) <= flags]

    def apply(self, state: GameState, option_id: str) -> GameState:
        if state.get("outcome", OUTCOME_PLAYING) != OUTCOME_PLAYING:
            raise ValueError("game already ended; cannot apply further options")

        beat = self._current_beat(state)
        if beat is None:
            raise ValueError("no current beat to apply an option to")

        option = next(
            (o for o in self._beat_options(state, beat) if o["id"] == option_id),
            None,
        )
        if option is None:
            raise ValueError(f"unknown option {option_id!r} for beat {beat['id']!r}")
        missing = set(option.get("requires", [])) - set(state.get("flags", []))
        if missing:
            raise ValueError(
                f"option {option_id!r} gated by missing flags: {sorted(missing)}"
            )

        new_state: GameState = copy.deepcopy(state)
        scenario = self._scenario_for(state)
        bounds = bounds_from_scenario(scenario)
        kpis: dict[str, float] = dict(new_state["kpis"])  # type: ignore[arg-type]

        event_deltas: dict[str, float] = {}
        if beat.get("curveball"):
            variant = self._selected_variant(state, beat)
            event_deltas = dict(variant.get("eventDeltas", {}))
            for kpi, delta in event_deltas.items():
                kpis[kpi] = _clamp(kpi, kpis[kpi] + delta, bounds)

        for kpi, delta in option.get("deltas", {}).items():
            kpis[kpi] = _clamp(kpi, kpis.get(kpi, 0) + delta, bounds)

        new_state["kpis"] = kpis  # type: ignore[typeddict-item]

        for flag in option.get("unlocks", []):
            if flag not in new_state["flags"]:
                new_state["flags"].append(flag)

        entry: dict[str, Any] = {
            "beatId": beat["id"],
            "beatIndex": state["beatIndex"],
            "optionId": option["id"],
            "label": option.get("label", ""),
            "deltas": dict(option.get("deltas", {})),
            "consequence": option.get("consequence", ""),
            "kpis": dict(kpis),
        }
        if event_deltas:
            entry["eventDeltas"] = event_deltas
            entry["curveballVariantId"] = state.get("curveballVariantId")
        new_state["history"].append(entry)

        new_state["beatIndex"] = state["beatIndex"] + 1
        new_state["outcome"] = self._determine_outcome(scenario, new_state)
        new_state["phase"] = (
            "GAME_END" if new_state["outcome"] != OUTCOME_PLAYING else "EXPLORE"
        )
        return new_state

    def apply_lobby_bonus(self, state: GameState) -> GameState | None:
        """Grant the once-per-beat lobby bonus, or ``None`` if unavailable.

        Available while the game is still playing and the bonus has not been
        claimed for the current ``beatIndex``. Returns a new state (input
        untouched), like ``apply``. Deterministic: fixed authored deltas.
        """
        if state.get("outcome", OUTCOME_PLAYING) != OUTCOME_PLAYING:
            return None
        claimed = state.get("lobbyClaimedBeats", [])
        if state["beatIndex"] in claimed:
            return None

        new_state: GameState = copy.deepcopy(state)
        bounds = bounds_from_scenario(self._scenario_for(state))
        kpis: dict[str, float] = dict(new_state["kpis"])  # type: ignore[arg-type]
        for kpi, delta in LOBBY_BONUS_DELTAS.items():
            kpis[kpi] = _clamp(kpi, kpis[kpi] + delta, bounds)
        new_state["kpis"] = kpis  # type: ignore[typeddict-item]
        new_state["lobbyClaimedBeats"] = [*claimed, state["beatIndex"]]
        return new_state

    def summary(self, state: GameState) -> Summary:
        return {
            "beatIndex": state["beatIndex"],
            "kpis": dict(state["kpis"]),  # type: ignore[typeddict-item]
            "history": list(state.get("history", [])),
            "outcome": state.get("outcome", OUTCOME_PLAYING),
            "grade": self._grade(self._scenario_for(state), state),
        }

    # -- internals -----------------------------------------------------------

    def _scenario_for(self, state: GameState) -> Scenario:
        scenario_id = state["scenarioId"]
        if scenario_id not in self._scenarios:
            raise KeyError(
                f"scenario {scenario_id!r} not registered; call create() first"
            )
        return self._scenarios[scenario_id]

    def _current_beat(self, state: GameState) -> dict[str, Any] | None:
        beats = self._scenario_for(state).get("beats") or []
        index = state["beatIndex"]
        if index >= len(beats):
            return None
        return beats[index]

    def _beat_options(self, state: GameState, beat: dict[str, Any]) -> list[Option]:
        if beat.get("curveball"):
            return self._selected_variant(state, beat)["options"]
        return beat["options"]

    @staticmethod
    def _pick_curveball_variant(scenario: Scenario, seed: int) -> str | None:
        for beat in scenario.get("beats") or []:
            if beat.get("curveball"):
                variants = beat["variants"]
                return variants[random.Random(seed).randrange(len(variants))]["id"]
        return None

    def _selected_variant(
        self, state: GameState, beat: dict[str, Any]
    ) -> dict[str, Any]:
        variant_id = state.get("curveballVariantId")
        for variant in beat["variants"]:
            if variant["id"] == variant_id:
                return variant
        raise KeyError(f"curveball variant {variant_id!r} not found in {beat['id']!r}")

    @staticmethod
    def _condition_met(kpis: dict[str, float], cond: dict[str, Any]) -> bool:
        value = kpis[cond["kpi"]]
        if "gte" in cond and value >= cond["gte"]:
            return True
        if "lte" in cond and value <= cond["lte"]:
            return True
        return False

    def _determine_outcome(self, scenario: Scenario, state: GameState) -> str:
        kpis: dict[str, float] = state["kpis"]  # type: ignore[assignment]
        for cond in scenario.get("loseConditions", []):
            if self._condition_met(kpis, cond):
                return OUTCOME_LOST
        if state["beatIndex"] >= len(scenario["beats"]):
            win = scenario["winCondition"]
            return OUTCOME_WON if self._condition_met(kpis, win) else OUTCOME_LOST
        return OUTCOME_PLAYING

    @staticmethod
    def _grade(scenario: Scenario, state: GameState) -> str:
        """Letter grade for the end-of-game scorecard (deterministic).

        Wins grade A/B/C by how far stockPrice cleared the target; losses are
        D (campaign finished but missed the target) or F (a lose condition
        fired mid-game).
        """
        outcome = state.get("outcome", OUTCOME_PLAYING)
        kpis: dict[str, float] = state["kpis"]  # type: ignore[assignment]
        target = scenario["winCondition"]["gte"]
        if outcome == OUTCOME_WON:
            margin = kpis["stockPrice"] - target
            if margin >= 10:
                return "A"
            if margin >= 5:
                return "B"
            return "C"
        if outcome == OUTCOME_LOST:
            finished = state["beatIndex"] >= len(scenario["beats"])
            blowout = any(
                MeridianScoringEngine._condition_met(kpis, cond)
                for cond in scenario.get("loseConditions", [])
            )
            return "F" if blowout else ("D" if finished else "F")
        return "-"  # game still in progress


# Backwards-compatible alias kept from the Phase 1 scaffold.
StubScoringEngine = MeridianScoringEngine
