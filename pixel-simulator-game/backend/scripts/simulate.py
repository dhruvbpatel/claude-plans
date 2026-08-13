"""Headless balance simulation (Phase 6).

Runs many full games against the shipped scenario with different policies and
reports win rates and loss reasons, so scenario deltas can be tuned toward a
~40-60% mixed-strategy win rate.

Usage:
    .venv/bin/python scripts/simulate.py [n_runs]
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

SCENARIO = json.loads(
    (BACKEND_ROOT / "scenarios" / "meridian-activist-01.json").read_text()
)


def run_policy(engine, seed: int, pick) -> dict:
    """Play one full game; ``pick(rng, options, state)`` chooses an option."""
    rng = random.Random(seed)
    state = engine.create(SCENARIO, seed=seed)
    while state["outcome"] == "playing":
        options = engine.available_options(state)
        state = engine.apply(state, pick(rng, options, state)["id"])
    return state


def pick_random(rng, options, _state):
    return rng.choice(options)


def loss_reason(state) -> str:
    kpis = state["kpis"]
    if kpis["boardResistance"] >= 100:
        return "boardResistance>=100"
    if kpis["warChest"] <= 0:
        return "warChest<=0"
    return "missed stock target"


def report(name: str, n: int, pick) -> None:
    engine = MeridianScoringEngine()
    wins = 0
    grades: Counter[str] = Counter()
    losses: Counter[str] = Counter()
    finals: list[float] = []
    for seed in range(n):
        state = run_policy(engine, seed, pick)
        finals.append(state["kpis"]["stockPrice"])
        grades[engine.summary(state)["grade"]] += 1
        if state["outcome"] == "won":
            wins += 1
        else:
            losses[loss_reason(state)] += 1
    finals.sort()
    median = finals[len(finals) // 2]
    print(
        f"{name:>14}: {wins}/{n} wins ({100 * wins / n:.1f}%)  "
        f"median final stock ${median:.2f}  grades {dict(sorted(grades.items()))}"
    )
    if losses:
        print(f"{'':>14}  losses: {dict(losses.most_common())}")


def report_path(name: str, path: list[str | None]) -> None:
    """Scripted path (None = first curveball option), across all 3 variants."""
    engine = MeridianScoringEngine()
    variant_seeds: dict[str, int] = {}
    for s in range(100):
        vid = engine.create(SCENARIO, seed=s)["curveballVariantId"]
        variant_seeds.setdefault(vid, s)
        if len(variant_seeds) == 3:
            break
    for vid, seed in sorted(variant_seeds.items()):
        state = engine.create(SCENARIO, seed=seed)
        for opt in path:
            if state["outcome"] != "playing":
                break
            if opt is None:
                opt = engine.available_options(state)[0]["id"]
            state = engine.apply(state, opt)
        print(
            f"{name:>14} [{vid}]: {state['outcome']}  "
            f"stock ${state['kpis']['stockPrice']:.2f}  "
            f"resist {state['kpis']['boardResistance']}  "
            f"chest {state['kpis']['warChest']}  "
            f"grade {MeridianScoringEngine._grade(SCENARIO, state)}"
        )


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    report("random walk", n, pick_random)
    print()
    # Archetype paths from the engine tests.
    report_path("proxy", ["1a", "2a", "3a", "4b", "5b", None, "7b", "8a", "9a"])
    report_path("settlement", ["1a", "2a", "3b", "4a", "5a", None, "7a", "8b", "9b"])
    # The Phase 4 "sensible mixed" run that finished $54.50 (grade D).
    report_path("mixed(P4)", ["1b", "2c", "3b", "4b", "5a", None, "7a", "8b", "9b"])
