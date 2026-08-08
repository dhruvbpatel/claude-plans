"""Debate providers: deterministic | gateway | swarm (Phase 4-5)."""

from app.providers.deterministic import DeterministicDebate
from app.providers.factory import create_debate_provider
from app.providers.gateway import GatewayDebate
from app.providers.protocols import DebateProvider
from app.providers.swarm import SwarmDebate

__all__ = [
    "DebateProvider",
    "DeterministicDebate",
    "GatewayDebate",
    "SwarmDebate",
    "create_debate_provider",
]
