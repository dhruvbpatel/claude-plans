"""Shared type stubs and engine / provider protocols.

Meridian (schema v1) keeps ScoringEngine + DebateProvider + BoardVoteResolver.
NovaTech (schema v2) adds CardDealer, RivalPolicy, ScoringModel, WarRoomProvider,
and EventDeck. Advisory components never mutate GameState.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Protocol, TypedDict

# Generic metric map. v1 has five Meridian keys; v2 has thirteen NovaTech keys.
Kpis = dict[str, float]


class Option(TypedDict, total=False):
    id: str
    label: str
    pros: list[str]
    cons: list[str]
    deltas: dict[str, float]
    requires: list[str]
    unlocks: list[str]
    consequence: str
    family: str
    once: bool


class MetricDef(TypedDict, total=False):
    id: str
    label: str
    opening: float
    min: float
    max: float
    group: str


class Scenario(TypedDict, total=False):
    id: str
    title: str
    schemaVersion: int
    kpis: Kpis
    metrics: list[MetricDef]
    beats: list[dict[str, Any]]
    cards: list[dict[str, Any]]
    knockOnRules: list[dict[str, Any]]
    eventDeck: list[dict[str, Any]]
    rival: dict[str, Any]
    scoring: dict[str, Any]
    warRoom: dict[str, Any]
    winCondition: dict[str, Any]
    loseConditions: list[dict[str, Any]]
    maxQuarters: int


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
    openingKpis: Kpis
    hand: list[str]
    interrupt: bool
    playedCardIds: list[str]
    playedFamilies: list[str]
    companyValue: float
    lastNews: str
    pendingInterrupt: bool


class Summary(TypedDict, total=False):
    beatIndex: int
    kpis: Kpis
    history: list[dict[str, Any]]
    outcome: str
    grade: str
    composite: float
    band: str
    breakdown: list[dict[str, Any]]


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


class QuarterContext(TypedDict, total=False):
    quarter: int
    news: str
    focusMetrics: list[str]
    interrupt: bool
    interruptCardId: str
    eventId: str
    cards: list[dict[str, Any]]


class CardDealer(Protocol):
    def deal(self, state: GameState, quarter_ctx: QuarterContext) -> list[str]: ...


class Event(TypedDict, total=False):
    id: str
    title: str
    news: str
    quarterMin: int
    quarterMax: int
    deltas: dict[str, float]
    focusMetrics: list[str]
    interrupt: bool
    interruptCardId: str


class EventDeck(Protocol):
    def draw(self, state: GameState, quarter: int) -> Event: ...


class RivalResponse(TypedDict, total=False):
    pressure: float
    attackId: str | None
    deltas: dict[str, float]
    news: str
    interrupt: bool
    interruptCardId: str
    heldOff: bool


class RivalPolicy(Protocol):
    def respond(self, state: GameState, played_card: dict[str, Any]) -> RivalResponse: ...


class ScoreBreakdown(TypedDict):
    metricId: str
    weight: float
    opening: float
    current: float
    ratio: float
    contribution: float


class Score(TypedDict, total=False):
    composite: float
    band: str
    breakdown: list[ScoreBreakdown]
    outcome: str
    failedOn: str


class ScoringModel(Protocol):
    def close_out(self, state: GameState) -> Score: ...

    def early_failure(self, state: GameState) -> str | None: ...


class WarRoomSeatVote(TypedDict):
    seatId: str
    preferredCardId: str
    rationale: str
    concern: str


class WarRoomDissent(TypedDict):
    seatId: str
    preferredCardId: str
    concern: str


class WarRoomChair(TypedDict):
    recommendedCardId: str
    tally: dict[str, int]
    dissents: list[WarRoomDissent]
    confidence: str


class WarRoomResult(TypedDict):
    seats: list[WarRoomSeatVote]
    chair: WarRoomChair


class WarRoomContext(TypedDict, total=False):
    state: GameState
    quarter: int
    news: str
    hand: list[Option]
    interrupt: bool
    npcs: list[str]
    seats: list[dict[str, Any]]


class WarRoomProvider(Protocol):
    def convene(self, ctx: WarRoomContext) -> WarRoomResult: ...
