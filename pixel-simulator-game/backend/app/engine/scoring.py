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

from app.engine.metrics import (
    V1_BOUNDS,
    bounds_from_scenario,
    clamp_metric,
    openings_from_scenario,
    schema_version,
)
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
    return clamp_metric(kpi, value, bounds)


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
            from app.engine.quarter import company_value

            state["openingKpis"] = dict(kpis)
            cv = company_value(kpis, scenario.get("scoring") or {})
            state["companyValue"] = cv
            state["openingCompanyValue"] = cv
            state["hand"] = []
            state["playedCardIds"] = []
            state["playedFamilies"] = []
            state["pendingInterrupt"] = False
            self._bind_plugins(scenario)

        variant_id = self._pick_curveball_variant(scenario, seed)
        if variant_id is not None:
            state["curveballVariantId"] = variant_id
        return state

    def _bind_plugins(self, scenario: Scenario) -> dict[str, Any]:
        from app.engine.factory import (
            create_card_dealer,
            create_event_deck,
            create_rival_policy,
            create_scoring_model,
        )

        if not hasattr(self, "_plugins"):
            self._plugins = {}
        sid = scenario["id"]
        self._plugins[sid] = {
            "dealer": create_card_dealer(scenario=scenario),
            "events": create_event_deck(scenario=scenario),
            "rival": create_rival_policy(scenario=scenario),
            "scoring": create_scoring_model(scenario=scenario),
        }
        return self._plugins[sid]

    def _plugins_for(self, state: GameState) -> dict[str, Any]:
        scenario = self._scenario_for(state)
        plugins = getattr(self, "_plugins", {}).get(scenario["id"])
        if plugins is None:
            plugins = self._bind_plugins(scenario)
        return plugins

    def start_quarter(self, state: GameState) -> GameState:
        """Draw news, apply event deltas, deal the quarter's hand. Pure."""
        new_state: GameState = copy.deepcopy(state)
        if new_state.get("hand"):
            return new_state
        from app.engine.quarter import begin_quarter

        scenario = self._scenario_for(new_state)
        plugins = self._plugins_for(new_state)
        return begin_quarter(
            new_state, scenario, plugins["dealer"], plugins["events"]
        )

    def available_options(self, state: GameState) -> list[Option]:
        if state.get("outcome", OUTCOME_PLAYING) != OUTCOME_PLAYING:
            return []
        scenario = self._scenario_for(state)
        if schema_version(scenario) == 2:
            catalog = {c["id"]: c for c in scenario.get("cards") or [] if c.get("id")}
            return [catalog[i] for i in state.get("hand") or [] if i in catalog]
        beat = self._current_beat(state)
        if beat is None:
            return []
        flags = set(state.get("flags", []))
        options = self._beat_options(state, beat)
        return [o for o in options if set(o.get("requires", [])) <= flags]

    def apply(self, state: GameState, option_id: str) -> GameState:
        if state.get("outcome", OUTCOME_PLAYING) != OUTCOME_PLAYING:
            raise ValueError("game already ended; cannot apply further options")
        scenario = self._scenario_for(state)
        if schema_version(scenario) == 2:
            return self._apply_v2(state, option_id)

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

    def _apply_v2(self, state: GameState, option_id: str) -> GameState:
        from app.engine.quarter import apply_deltas, evaluate_knockons, settle_quarter

        scenario = self._scenario_for(state)
        catalog = {c["id"]: c for c in scenario.get("cards") or [] if c.get("id")}
        if option_id not in (state.get("hand") or []) or option_id not in catalog:
            raise ValueError(f"unknown option {option_id!r} for this quarter")
        option = catalog[option_id]
        missing = set(option.get("requires") or []) - set(state.get("flags") or [])
        if missing:
            raise ValueError(
                f"option {option_id!r} gated by missing flags: {sorted(missing)}"
            )

        new_state: GameState = copy.deepcopy(state)
        bounds = bounds_from_scenario(scenario)
        kpis: dict[str, float] = dict(new_state["kpis"])
        apply_deltas(kpis, dict(option.get("deltas") or {}), bounds)
        for flag in option.get("unlocks") or []:
            if flag not in new_state["flags"]:
                new_state["flags"].append(flag)
        knockons = evaluate_knockons(
            kpis, list(scenario.get("knockOnRules") or []), bounds
        )
        opening = dict(new_state.get("openingKpis") or {})
        if new_state.get("openingCompanyValue") is not None:
            opening["companyValue"] = float(new_state["openingCompanyValue"])
        cv = settle_quarter(
            kpis, opening, scenario.get("scoring") or {}, bounds
        )
        new_state["kpis"] = kpis
        new_state["companyValue"] = cv

        plugins = self._plugins_for(new_state)
        rival_resp = plugins["rival"].respond(new_state, option)
        if rival_resp.get("deltas"):
            apply_deltas(kpis, dict(rival_resp["deltas"]), bounds)
        if rival_resp.get("pressure") is not None:
            kpis["rivalPressure"] = _clamp(
                "rivalPressure", float(rival_resp["pressure"]), bounds
            )
        new_state["kpis"] = kpis
        if rival_resp.get("interrupt"):
            new_state["pendingInterrupt"] = True
            new_state["pendingInterruptCardId"] = str(
                rival_resp.get("interruptCardId") or ""
            )
        attack_id = rival_resp.get("attackId")
        if attack_id:
            fired = list(new_state.get("firedAttackIds") or [])
            if attack_id not in fired:
                fired.append(str(attack_id))
            new_state["firedAttackIds"] = fired

        played = list(new_state.get("playedCardIds") or [])
        if option_id not in played:
            played.append(option_id)
        new_state["playedCardIds"] = played
        families = list(new_state.get("playedFamilies") or [])
        fam = option.get("family")
        if fam and fam not in families:
            families.append(str(fam))
        new_state["playedFamilies"] = families

        entry: dict[str, Any] = {
            "beatId": f"quarter-{state['beatIndex'] + 1}",
            "beatIndex": state["beatIndex"],
            "optionId": option["id"],
            "label": option.get("label", ""),
            "deltas": dict(option.get("deltas") or {}),
            "consequence": option.get("consequence", ""),
            "kpis": dict(kpis),
            "knockOns": knockons,
            "companyValue": cv,
        }
        if rival_resp.get("news"):
            entry["rivalNews"] = rival_resp["news"]
        new_state["history"].append(entry)
        new_state["hand"] = []
        new_state["interrupt"] = False
        new_state["beatIndex"] = state["beatIndex"] + 1

        model = plugins["scoring"]
        failed = model.early_failure(new_state)
        max_q = int(scenario.get("maxQuarters") or 8)
        if failed:
            new_state["outcome"] = OUTCOME_LOST
            new_state["failedOn"] = failed
            new_state["phase"] = "GAME_END"
        elif new_state["beatIndex"] >= max_q:
            score = model.close_out(new_state)
            new_state["outcome"] = score.get("outcome") or OUTCOME_LOST
            new_state["phase"] = "GAME_END"
            new_state["composite"] = score.get("composite")
            new_state["band"] = score.get("band")
        else:
            new_state["outcome"] = OUTCOME_PLAYING
            new_state["phase"] = "EXPLORE"
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
        scenario = self._scenario_for(state)
        result: Summary = {
            "beatIndex": state["beatIndex"],
            "kpis": dict(state["kpis"]),  # type: ignore[typeddict-item]
            "history": list(state.get("history", [])),
            "outcome": state.get("outcome", OUTCOME_PLAYING),
            "grade": "-" if schema_version(scenario) == 2 else self._grade(scenario, state),
        }
        if schema_version(scenario) == 2:
            score = self._plugins_for(state)["scoring"].close_out(state)
            result["composite"] = score.get("composite")
            result["band"] = score.get("band")
            result["breakdown"] = score.get("breakdown")
            if score.get("band"):
                result["grade"] = str(score["band"])
        return result

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
