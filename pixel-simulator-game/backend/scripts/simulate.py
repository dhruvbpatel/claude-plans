"""Headless balance simulation.

Usage:
    python scripts/simulate.py [n_runs]
    python scripts/simulate.py --meridian [n_runs]
"""

from __future__ import annotations

import json
import random
import sys
from collections import Counter
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.engine.scoring import MeridianScoringEngine  # noqa: E402

MERIDIAN = json.loads(
    (BACKEND_ROOT / "scenarios" / "meridian-activist-01.json").read_text()
)
NOVATECH = json.loads(
    (BACKEND_ROOT / "scenarios" / "novatech-proxy-war-01.json").read_text()
)


def pick_random(rng, options, _state):
    return rng.choice(options)


def run_meridian(engine, seed: int, pick) -> dict:
    rng = random.Random(seed)
    state = engine.create(MERIDIAN, seed=seed)
    while state["outcome"] == "playing":
        options = engine.available_options(state)
        state = engine.apply(state, pick(rng, options, state)["id"])
    return state


def run_novatech(engine, seed: int, pick) -> dict:
    rng = random.Random(seed)
    state = engine.create(NOVATECH, seed=seed)
    steps = 0
    while state["outcome"] == "playing":
        state = engine.start_quarter(state)
        options = engine.available_options(state)
        if not options:
            break
        state = engine.apply(state, pick(rng, options, state)["id"])
        steps += 1
        if steps > 8:
            break
    return state


def meridian_loss(state) -> str:
    kpis = state["kpis"]
    if kpis["boardResistance"] >= 100:
        return "boardResistance>=100"
    if kpis["warChest"] <= 0:
        return "warChest<=0"
    return "missed stock target"


def novatech_loss(state) -> str:
    if state.get("failedOn"):
        return str(state["failedOn"])
    return str(state.get("band") or "below winAt")


def report_meridian(n: int) -> None:
    engine = MeridianScoringEngine()
    wins = 0
    grades: Counter[str] = Counter()
    losses: Counter[str] = Counter()
    finals: list[float] = []
    for seed in range(n):
        state = run_meridian(engine, seed, pick_random)
        finals.append(state["kpis"]["stockPrice"])
        grades[engine.summary(state)["grade"]] += 1
        if state["outcome"] == "won":
            wins += 1
        else:
            losses[meridian_loss(state)] += 1
    finals.sort()
    median = finals[len(finals) // 2]
    print(
        f"{'random walk':>14}: {wins}/{n} wins ({100 * wins / n:.1f}%)  "
        f"median final stock ${median:.2f}  grades {dict(sorted(grades.items()))}"
    )
    if losses:
        print(f"{'':>14}  losses: {dict(losses.most_common())}")


def report_novatech(n: int) -> None:
    engine = MeridianScoringEngine()
    wins = 0
    bands: Counter[str] = Counter()
    losses: Counter[str] = Counter()
    composites: list[float] = []
    for seed in range(n):
        state = run_novatech(engine, seed, pick_random)
        summary = engine.summary(state)
        composites.append(float(summary.get("composite") or 0))
        bands[str(summary.get("band") or "-")] += 1
        if state["outcome"] == "won":
            wins += 1
        else:
            losses[novatech_loss(state)] += 1
    composites.sort()
    median = composites[len(composites) // 2] if composites else 0
    print(
        f"{'random walk':>14}: {wins}/{n} wins ({100 * wins / n:.1f}%)  "
        f"median composite {median:.1f}  bands {dict(sorted(bands.items()))}"
    )
    if losses:
        print(f"{'':>14}  losses: {dict(losses.most_common())}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    flags = {a for a in sys.argv[1:] if a.startswith("-")}
    n = int(args[0]) if args else 50
    if "--meridian" in flags:
        report_meridian(n)
    else:
        report_novatech(n)
