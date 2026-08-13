"""Shared type stubs and ScoringEngine / DebateProvider protocols.

Phase 2 fills ScoringEngine; Phase 4–5 fill DebateProvider implementations.
Contracts must stay stable so teammate FastAPI / line-graph code can drop in.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Protocol, TypedDict


class Kpis(TypedDict):
    stockPrice: float
    boardResistance: float
    ownershipPct: float
    warChest: float
    mediaHeat: float


class Option(TypedDict, total=False):
    id: str
    label: str
    pros: list[str]
    cons: list[str]
    deltas: dict[str, float]
    requires: list[str]
    unlocks: list[str]
    consequence: str


class Scenario(TypedDict, total=False):
    id: str
    title: str
    kpis: Kpis
    beats: list[dict[str, Any]]
    winCondition: dict[str, Any]
    loseConditions: list[dict[str, Any]]


class GameState(TypedDict, total=False):
    sessionId: str
    scenarioId: str
    phase: str
    beatIndex: int
    kpis: Kpis
    flags: list[str]
    history: list[dict[str, Any]]
    seed: int
    outcome: str
    curveballVariantId: str


class Summary(TypedDict, total=False):
    beatIndex: int
    kpis: Kpis
    history: list[dict[str, Any]]
    outcome: str
    grade: str


class DebateContext(TypedDict, total=False):
    state: GameState
    beat: dict[str, Any]
    options: list[Option]
    npcs: list[str]
    motionId: str


class BoardVote(TypedDict, total=False):
    ballots: dict[str, str]
    winningOptionId: str
    tieBrokenBy: str


class BoardVoteResolver(Protocol):
    def resolve(self, ctx: DebateContext) -> BoardVote: ...


class DebateDelta(TypedDict, total=False):
    speakerId: str
    text: str
    done: bool


class ScoringEngine(Protocol):
    def create(self, scenario: Scenario) -> GameState: ...

    def available_options(self, state: GameState) -> list[Option]: ...

    def apply(self, state: GameState, option_id: str) -> GameState: ...

    def summary(self, state: GameState) -> Summary: ...


class DebateProvider(Protocol):
    async def stream(self, ctx: DebateContext) -> AsyncIterator[DebateDelta]: ...
