"""Pure scoring state machine and v2 engine plugins."""

from app.engine.factory import (
    create_card_dealer,
    create_event_deck,
    create_rival_policy,
    create_scoring_model,
    create_war_room_provider,
)
from app.engine.protocols import ScoringEngine
from app.engine.scoring import MeridianScoringEngine

__all__ = [
    "ScoringEngine",
    "MeridianScoringEngine",
    "create_card_dealer",
    "create_event_deck",
    "create_rival_policy",
    "create_scoring_model",
    "create_war_room_provider",
]
