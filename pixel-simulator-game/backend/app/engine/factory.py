"""Env-driven factories for v2 engine plugins. Unknown names → deterministic."""

from __future__ import annotations

import logging
import os
from typing import Any

from app.engine.composite import WeightedComposite
from app.engine.dealer import SeededCardDealer
from app.engine.events import SeededEventDeck
from app.engine.protocols import (
    CardDealer,
    EventDeck,
    RivalPolicy,
    ScoringModel,
    WarRoomProvider,
)
from app.engine.rival import DeterministicRival
from app.engine.war_room import DeterministicWarRoom, SwarmWarRoom

logger = logging.getLogger(__name__)

_DEFAULT = "deterministic"


def _pick(env_key: str, name: str | None, table: dict[str, type], default_cls: type):
    key = (name or os.getenv(env_key, _DEFAULT)).strip().lower()
    cls = table.get(key)
    if cls is None:
        logger.warning("unknown %s=%r; falling back to %r", env_key, key, _DEFAULT)
        cls = default_cls
    return cls


def create_card_dealer(
    name: str | None = None, scenario: dict[str, Any] | None = None
) -> CardDealer:
    cls = _pick(
        "CARD_DEALER",
        name,
        {"deterministic": SeededCardDealer},
        SeededCardDealer,
    )
    return cls(scenario=scenario)


def create_event_deck(
    name: str | None = None, scenario: dict[str, Any] | None = None
) -> EventDeck:
    cls = _pick(
        "EVENT_DECK",
        name,
        {"deterministic": SeededEventDeck},
        SeededEventDeck,
    )
    return cls(scenario=scenario)


def create_rival_policy(
    name: str | None = None, scenario: dict[str, Any] | None = None
) -> RivalPolicy:
    cls = _pick(
        "RIVAL_POLICY",
        name,
        {"deterministic": DeterministicRival},
        DeterministicRival,
    )
    return cls(scenario=scenario)


def create_scoring_model(
    name: str | None = None, scenario: dict[str, Any] | None = None
) -> ScoringModel:
    cls = _pick(
        "SCORING_MODEL",
        name,
        {"deterministic": WeightedComposite},
        WeightedComposite,
    )
    return cls(scenario=scenario)


def create_war_room_provider(
    name: str | None = None, scenario: dict[str, Any] | None = None
) -> WarRoomProvider:
    cls = _pick(
        "WAR_ROOM_PROVIDER",
        name,
        {"deterministic": DeterministicWarRoom, "swarm": SwarmWarRoom},
        DeterministicWarRoom,
    )
    return cls(scenario=scenario)
