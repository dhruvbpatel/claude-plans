"""Deterministic rival pressure-gauge policy (spec §10)."""

from __future__ import annotations

from typing import Any

from app.engine.protocols import GameState, RivalResponse


def _trigger_hit(kpis: dict[str, float], trigger: dict[str, Any]) -> bool:
    kpi = trigger.get("kpi")
    if not kpi:
        return False
    value = float(kpis.get(kpi, 0))
    if "lt" in trigger and value < trigger["lt"]:
        return True
    if "lte" in trigger and value <= trigger["lte"]:
        return True
    if "gte" in trigger and value >= trigger["gte"]:
        return True
    return False


class DeterministicRival:
    def __init__(self, scenario: dict[str, Any] | None = None) -> None:
        self._scenario = scenario or {}

    def respond(self, state: GameState, played_card: dict[str, Any]) -> RivalResponse:
        cfg = self._scenario.get("rival") or {}
        kpis = dict(state.get("kpis") or {})
        current = float(kpis.get("rivalPressure") or 0)
        card_id = str((played_card or {}).get("id") or "")
        card_table = dict(cfg.get("cardPressure") or {})
        delta = float(card_table.get(card_id, cfg.get("defaultPressureDelta", 6)))
        pressure = max(0.0, min(100.0, current + delta))
        fired = list(state.get("firedAttackIds") or [])
        attacks = list(cfg.get("attacks") or [])
        unused = [a for a in attacks if a.get("id") not in fired]
        threshold = float(cfg.get("threshold", 55))
        secondary_hit = any(
            _trigger_hit(kpis, t) for t in (cfg.get("secondaryTriggers") or [])
        )
        should_attack = (pressure >= threshold or secondary_hit) and bool(unused)
        if not should_attack:
            return {
                "pressure": pressure,
                "attackId": None,
                "deltas": {},
                "news": str(cfg.get("holdOffNews") or "The rival watches and holds off."),
                "interrupt": False,
                "heldOff": True,
            }
        preferred = None
        for trigger in cfg.get("secondaryTriggers") or []:
            if _trigger_hit(kpis, trigger) and trigger.get("attackId"):
                preferred = trigger["attackId"]
                break
        attack = next((a for a in unused if a.get("id") == preferred), unused[0])
        return {
            "pressure": pressure,
            "attackId": attack.get("id"),
            "deltas": dict(attack.get("deltas") or {}),
            "news": str(attack.get("news") or attack.get("title") or ""),
            "interrupt": bool(attack.get("interrupt")),
            "interruptCardId": str(attack.get("interruptCardId") or ""),
            "heldOff": False,
        }
