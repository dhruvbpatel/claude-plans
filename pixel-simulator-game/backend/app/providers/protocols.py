"""Re-export DebateProvider protocol (implementations live in sibling modules)."""

from app.engine.protocols import DebateContext, DebateDelta, DebateProvider

__all__ = ["DebateContext", "DebateDelta", "DebateProvider"]
