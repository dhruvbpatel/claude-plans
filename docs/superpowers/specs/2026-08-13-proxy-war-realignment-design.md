# Proxy War Realignment

Date: 2026-08-13  
Project: `pixel-simulator-game` (Activist Pixel Sim)  
Status: approved for implementation  
Sources: `Activist Investor Scenario.md`, `Proxy War — Campaign Decision Flow.md`, plan `proxy_war_realignment_6b80208e`

This spec is the durable reference for Phases 1–6. Later sessions start here. Do not treat Meridian `SPEC.md` as the NovaTech contract; that file remains the Meridian baseline.

## 1. Problem

The shipped game is a 9-beat authored Meridian campaign with 5 hardcoded KPIs, per-beat option cards, and a stock-target A–F grade. The approved NovaTech / Proxy War design is a different game on the same pixel loop: 8 seeded quarters, a 16-card deck, 13 config-driven metrics, a deterministic rival on a pressure gauge, a 6-seat war room every quarter, and a weighted composite score.

## 2. Goal

Realign the engine, session loop, and frontend to NovaTech Proxy War while keeping Meridian (`meridian-activist-01`) playable as a regression baseline until Phase 6.

Player loop stays: walk, interact, debate, decide. The existing boardroom gather/cutscene becomes the every-quarter war-room ritual.

## 3. Non-goals

- Competitive multiplayer / leaderboard (Phase 7).
- A real LangGraph or internal-platform swarm. Deterministic defaults + documented stubs only.
- Rewriting Phaser as a new scene or second map.
- Changing Meridian authored deltas, board ballots, or letter-grade math.
- Director / campaign-shape LLM (“why” texture). Physics is identical for every world.

## 4. Invariant — pluggability

**Agents advise. Only the deterministic engine mutates `GameState`.**

`CardDealer`, `RivalPolicy`, `ScoringModel`, `WarRoomProvider`, and `EventDeck` are advisory or config components. They return structured values. Session code passes those values into `ScoringEngine.apply` / settle / clamp. If a provider hallucinates a number, it is discarded; the engine never reads deltas out of LLM text.

A real agent swarm later implements `WarRoomProvider` (and optionally `DebateProvider`) against the contracts in §8. No game or Phaser change should be required.

Factories follow the existing `create_debate_provider()` pattern: env var, unknown → log warning → deterministic, resolved per session at `POST /sessions`.

| Component | Env | Default | Swarm slot |
|-----------|-----|---------|------------|
| Debate | `DEBATE_PROVIDER` | `deterministic` | existing stub |
| War room | `WAR_ROOM_PROVIDER` | `deterministic` | documented stub delegating to deterministic |
| Card dealer | `CARD_DEALER` | `deterministic` | not required this effort |
| Rival | `RIVAL_POLICY` | `deterministic` | not required this effort |
| Scoring | `SCORING_MODEL` | `deterministic` | not required this effort |
| Event deck | `EVENT_DECK` | `deterministic` | not required this effort |

## 5. Dual scenario paths

| | Meridian (v1) | NovaTech (v2) |
|---|---|---|
| Id | `meridian-activist-01` | `novatech-proxy-war-01` |
| Detection | no `schemaVersion` / `schemaVersion: 1`, or presence of `beats` without `cards` | `schemaVersion: 2` |
| Clock | 9 authored beats | 8 quarters (`MAX_QUARTERS = 8`) |
| Options | per-beat authored cards | dealt 3-card hand (4 on interrupt) from a 16-card deck |
| Metrics | 5 KPIs via `kpis` object | 13 metrics via `metrics` array |
| Meeting | boardroom on beats 4/7/9: motion → debate → board vote **applies winner** | war room **every quarter**: debate → recommendation → player decides; **player card applies** |
| Scoring | stock target A–F | weighted composite; ≥110 wins |
| Rival | none (board resistance KPI) | pressure-gauge policy table |

Phase 1 keeps a legacy path so existing Meridian tests stay green. From Phase 2, `simulate.py` drives the v2 loop; Meridian remains loadable.

`GameState.kpis` stays the on-the-wire metric map (`kpi_patch` unchanged). For v1 it has the five Meridian keys. For v2 it has the thirteen NovaTech keys. Callers must not assume a fixed key set.

## 6. Quarter pipeline (v2)

Every quarter, regardless of campaign flavor:

```
EXPLORE
  → interact zone:war_room or npc:chair  (same trigger rules as today)
  → BEAT_INTRO          # quarter news / curveball from EventDeck
  → CONVENE             # sprites gather; server does not wait on walking
  → DEBATE              # stream debate_delta (existing SSE shape)
  → emit war_room       # structured recommendation (new event)
  → AWAIT_DECISION      # 3 or 4 public cards (pros/cons only, never deltas)
  → APPLY               # player optionId
        engine: card deltas → knock-ons → quarter-close settle → rival.respond
  → EXPLORE | GAME_END
```

Order of engine work inside `APPLY` (player’s card already chosen):

1. Apply the played card’s `deltas`, `unlocks`, `once` flag.
2. Evaluate knock-on rules against the post-card metrics.
3. Quarter-close settle (interest, EBITDA → cash, derived company value, share-price nudge).
4. `RivalPolicy.respond(state, played_card)` → optional attack deltas + news + `interrupt` for the **next** quarter.
5. Early-failure checks. If quarter index reaches 8, close-out score.

`decide` before `AWAIT_DECISION`, or a second `decide` in the same quarter, still returns 409.

Headless tests never wait on Phaser, walking, or keys.

### 6.1 Pixel loop

Walk / collide / `E` interact is unchanged. **Pressing E snaps the debate seats and player to the table** (no walk-in). Walking-in collided with the solid table and never flipped `seated`, which froze WASD/E. After `APPLY`, NPCs snap home and resume wandering. Lines still advance on key/click; cards appear after `war_room`.

Meridian boardroom path is unchanged for v1 (motion first, then debate, board vote applies).

### 6.2 `GameState` additions (v2)

```python
class GameState(TypedDict, total=False):
    sessionId: str
    scenarioId: str
    phase: str
    beatIndex: int          # quarter index 0..7 for v2; keep name for API compatibility
    kpis: dict[str, float]  # generic metric map
    flags: list[str]
    history: list[dict]
    seed: int
    outcome: str            # playing | won | lost
    openingKpis: dict[str, float]
    hand: list[str]         # dealt card ids this quarter
    interrupt: bool         # 4th card this quarter
    playedCardIds: list[str]
    playedFamilies: list[str]
    companyValue: float     # derived; also mirrored in kpis if desired
    lastNews: str
    pendingInterrupt: bool  # set by rival/event for next deal
```

`beatIndex` is the quarter counter on the wire so `next_beat` / HUD keep working. v2 `next_beat` uses `zoneId: "war_room"` every quarter.

## 7. Metric registry

Scenario JSON declares metrics. The engine clamps generically. No hardcoded `Kpis` TypedDict for v2.

```json
"metrics": [
  { "id": "sharePrice", "label": "Share price", "opening": 100, "min": 0, "group": "market" }
]
```

| Field | Rule |
|-------|------|
| `id` | Stable key in `kpis` |
| `label` | HUD |
| `opening` | Value at `create` |
| `min` / `max` | Optional; omitted = unbounded on that side |
| `group` | HUD grouping: `market` \| `financial` \| `ops` \| `people` \| `risk` \| `campaign` |

`companyValue` is **derived**, not a player-facing card delta target. Opening company value is computed once at `create` from openings (see §11.2) and stored on state for ratio scoring.

### 7.1 NovaTech openings

Indexed / constructed values from the worked example. Unspecified openings are assumptions (flagged).

| id | label | opening | min | max | group |
|----|-------|---------|-----|-----|-------|
| sharePrice | Share price | 100 | 0 | — | market |
| confidence | Confidence | 60 | 0 | 100 | market |
| reputation | Reputation | 55 | 0 | 100 | market |
| cash | Cash ($M) | 800 | — | — | financial |
| debt | Debt ($M) | 300 | 0 | — | financial |
| revenue | Revenue ($M, quarterly) | **400** | 0 | — | financial |
| margin | Margin (%) | **12** | -20 | 80 | financial |
| innovation | Innovation | 55 | 0 | 100 | ops |
| marketShare | Market share | **18** | 0 | 100 | ops |
| morale | Morale | 60 | 0 | 100 | people |
| integrationRisk | Integration risk | **0** | 0 | 100 | risk |
| regulatoryRisk | Regulatory risk | **20** | 0 | 100 | risk |
| rivalPressure | Rival pressure | 20 | 0 | 100 | campaign |

**Assumptions (not in the worked example’s opening line):** revenue 400, margin 12, marketShare 18, integrationRisk 0, regulatoryRisk 20. Phase 5 may retune openings only if win-rate cannot be hit via card/rival tables.

### 7.2 v1 adapter

If a scenario has a `kpis` object and no `metrics` array, `create` copies that object and uses the existing Meridian bounds:

```
stockPrice (0, ∞), boardResistance (0, 100), ownershipPct (0, 100),
warChest unbounded, mediaHeat (0, 100)
```

Meridian JSON does not need to change in Phase 1.

## 8. Protocols — exact shapes

All live in `backend/app/engine/protocols.py` (or a sibling module imported from there). Implementations never mutate the `state` they are given.

### 8.1 Quarter context (shared)

```python
class QuarterContext(TypedDict, total=False):
    quarter: int                    # 0..7
    news: str
    focusMetrics: list[str]         # dealer / seats may weight these
    interrupt: bool
    interruptCardId: str            # optional forced 4th card
    eventId: str
```

### 8.2 CardDealer

```python
class CardDealer(Protocol):
    def deal(self, state: GameState, quarter_ctx: QuarterContext) -> list[str]:
        """Return 3 card ids, or 4 when quarter_ctx['interrupt'] is true."""
        ...
```

Deterministic default (`SeededCardDealer`):

1. RNG = `random.Random(state["seed"] * 1009 + quarter + 17)`.
2. Eligible = cards whose `requires` ⊆ `state.flags`, whose `once` card has not been played, and whose `id` is not already in the hand.
3. **Unused-family rule:** if any family has not been played this game (`playedFamilies`), force one eligible card from such a family into the hand (pick uniformly among unused families that still have an eligible card). If none remain, skip.
4. **Situation weight:** remaining slots sampled weighted by how many of the card’s delta keys intersect `focusMetrics` (weight `3`) vs not (weight `1`). Without replacement.
5. **Interrupt:** if `interrupt`, append `interruptCardId` when eligible and not already in the hand; else append the next highest-weighted remaining card.
6. Same seed + same history ⇒ same hand.

### 8.3 EventDeck

```python
class Event(TypedDict, total=False):
    id: str
    title: str
    news: str
    quarterMin: int
    quarterMax: int
    deltas: dict[str, float]        # applied by the engine, not the deck
    focusMetrics: list[str]
    interrupt: bool
    interruptCardId: str

class EventDeck(Protocol):
    def draw(self, state: GameState, quarter: int) -> Event:
        ...
```

Seeded shuffle of the scenario `eventDeck` at `create` (RNG `Random(seed + 3)`). Each quarter draws the next event whose `[quarterMin, quarterMax]` contains the quarter (defaults 0..7). Replays with the same seed reproduce the full news sequence. Event `deltas` are applied by the engine at BEAT_INTRO (before deal), then clamped.

This replaces Meridian’s single beat-6 curveball **for v2 only**.

### 8.4 RivalPolicy

```python
class RivalResponse(TypedDict, total=False):
    pressure: float                 # new rivalPressure after this response
    attackId: str | None
    deltas: dict[str, float]
    news: str
    interrupt: bool                 # next quarter gets a 4th card
    interruptCardId: str
    heldOff: bool

class RivalPolicy(Protocol):
    def respond(self, state: GameState, played_card: dict) -> RivalResponse:
        ...
```

No LLM. Policy table is scenario JSON (`rival`). See §10.

### 8.5 ScoringModel

```python
class ScoreBreakdown(TypedDict):
    metricId: str
    weight: float
    opening: float
    current: float
    ratio: float                    # current / opening (opening 0 → ratio 1)
    contribution: float             # weight * ratio

class Score(TypedDict, total=False):
    composite: float
    band: str                       # see §11.3
    breakdown: list[ScoreBreakdown]
    outcome: str                    # won | lost
    failedOn: str                   # early-failure id, if any

class ScoringModel(Protocol):
    def close_out(self, state: GameState) -> Score:
        ...
    def early_failure(self, state: GameState) -> str | None:
        """None if still alive; otherwise a failedOn id."""
        ...
```

`ScoringEngine.summary` for v2 returns this composite (grade field may map band → letter for the existing scorecard event, but the HUD shows the breakdown). Meridian `MeridianScoringEngine.summary` is unchanged.

### 8.6 WarRoomProvider

```python
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
    tally: dict[str, int]           # cardId -> vote count (sums to 6)
    dissents: list[WarRoomDissent]
    confidence: str                 # "low" | "moderate" | "high"

class WarRoomResult(TypedDict):
    seats: list[WarRoomSeatVote]    # exactly the 6 voting seats
    chair: WarRoomChair

class WarRoomContext(TypedDict, total=False):
    state: GameState
    quarter: int
    news: str
    hand: list[Option]              # dealt, public fields + deltas for scoring seats
    interrupt: bool
    npcs: list[str]
    seats: list[dict]               # from scenario.warRoom.seats

class WarRoomProvider(Protocol):
    def convene(self, ctx: WarRoomContext) -> WarRoomResult:
        ...
```

**Hard rules**

- `convene` is pure. It does not write `GameState`.
- `preferredCardId` / `recommendedCardId` must be ids in `ctx["hand"]`.
- Tally counts always sum to 6. **Never unanimous** (forced-dissent rule, §9.3).
- Chair does not cast a 7th vote. Chair synthesizes the six seats.
- Qualitative text only on the wire for players: session strips deltas when emitting SSE.

Session mapping onto existing SSE:

1. `convene` event: `{ beatId, quarter }` (no `motionId` — player has not chosen yet).
2. For each seat in `result.seats`, emit `debate_delta` `{ speakerId: seatId, text: rationale }`. Then one chair line summarizing the recommendation. Existing `DebateDelta` shape. Pacing via `DEBATE_DELAY_MS`.
3. `debate_complete`.
4. New `war_room` event (see §12).
5. `options` + `AWAIT_DECISION`.

Gateway: keep `DEBATE_PROVIDER=gateway` streaming flavor lines if selected; still call `WarRoomProvider.convene` for the structured vote (deterministic unless a later gateway war-room exists). Do not let gateway text pick the card.

Swarm slot: `SwarmWarRoom` documents the contract and **delegates to deterministic** this effort. Same idea as today’s `SwarmDebate` fake stream, but the structured result must stay engine-legal (valid ids, forced dissent).

### 8.7 Factories

Mirror `create_debate_provider()`:

```python
def create_card_dealer(name: str | None = None) -> CardDealer: ...
def create_rival_policy(name: str | None = None) -> RivalPolicy: ...
def create_scoring_model(name: str | None = None) -> ScoringModel: ...
def create_war_room_provider(name: str | None = None) -> WarRoomProvider: ...
def create_event_deck(name: str | None = None) -> EventDeck: ...
```

Unknown names → warning → deterministic. Phase 1 may ship no-op / identity stubs that tests lock; Phase 2–5 fill behavior.

## 9. War room

### 9.1 Seats

Six voting seats + chair. Ids are speaker ids for bubbles and map sprites.

| seatId | Name | Owns (scoring keys) |
|--------|------|---------------------|
| cfo | Capital Markets Partner (CFO) | cash, debt, margin, sharePrice |
| operator | Operating Partner | revenue, marketShare |
| cto | Research / CTO | innovation, integrationRisk |
| hr | Talent / HR | morale |
| gc | Governance Counsel | regulatoryRisk |
| comms | Communications Lead | reputation |
| chair | Chair (no vote) | synthesizes |

Phase 6 map: reuse the boardroom table as the war-room ritual (same tiles as today’s `BOARD_SEATS`). NPC roster for NovaTech: the six seats + chair. Existing Meridian names `ceo` / `analyst` / `partner` are v1-only.

Scenario JSON:

```json
"warRoom": {
  "chair": "chair",
  "seats": [
    { "id": "cfo", "name": "CFO", "owns": ["cash", "debt", "margin", "sharePrice"] },
    { "id": "operator", "name": "Operating Partner", "owns": ["revenue", "marketShare"] },
    { "id": "cto", "name": "Research / CTO", "owns": ["innovation", "integrationRisk"] },
    { "id": "hr", "name": "Talent / HR", "owns": ["morale"] },
    { "id": "gc", "name": "Governance Counsel", "owns": ["regulatoryRisk"] },
    { "id": "comms", "name": "Communications Lead", "owns": ["reputation"] }
  ]
}
```

### 9.2 Seat-ownership vote (deterministic)

For each seat, score each card in the hand:

```
score(card) = Σ  w(metric) * delta(metric)
```

`w` is `+1` for owned metrics the seat wants up (cash, margin, sharePrice, revenue, marketShare, innovation, morale, reputation, confidence) and `-1` for owned metrics the seat wants down (debt, integrationRisk, regulatoryRisk). Unowned metrics contribute 0.

Seat picks the max score. Ties: first card in hand order.

### 9.3 Chair synthesis + forced dissent

1. Tally the six preferred cards.
2. Chair `recommendedCardId` = plurality winner. Tie → the tied card that appears first in the hand.
3. `confidence`: high if winner has ≥5 votes, moderate if 3–4, low if 2 (three-way).
4. **Forced dissent:** if all six match, switch the seat whose **second-best** score is closest to its first (smallest gap) onto that second-best card. If a seat has no distinct second (one-card hand — should not happen), switch the last seat in seats-array order to the second card in the hand.
5. `dissents` = every seat whose `preferredCardId != recommendedCardId` after step 4.

Player may follow or defy. Engine applies the **player** `optionId`. History records `motionId` (player) and `recommendedCardId` (chair).

## 10. Rival + events

### 10.1 Pressure gauge

`rivalPressure` starts at 20. After each played card, the policy table applies a pressure delta, then checks threshold **55**.

```json
"rival": {
  "threshold": 55,
  "defaultPressureDelta": 6,
  "cardPressure": {
    "acquire_challenger": -8,
    "retention_package": -4,
    "trust_campaign": 6,
    "product_bet": 7,
    "leadership_renewal": 6,
    "cost_reset": 5
  },
  "holdOffNews": "The rival watches and holds off.",
  "attacks": [
    {
      "id": "injunction",
      "title": "Vote delay / injunction",
      "deltas": { "confidence": -5, "reputation": -3 },
      "news": "The rival delays the vote and seeks an injunction.",
      "interrupt": false
    },
    {
      "id": "nominate_slate",
      "title": "Rival nominates a short slate",
      "deltas": {},
      "news": "The rival nominates its own short slate mid-quarter.",
      "interrupt": true,
      "interruptCardId": "leadership_renewal"
    },
    {
      "id": "split_offer",
      "title": "Board-seat split offer",
      "deltas": {},
      "news": "Incumbent management offers the rival a board seat to split the activist bloc.",
      "interrupt": false
    }
  ],
  "secondaryTriggers": [
    { "kpi": "confidence", "lte": 45, "attackId": "injunction" },
    { "kpi": "innovation", "lte": 55, "attackId": "injunction" }
  ]
}
```

`respond` algorithm:

1. `delta = cardPressure[played_id] if present else defaultPressureDelta`.
2. `pressure = clamp(current + delta)`.
3. If `pressure >= threshold` **or** any `secondaryTriggers` match post-card metrics, fire the next unused attack in `attacks` order (once each). Apply attack `deltas`, set `interrupt` / `interruptCardId` on the response (pending for next quarter).
4. Else `heldOff: true`, news = `holdOffNews`.

Attacks are authored flavor; the coin flip is there is no coin flip — order + threshold is the whole policy.

### 10.2 Event deck (starter)

At least one event per quarter in `[0, 7]`. Starter list (titles from the worked example; Phase 2 may add more as long as the seed replay test holds):

| quarter | id | news focus | interrupt? |
|---------|----|------------|------------|
| 0 | `sale_thesis` | Rival goes public with a sale thesis | no |
| 1 | `soft_earnings` | Soft earnings; market impatient | no |
| 2 | `nominate_slate` | Rival nominates a short slate | **yes**, 4th card `leadership_renewal` |
| 3 | `split_bloc` | Board-seat offer to split the bloc | no |
| 4 | `interest_bite` | Interest on new debt bites | no |
| 5 | `morale_warning` | Morale near the collapse line | no |
| 6 | `proxy_season` | Annual meeting; both funds lobby advisers | no |
| 7 | `the_vote` | The vote itself | no |

Event news is emitted on `news` SSE at BEAT_INTRO. Interrupt from the event ORs with `state.pendingInterrupt`.

## 11. Scoring

### 11.1 Close-out formula

After quarter 8 (or immediately on early failure):

```
ratio(m) = current(m) / opening(m)     # if opening == 0, ratio = 1.0
composite = Σ weight(m) * ratio(m)
```

Weights (must sum to 100):

| metric | weight |
|--------|--------|
| sharePrice | 40 |
| companyValue | 20 |
| confidence | 15 |
| morale | 10 |
| innovation | 10 |
| reputation | 5 |

**Win:** `composite >= 110` and no early failure. Worked example ≈ 111.6.

Scenario JSON:

```json
"scoring": {
  "winAt": 110,
  "weights": {
    "sharePrice": 40,
    "companyValue": 20,
    "confidence": 15,
    "morale": 10,
    "innovation": 10,
    "reputation": 5
  },
  "earlyFailure": [
    { "id": "cash", "kpi": "cash", "lt": 0 },
    { "id": "price_collapse", "kpi": "sharePrice", "ltRatioOfOpening": 0.40 },
    { "id": "confidence", "kpi": "confidence", "lt": 15 }
  ]
}
```

### 11.2 Derived company value + quarter-close settle

```
interestRateAnnual = 0.05          # scenario.scoring.interestRateAnnual
evMultiple = 8                     # scenario.scoring.evMultiple
ebitda = revenue * margin / 100
interest = debt * interestRateAnnual / 4
cash += ebitda - interest
companyValue = ebitda * evMultiple + cash - debt
```

Share-price settle after cash/interest (additive, so card deltas such as buybacks survive):

```
sharePrice += 0.15 * (confidence - opening.confidence)
sharePrice += 0.10 * opening.sharePrice * (companyValue / opening.companyValue - 1)
```

Then clamp all metrics. Coefficients live in `scenario.scoring.settle` so Phase 5 can tune without code changes.

```json
"settle": {
  "interestRateAnnual": 0.05,
  "evMultiple": 8,
  "confidenceToPrice": 0.15,
  "valueToPrice": 0.10
}
```

### 11.3 Bands

| band | composite | flavor |
|------|-----------|--------|
| constructive | ≥ 110 and morale ratio ≥ 0.9 and innovation ratio ≥ 0.9 | primary target |
| pyrrhic | ≥ 110 but morale or innovation ratio < 0.9 | extraction that killed the host |
| settled | 95–110 | modest / truce |
| failed | < 95 or early failure | lost campaign |

Early failure (`cash < 0`, `sharePrice < 0.4 * opening`, `confidence < 15`) sets `outcome=lost`, `band=failed`, `failedOn=<id>` immediately, even mid-campaign.

Meridian letter grades are v1-only.

### 11.4 Balance target

`simulate.py` runs v2 across seeds and policies `random` / `follow-chair` / `defy-chair`. Mixed-strategy win rate target **40–60%**. Tune card deltas and rival table before openings. Do not retune Meridian.

## 12. Session / SSE additions

Existing events stay: `phase`, `kpi_patch`, `beat`, `news`, `debate_delta`, `debate_complete`, `options`, `next_beat`, `game_end`, `convene`, `board_vote`.

v2 uses `convene` without `motionId`. v1 boardroom `convene` / `board_vote` unchanged.

New event:

```
war_room  →  bus game:warRoom
{
  "quarter": 0,
  "recommendedCardId": "trust_campaign",
  "recommendedLabel": "Win the public narrative",
  "tally": { "trust_campaign": 3, "platform_partnership": 2, "debt_paydown": 1 },
  "confidence": "moderate",
  "dissents": [
    { "seatId": "cfo", "name": "CFO", "preferredCardId": "debt_paydown",
      "preferredLabel": "Pay debt off outright", "concern": "..." }
  ],
  "seats": [
    { "seatId": "cfo", "name": "CFO", "preferredCardId": "...", "preferredLabel": "..." }
  ]
}
```

No deltas. `game_end.summary` for v2 includes `composite`, `band`, `breakdown`.

`GET /sessions/{id}` snapshot: v2 `AWAIT_DECISION` includes `options` and `warRoom` (same public shape). `kpis` is the 13-key map. `beatIndex` is the quarter index.

## 13. Card deck

16 cards, 8 families of 2. `once: true` cards may be played at most once per game.

Deltas below are the **Phase 2 starting table**, taken from the worked example where it quotes numbers and from the glossary otherwise. Phase 5 may edit numbers; it may not add cards or change ids.

### 13.1 Families

| family | cards |
|--------|-------|
| capital_return | `share_buyback`, `debt_buyback` |
| capital_structure | `equity_raise`, `debt_paydown` |
| operating | `cost_reset`, `price_increase` |
| people | `retention_package`, `leadership_renewal` |
| campaign | `trust_campaign`, `execution_sprint` |
| product | `product_bet`, `acquire_challenger` |
| inorganic | `platform_partnership`, `integration_push` |
| portfolio | `divest_legacy`, `compliance_program` |

### 13.2 Cards

Each card: `id`, `family`, `label`, `pros[]`, `cons[]`, `deltas`, `requires[]`, `unlocks[]`, `once`, `consequence`.

| id | label | once | requires | deltas (starting) |
|----|-------|------|----------|-------------------|
| share_buyback | Buy back your own stock | no | | cash −80, sharePrice +4, confidence +2 |
| debt_buyback | Buy back your own debt | no | | cash −40, debt −60, reputation +1 |
| equity_raise | Sell new shares for cash | no | | cash +200, sharePrice −6, confidence −4, reputation −2 |
| debt_paydown | Pay debt off outright | no | | cash −100, debt −100, confidence +1 |
| cost_reset | Cut costs structurally | no | | cash +180, margin +1.5, morale −3, revenue −20 |
| price_increase | Raise prices | no | | cash +40, margin +1.2, confidence −3, marketShare −0.5 |
| retention_package | Pay key people to stay | no | | morale +15, cash −100 |
| leadership_renewal | Change who's in charge | no | | morale −6, confidence +5, integrationRisk +5 |
| trust_campaign | Win the public narrative | no | | reputation +5, confidence +4, cash −25 |
| execution_sprint | Push for a quick operating win | no | | cash −20, revenue +15, morale −4, innovation +2 |
| product_bet | Invest in a real product improvement | no | | innovation +12, cash −150, margin −1 |
| acquire_challenger | Buy a smaller rival or disruptor | **yes** | | innovation +20, marketShare +3, cash −400, debt +200, integrationRisk +25 |
| platform_partnership | Partner instead of buy | no | | cash −40, marketShare +1.5, integrationRisk +8, reputation +2 |
| integration_push | Force the pieces to actually work together | no | `inorganic_live` | integrationRisk −15, margin +1.2, revenue +30, morale −2 |
| divest_legacy | Sell off an old business line | no | | cash +250, revenue −50, marketShare −2, debt −50, integrationRisk −10 |
| compliance_program | Clean up governance and regulatory exposure | no | | cash −40, regulatoryRisk −12, reputation +3, confidence +1 |

`acquire_challenger` and `platform_partnership` unlock `inorganic_live`.

Pros/cons copy follows the campaign-flow glossary (qualitative). Cards never expose deltas on the client.

### 13.3 Knock-on rules

Evaluated after card deltas, before settle. Fire **every quarter they match** (integration drag is per-quarter while over threshold).

```json
"knockOnRules": [
  {
    "id": "morale_collapse",
    "when": { "kpi": "morale", "lt": 40 },
    "deltas": { "innovation": -6, "revenue": -40 },
    "news": "Morale collapse hits innovation and revenue."
  },
  {
    "id": "innovation_flywheel",
    "when": { "kpi": "innovation", "gte": 85 },
    "deltas": { "confidence": 3 },
    "news": "Innovation proof starts lifting confidence on its own."
  },
  {
    "id": "integration_drag",
    "when": { "kpi": "integrationRisk", "gte": 25 },
    "deltas": { "morale": -5, "margin": -0.8 },
    "news": "Integration strain drags morale and margin."
  }
]
```

**Assumption:** integration threshold **25** (worked example: 5 → 30 crosses the drag).

## 14. Scenario JSON v2 schema (sections)

```json
{
  "id": "novatech-proxy-war-01",
  "schemaVersion": 2,
  "title": "NovaTech — Proxy War",
  "maxQuarters": 8,
  "metrics": [ ],
  "cards": [ ],
  "knockOnRules": [ ],
  "eventDeck": [ ],
  "rival": { },
  "scoring": { },
  "warRoom": { },
  "npcs": ["cfo", "operator", "cto", "hr", "gc", "comms", "chair"],
  "zones": ["lobby", "trading_floor", "war_room", "press_bay"]
}
```

No `beats` array. Quarters are procedural. Optional `beats` in a v2 file is ignored.

v1 files keep today’s shape (`kpis`, `beats`, `winCondition`, `loseConditions`, `boardVote`).

## 15. Frontend (Phase 6)

- Default scenario id is configurable: `VITE_SCENARIO_ID` (default `novatech-proxy-war-01`), plus `?scenario=` URL override. Seed stays `?seed=`.
- Re-theme copy/map labels to NovaTech. War room: 6 seat NPCs + chair at the existing table (`BOARD_SEATS` remapped to the six v2 seats + chair).
- HUD: grouped 13-metric panel using `metrics[].group` / `label` (fallback: today’s five Meridian keys if those are the only keys in `kpi_patch`).
- Rival pressure gauge (0–100, threshold mark at 55).
- Quarter counter (`beatIndex + 1` / 8).
- Scorecard: weighted composite breakdown + band, not Meridian A–F (v1 still shows grade).
- News ticker: quarter news, rival attacks, knock-on triggers (existing `news` events).
- Card overlay unchanged except it must layout 4 cards on interrupt.
- Reuse **snap** convene / key-advance / snap-home. Cards show **after** `war_room`, not before (v2). v1 boardroom still shows cards first.
- NovaTech spawns only the seven debate sprites (chair + six seats). Meridian `ceo` / `analyst` / `partner` spawn only on the v1 scenario.
- Board table sits mid-room; speech bubbles clamp into the camera (flip below the speaker if the top would clip).

## 16. Phasing

Each phase leaves a runnable game. `pytest` green. `simulate.py` runs without error. Do not skip Meridian until Phase 6 default switches.

| Phase | Ship | Verify |
|-------|------|--------|
| 0 | This spec, committed | — |
| 1 | Generic metric registry; v2 schema types; protocols + factories; Meridian adapter | existing tests green; Meridian playable |
| 2 | `novatech-proxy-war-01.json`; seeded dealer; quarter pipeline; knock-ons; settle; `simulate.py` v2 | new engine tests; headless simulate; NovaTech playable |
| 3 | Rival pressure policy; seeded event deck; interrupt 4th card | same-seed replay of news + attacks |
| 4 | Deterministic 6-seat war room; SSE `war_room`; gateway still works; swarm stub | debate streams; player can defy chair |
| 5 | Weighted `ScoringModel`; bands; early failure; balance 40–60% | simulate report |
| 6 | NovaTech HUD/map/scorecard; configurable scenario id | `npm run build`; Meridian still loadable via `?scenario=meridian-activist-01` |
| 7 | Deferred: N isolated sessions, same seed, leaderboard; real swarm on `WarRoomProvider` | — |

## 17. Files (expected)

Phase 1–5 backend, roughly:

- `backend/app/engine/protocols.py` — generic metrics + new protocols
- `backend/app/engine/scoring.py` — v1 path unchanged; clamp becomes generic
- `backend/app/engine/quarter.py` — deal / knock-on / settle / apply card (new)
- `backend/app/engine/dealer.py`, `rival.py`, `events.py`, `war_room.py`, `composite.py` (new)
- `backend/app/providers/factory.py` — additional factories (or a sibling `engine/factory.py`)
- `backend/app/api/sessions.py` — v2 quarter pipeline branch
- `backend/scenarios/novatech-proxy-war-01.json`
- `backend/scripts/simulate.py` — v2 policies
- `backend/tests/test_*.py` — dealer, rival, war room, composite, quarter, API

Phase 6 frontend:

- `frontend/src/net/session.ts` — scenario id
- `frontend/src/game/officeMap.ts` — NovaTech labels + seats
- `frontend/src/ui/SidePanel.tsx` — grouped metrics, pressure, quarter
- `frontend/src/ui/Scorecard.tsx` — composite breakdown
- `frontend/src/ui/OptionCards.tsx` — 4-card layout if needed
- `frontend/src/game/OfficeScene.ts` — v2 convene-before-cards

## 18. Success criteria

- Same seed replays the same events, hands, rival attacks, and scores (war-room text may differ only if a non-deterministic provider is selected; default must be identical).
- LLM / swarm cannot mutate metrics.
- Player can follow or defy the chair; only the player’s card hits the engine.
- Early failure lines fire; composite ≥110 is the win.
- Meridian tests remain green throughout.
- Mixed-strategy simulate win rate in 40–60% after Phase 5.

## 19. Shipped notes (post Phase 6)

Playability fixes on this branch, not in the original phase list:

- **Snap convene / snap home** instead of walking. Root cause: arcade collisions with the solid `board_table` and other NPCs prevented `seated` from becoming true, so `meeting` stayed on and locked movement after Q1.
- **Canvas focus** restored on `EXPLORE` so HTML option-card clicks do not steal WASD.
- **Cast:** `npcsForScenario()` — NovaTech = `cfo, operator, cto, hr, gc, comms, chair`. Dual “Research / CTO” was Meridian `analyst` plus NovaTech `cto` on the same map.
- **Bubbles:** table moved from y=3 to y=6; `layoutBubble` keeps text inside `camera.worldView`.

)
