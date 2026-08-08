"""Shared fixtures: sys.path bootstrap, scenario loader, engine factory."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

SCENARIO_PATH = BACKEND_ROOT / "scenarios" / "meridian-activist-01.json"


@pytest.fixture(scope="session")
def scenario() -> dict:
    return json.loads(SCENARIO_PATH.read_text())


@pytest.fixture()
def engine():
    from app.engine.scoring import MeridianScoringEngine

    return MeridianScoringEngine()
