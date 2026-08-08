"""Debate provider selection: DEBATE_PROVIDER=deterministic|gateway|swarm.

Resolved per session at creation time, so the env switch takes effect for new
sessions without a restart. Unknown values log a warning and fall back to
deterministic — the game must always be playable with no config at all.
"""

from __future__ import annotations

import logging
import os

from app.engine.protocols import DebateProvider
from app.providers.deterministic import DeterministicDebate
from app.providers.gateway import GatewayDebate
from app.providers.swarm import SwarmDebate

logger = logging.getLogger(__name__)

DEFAULT_PROVIDER = "deterministic"

_PROVIDERS: dict[str, type] = {
    "deterministic": DeterministicDebate,
    "gateway": GatewayDebate,
    "swarm": SwarmDebate,
}


def create_debate_provider(name: str | None = None) -> DebateProvider:
    """Instantiate the debate provider named by ``name`` or ``DEBATE_PROVIDER``."""
    key = (name or os.getenv("DEBATE_PROVIDER", DEFAULT_PROVIDER)).strip().lower()
    cls = _PROVIDERS.get(key)
    if cls is None:
        logger.warning(
            "unknown DEBATE_PROVIDER=%r; falling back to %r", key, DEFAULT_PROVIDER
        )
        cls = _PROVIDERS[DEFAULT_PROVIDER]
    return cls()
