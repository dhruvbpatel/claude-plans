"""Weighted composite scoring. Phase 1: ratio formula. Phase 5 fills bands/balance."""

from __future__ import annotations

from typing import Any

from app.engine.protocols import GameState, Score, ScoreBreakdown


class WeightedComposite:
    def __init__(self, scenario: dict[str, Any] | None = None) -> None:
        self._scenario = scenario or {}

    def early_failure(self, state: GameState) -> str | None:
        cfg = (self._scenario.get("scoring") or {}).get("earlyFailure") or []
        kpis = state.get("kpis") or {}
        opening = state.get("openingKpis") or {}
        for rule in cfg:
            kpi = rule["kpi"]
            current = float(kpis.get(kpi, 0))
            if "lt" in rule and current < rule["lt"]:
                return str(rule.get("id") or kpi)
            if "ltRatioOfOpening" in rule:
                base = float(opening.get(kpi, 0))
                if base and current < rule["ltRatioOfOpening"] * base:
                    return str(rule.get("id") or kpi)
        return None

    def close_out(self, state: GameState) -> Score:
        failed = self.early_failure(state)
        weights: dict[str, float] = dict(
            (self._scenario.get("scoring") or {}).get("weights") or {}
        )
        kpis = dict(state.get("kpis") or {})
        opening = dict(state.get("openingKpis") or kpis)
        if "companyValue" in weights:
            kpis["companyValue"] = float(state.get("companyValue") or kpis.get("companyValue") or 0)
            opening["companyValue"] = float(
                state.get("openingCompanyValue")
                or opening.get("companyValue")
                or kpis["companyValue"]
                or 1.0
            )

        breakdown: list[ScoreBreakdown] = []
        composite = 0.0
        for metric_id, weight in weights.items():
            cur = float(kpis.get(metric_id, 0))
            opn = float(opening.get(metric_id, 0))
            ratio = 1.0 if opn == 0 else cur / opn
            contribution = float(weight) * ratio
            composite += contribution
            breakdown.append(
                {
                    "metricId": metric_id,
                    "weight": float(weight),
                    "opening": opn,
                    "current": cur,
                    "ratio": ratio,
                    "contribution": contribution,
                }
            )
        ratios = {row["metricId"]: row["ratio"] for row in breakdown}
        win_at = float((self._scenario.get("scoring") or {}).get("winAt") or 110)
        if failed:
            band, outcome = "failed", "lost"
        elif composite >= win_at:
            host_ok = ratios.get("morale", 1) >= 0.9 and ratios.get("innovation", 1) >= 0.9
            band = "constructive" if host_ok else "pyrrhic"
            outcome = "won"
        elif composite >= 95:
            band, outcome = "settled", "lost"
        else:
            band, outcome = "failed", "lost"
        result: Score = {
            "composite": composite,
            "band": band,
            "breakdown": breakdown,
            "outcome": outcome,
        }
        if failed:
            result["failedOn"] = failed
        return result
