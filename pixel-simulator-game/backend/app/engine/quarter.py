"""v2 quarter start, knock-on evaluation, and close-out settle."""

from __future__ import annotations

from typing import Any

from app.engine.metrics import bounds_from_scenario, clamp_metric
from app.engine.protocols import CardDealer, EventDeck, GameState


def company_value(kpis: dict[str, float], scoring: dict[str, Any]) -> float:
    settle = scoring.get("settle") or {}
    ev = float(settle.get("evMultiple", 8))
    ebitda = float(kpis.get("revenue", 0)) * float(kpis.get("margin", 0)) / 100.0
    return ebitda * ev + float(kpis.get("cash", 0)) - float(kpis.get("debt", 0))


def apply_deltas(
    kpis: dict[str, float],
    deltas: dict[str, float],
    bounds: dict[str, tuple[float | None, float | None]],
) -> None:
    for key, delta in deltas.items():
        kpis[key] = clamp_metric(key, float(kpis.get(key, 0)) + float(delta), bounds)


def evaluate_knockons(
    kpis: dict[str, float],
    rules: list[dict[str, Any]],
    bounds: dict[str, tuple[float | None, float | None]],
) -> list[dict[str, Any]]:
    fired: list[dict[str, Any]] = []
    for rule in rules:
        when = rule.get("when") or {}
        kpi = when.get("kpi")
        if not kpi:
            continue
        value = float(kpis.get(kpi, 0))
        matched = False
        if "lt" in when and value < when["lt"]:
            matched = True
        if "gte" in when and value >= when["gte"]:
            matched = True
        if not matched:
            continue
        apply_deltas(kpis, dict(rule.get("deltas") or {}), bounds)
        fired.append(
            {
                "id": rule.get("id"),
                "deltas": dict(rule.get("deltas") or {}),
                "news": rule.get("news", ""),
            }
        )
    return fired


def settle_quarter(
    kpis: dict[str, float],
    opening: dict[str, float],
    scoring: dict[str, Any],
    bounds: dict[str, tuple[float | None, float | None]],
) -> float:
    settle = scoring.get("settle") or {}
    rate = float(settle.get("interestRateAnnual", 0.05))
    ebitda = float(kpis.get("revenue", 0)) * float(kpis.get("margin", 0)) / 100.0
    interest = float(kpis.get("debt", 0)) * rate / 4.0
    kpis["cash"] = clamp_metric("cash", float(kpis.get("cash", 0)) + ebitda - interest, bounds)
    cv = company_value(kpis, scoring)
    opening_cv = float(opening.get("companyValue") or cv or 1.0)
    conf_open = float(opening.get("confidence") or 0)
    price_open = float(opening.get("sharePrice") or kpis.get("sharePrice") or 0)
    price = float(kpis.get("sharePrice") or 0)
    price += float(settle.get("confidenceToPrice", 0.15)) * (
        float(kpis.get("confidence", 0)) - conf_open
    )
    if opening_cv:
        price += float(settle.get("valueToPrice", 0.10)) * price_open * (cv / opening_cv - 1)
    kpis["sharePrice"] = clamp_metric("sharePrice", price, bounds)
    return cv


def begin_quarter(
    state: GameState,
    scenario: dict[str, Any],
    dealer: CardDealer,
    events: EventDeck,
) -> GameState:
    kpis: dict[str, float] = dict(state["kpis"])
    bounds = bounds_from_scenario(scenario)
    quarter = int(state.get("beatIndex") or 0)
    event = events.draw(state, quarter)
    apply_deltas(kpis, dict(event.get("deltas") or {}), bounds)
    interrupt = bool(state.get("pendingInterrupt")) or bool(event.get("interrupt"))
    interrupt_card = event.get("interruptCardId") or state.get("pendingInterruptCardId")
    ctx = {
        "quarter": quarter,
        "news": event.get("news", ""),
        "focusMetrics": list(event.get("focusMetrics") or []),
        "interrupt": interrupt,
        "interruptCardId": interrupt_card,
        "eventId": event.get("id"),
    }
    hand = dealer.deal(state, ctx)
    state["kpis"] = kpis
    state["hand"] = hand
    state["interrupt"] = interrupt
    state["lastNews"] = str(event.get("news") or event.get("title") or "")
    state["lastEventId"] = event.get("id")
    state["pendingInterrupt"] = False
    if "pendingInterruptCardId" in state:
        state["pendingInterruptCardId"] = ""
    return state
