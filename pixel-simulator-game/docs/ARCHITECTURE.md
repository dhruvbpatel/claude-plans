# Activist Pixel Sim — Architecture

Shipped system on `proxy-war-realignment`. Design intent lives in
[`docs/superpowers/specs/2026-08-13-proxy-war-realignment-design.md`](../../docs/superpowers/specs/2026-08-13-proxy-war-realignment-design.md).
Meridian v1 contracts remain in [`SPEC.md`](../SPEC.md).

## 1. What this is

A local-first activist campaign: Phaser 3 office + React HUD, FastAPI session
engine. **Default scenario is NovaTech Proxy War** (`novatech-proxy-war-01`):
8 quarters, a 16-card deck, 13 metrics, a 6-seat war room, a deterministic
rival, weighted composite scoring.

Meridian (`meridian-activist-01`) is still loadable as a regression baseline:
`http://localhost:5173/?scenario=meridian-activist-01`.

**Invariant:** agents advise. Only the deterministic engine mutates `GameState`.
LLM / swarm text never becomes a KPI delta.

## 2. Runtime

```
Browser (Vite :5173)
  Phaser OfficeScene  ←→  gameBus  ←→  React HUD
                              ↑
                     REST + SSE (proxy /sessions)
                              ↓
                    FastAPI (:8000) Session
                         │
         ┌───────────────┼────────────────┐
         ▼               ▼                ▼
   ScoringEngine    WarRoomProvider   DebateProvider
   CardDealer       RivalPolicy       EventDeck
   ScoringModel
```

- Frontend: Vite 8, React 19, Phaser 3.88. REST + SSE, no WebSocket.
- Backend: FastAPI, in-memory `SESSIONS` dict, no database.
- Replay: same `seed` → same events, hands, rival attacks, scores
  (war-room *text* is identical on the deterministic provider).

## 3. Two schema versions

| | v1 Meridian | v2 NovaTech (default) |
|---|---|---|
| File | `backend/scenarios/meridian-activist-01.json` | `backend/scenarios/novatech-proxy-war-01.json` |
| Clock | 9 authored beats | 8 quarters |
| Options | per-beat authored cards | 3-card hand (4 on interrupt) from 16 cards |
| Metrics | 5 KPIs | 13 config-driven metrics + derived company value |
| Meeting | boardroom on beats 4/7/9; **board vote applies** | war room **every quarter**; **player card applies** |
| Scoring | stock target A–F | weighted composite; ≥110 wins |
| Rival | none | pressure-gauge policy table |
| Detection | no `schemaVersion` / beats without `cards` | `schemaVersion: 2` |

`GameState.kpis` is a generic `dict[str, float]`. Callers must not assume keys.

## 4. Quarter pipeline (v2)

```
EXPLORE
  → E on zone:war_room / zone:boardroom / a debate NPC
  → BEAT_INTRO     EventDeck news (seeded)
  → CONVENE        Phaser snaps seats; server does not wait
  → DEBATE         debate_delta SSE (seat rationales + chair)
  → war_room       structured recommendation
  → AWAIT_DECISION 3 or 4 public cards (pros/cons, never deltas)
  → APPLY          player optionId
        card deltas → knock-ons → quarter-close settle → rival.respond
  → EXPLORE | GAME_END
```

Order inside `APPLY`:

1. Played card `deltas` / `unlocks` / `once`.
2. Knock-on rules (morale collapse, innovation flywheel, integration drag).
3. Quarter-close settle (interest, cash, derived company value, share-price nudge).
4. `RivalPolicy.respond` → optional attack + news + interrupt for **next** quarter.
5. Early-failure checks. After quarter 8, close-out score.

v1 boardroom path is unchanged: motion → debate → authored ballots → engine
applies the **board** winner.

## 5. Pluggable protocols

All factories live in `backend/app/engine/factory.py` (plus
`app/providers/factory.py` for debate). Unknown env names log a warning and
fall back to deterministic.

| Component | Env | Default | Role |
|-----------|-----|---------|------|
| Debate | `DEBATE_PROVIDER` | `deterministic` | flavor lines only |
| War room | `WAR_ROOM_PROVIDER` | `deterministic` | per-seat vote + chair synthesis |
| Card dealer | `CARD_DEALER` | `deterministic` | seeded 3/4-card hands |
| Rival | `RIVAL_POLICY` | `deterministic` | pressure gauge + attacks |
| Scoring | `SCORING_MODEL` | `deterministic` | weighted composite |
| Event deck | `EVENT_DECK` | `deterministic` | quarterly news / curveballs |
| Board vote (v1) | `BOARD_VOTE_RESOLVER` | `authored` | Meridian ballots |

A real LangGraph / internal-platform swarm implements `WarRoomProvider.convene`
(and optionally `DebateProvider.stream`). It must return the same structured
shapes. It must not write `kpis`.

`SwarmWarRoom` is a documented stub that delegates to `DeterministicWarRoom`.

### War-room contract (input → output)

Input: read-only `{ state, quarter, news, hand, interrupt, npcs, seats }`.

Output:

```
{
  seats: [{ seatId, preferredCardId, rationale, concern }],
  chair: { recommendedCardId, tally, dissents, confidence }
}
```

Forced dissent: the room is never unanimous. Seat ownership (which metrics
each seat scores) is scenario JSON, not engine code.

## 6. Metrics, cards, rival, score (v2)

**13 metrics** (plus derived `companyValue`): sharePrice, confidence,
reputation, cash, debt, revenue, margin, innovation, marketShare, morale,
integrationRisk, regulatoryRisk, rivalPressure.

**16 action cards** in `novatech-proxy-war-01.json`: family, deltas,
requirements, optional `once`. Dealer is situation-weighted and always
includes one unused family; interrupt deals a 4th card.

**Rival:** pressure starts at 20; default +6 / quarter, card-specific modifiers.
At/above threshold 55 → attack (injunction, nominate slate, split offer).
Q3 `nominate_slate` is an interrupt.

**Close-out:** `sum(weight × current/opening)`. Weights: sharePrice 40,
companyValue 20, confidence 15, morale 10, innovation 10, reputation 5.
≥110 wins. Early fail: cash < 0, sharePrice < 40% of open, confidence < 15.

Bands: constructive / proxy-fight-winner / pyrrhic / failed / greenmailed /
settled / legal — see scoring config.

## 7. Pixel layer

`OfficeScene` is the only Phaser scene. Interaction: WASD, `E` or click.

**NovaTech cast** (only these sprites spawn): chair, cfo, operator, cto, hr,
gc, comms. Meridian leftovers (`ceo`, `analyst`, `partner`) spawn only when
`?scenario=meridian-activist-01`.

**Convene (v2):** pressing E **snaps** the seven seats + player to the board
table. Walking-in was abandoned: NPC–NPC and table collisions left `meeting`
true, which froze WASD/E.

**Dismiss:** on `EXPLORE` / `GAME_END`, leftover debate lines are dropped and
NPCs snap home. Clicking option cards restores canvas keyboard focus.

**Table placement:** board table sits mid-room (tile y≈6), not against the
north wall, so north-row speech bubbles have headroom. `layoutBubble` clamps
into the camera view and flips below the speaker if the top would clip.

**Seats** (`officeMap.ts` `BOARD_SEATS`): authored tile coords around
`board_table`. Camera holds `BOARD_CAMERA` then pans to the speaking NPC.

## 8. Session API

| Method | Path | Notes |
|--------|------|-------|
| POST | `/sessions` | `{ scenarioId?, seed? }` |
| GET | `/sessions/{id}` | snapshot; options only in `AWAIT_DECISION` |
| POST | `/sessions/{id}/interact` | `{ targetId }` |
| POST | `/sessions/{id}/decide` | `{ optionId }` |
| GET | `/sessions/{id}/events` | SSE |

v2 interact also accepts `zone:boardroom` and `zone:war_room` every quarter.

SSE types: `phase`, `beat`, `convene`, `debate_delta`, `war_room`, `options`,
`kpi_patch`, `news`, `next_beat`, `game_end` (plus v1 `board_vote`).

## 9. Frontend map

| File | Job |
|------|-----|
| `frontend/src/net/session.ts` | REST + SSE ↔ gameBus; `?scenario=` / `?seed=` |
| `frontend/src/game/OfficeScene.ts` | world, convene, bubbles, lock |
| `frontend/src/game/officeMap.ts` | rooms, pads, NPC lists, seats |
| `frontend/src/ui/SidePanel.tsx` | phase, 13 metrics, pressure gauge, transcript |
| `frontend/src/ui/OptionCards.tsx` | 3/4-card overlay |
| `frontend/src/ui/WarRoomOverlay.tsx` | chair rec + dissents (clears when cards show) |
| `frontend/src/ui/Scorecard.tsx` | composite breakdown + band |

## 10. How to swap the swarm later

1. Implement `WarRoomProvider` in a new module with `convene(ctx) -> WarRoomResult`.
2. Register it in `create_war_room_provider` under a name (`langgraph`, `platform`, …).
3. Set `WAR_ROOM_PROVIDER=<name>`.
4. Keep emitting `debate_delta` from session using `rationale` text (already done).
5. Do not touch `ScoringEngine.apply`, Phaser, or card JSON.

## 11. Deferred

- Phase 7 competitive leaderboard (N isolated sessions, same seed).
- Real LangGraph / internal-platform swarm.
- Director campaign-shape LLM.
- Persistence / auth.

## 12. Verify

```bash
cd backend && python -m pytest tests/ -q
python scripts/simulate.py          # mixed ~40–60% win band
cd ../frontend && npm run build
```
