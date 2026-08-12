# Boardroom debate cutscene

Date: 2026-08-13  
Project: `pixel-simulator-game` (Activist Pixel Sim)  
Status: approved for implementation planning

## 1. Problem

On boardroom beats the camera jumps between NPCs frozen in their own rooms. The meeting does not feel like a meeting. The player’s card also applies scoring immediately, so there is no board decision to watch.

## 2. Goal

For beats **4, 7, and 9** only (`zoneId === "boardroom"`):

1. Player submits a motion via the existing option cards.
2. All six agents walk to authored seats at the existing boardroom table.
3. They speak one line at a time; the player advances each line with any key or click.
4. The board votes. A recap overlay shows labels only (no KPI numbers).
5. Scoring applies the **board’s** winning option, not the player’s motion.
6. Agents walk back to their desks and resume wandering.

Beats 1, 2, 3, 5, 6, and 8 stay on today’s loop: interact → debate → cards → `apply(player pick)`.

## 3. Non-goals

- New Phaser scene or second map.
- Skip-all / hold-to-skip.
- Live KPI math inside the vote (no `boardResistance` thresholds in this ship).
- Changing `ScoringEngine.apply` math, option deltas, or win-rate tables.
- Agentic debate or agentic voting (hooks only).
- Adding a third option to beat 7 (it is authored with two cards). Cards always show `available_options` for that beat.

## 4. Phase machine

### 4.1 Non-boardroom (unchanged)

`EXPLORE` → `BEAT_INTRO` → `DEBATE` → `AWAIT_DECISION` → `APPLY` → `EXPLORE` | `GAME_END`

### 4.2 Boardroom

`EXPLORE` → `BEAT_INTRO` → `AWAIT_DECISION` → `CONVENE` → `DEBATE` → `BOARD_VOTE` → `APPLY` → `EXPLORE` | `GAME_END`

Detection: current beat `zoneId == "boardroom"`. Do not special-case beat ids in runtime code.

### 4.3 Boardroom sequence

1. Interact on `zone:boardroom` or `npc:chair` while `EXPLORE` (same trigger rules as today).
2. `BEAT_INTRO` emits the existing `beat` event (situation / title).
3. Server sets `AWAIT_DECISION` and emits `options`. **No debate yet.**
4. Player picks a card. `POST /decide` with `{ optionId }` is accepted. That id is the **motion**, not the applied score.
5. Server stores `motionId` on the session, sets `CONVENE`, emits `convene` `{ beatId, motionId }`.
6. Server does **not** wait for sprites to sit. It sets `DEBATE` and streams `debate_delta` as today. Headless tests never wait on walking or keys.
7. After the provider finishes, server calls `BoardVoteResolver.resolve(ctx)`, emits `board_vote`, sets `BOARD_VOTE`.
8. Server calls existing `engine.apply(state, winningOptionId)`, emits `kpi_patch` and consequence `news`, then `EXPLORE` or `GAME_END`.
9. Session copies vote metadata onto the latest history entry after `apply` (see §6.4). `apply` itself is unchanged.

`decide` before `AWAIT_DECISION`, or a second `decide` in the same beat, still returns 409.

## 5. World choreography

All seat and camera numbers live in `frontend/src/game/officeMap.ts` so they can be nudged without touching the phase machine.

### 5.1 Seats

Existing table: `board_table` at tile (25, 3), 10×2 tiles (covers x 25–34, y 3–4). Existing chairs stay as furniture. NPCs stand on chair tiles (chairs are not solid).

| Actor    | Tile     | Face  | Votes |
|----------|----------|-------|-------|
| chair    | (35, 3)  | left  | yes   |
| ceo      | (26, 1)  | down  | yes   |
| cfo      | (29, 1)  | down  | yes   |
| gc       | (32, 1)  | down  | yes   |
| analyst  | (26, 5)  | up    | no    |
| partner  | (29, 5)  | up    | no    |
| player   | (32, 5)  | up    | no    |

Player is soft-locked at the gallery tile for the whole meeting. WASD does not move them.

### 5.2 Walk-in

On `convene`, each NPC `moveTo`s its seat (existing straight-line mover). Player `moveTo`s the gallery tile. If an actor makes no progress for **1000 ms**, snap them to the seat so the meeting cannot hang.

Camera: `stopFollow`, pan to table center tile **(30, 4)** over **700 ms** (`Sine.easeInOut`), then hold. Do not pan to each speaker.

### 5.3 Line advance

Client buffers `debate_delta` events after `convene` and does **not** auto-show them.

After every actor is seated (or snapped):

1. Show a “press any key” prompt.
2. Each keydown or pointerdown reveals the next buffered line as a speech bubble over that speaker.
3. One bubble at a time. The next input replaces it.
4. If the buffer is empty and `debate_complete` has not arrived, wait; do not skip.
5. Camera stays on the table.
6. When `board_vote` arrives, show the vote overlay immediately. Do not require an extra key after the last line.

Non-boardroom beats still show `debate_delta` immediately (today’s behavior).

No skip-all.

### 5.4 Walk-out

When phase returns to `EXPLORE` (or `GAME_END`), NPCs `moveTo` their `NPCS[].spawn` tile, then resume wander rects. Chair’s spawn is already in the boardroom. Same 1000 ms stuck-snap. Camera resumes follow on the player.

## 6. Vote and scoring

### 6.1 Keep `ScoringEngine.apply` unchanged

`apply(state, option_id)` still applies that option’s authored deltas, flags, and history `optionId`. The only change is **which** id the session passes: the resolver’s winner, not `motionId`.

### 6.2 Pluggable resolver

New protocol, parallel to `DebateProvider`:

```python
class BoardVote(TypedDict, total=False):
    ballots: dict[str, str]       # voterId -> optionId (valid, available only)
    winningOptionId: str
    tieBrokenBy: str | None       # "chair" or omitted/None

class BoardVoteResolver(Protocol):
    def resolve(self, ctx: DebateContext) -> BoardVote: ...
```

`DebateContext` gains `motionId: str` (the player’s card). Dialogue providers may read it. The authored resolver does not use it to change ballots.

Factory: `create_board_vote_resolver(name=None)` lives in `backend/app/engine/board_vote.py` and reads `BOARD_VOTE_RESOLVER` (default `authored`). Unknown values log a warning and use `authored`. Resolved per session at `POST /sessions`, same as debate providers. Do not add this to the debate-provider factory.

This ship implements **only** `AuthoredBoardVote`. A later agentic resolver implements the same `resolve` signature and is selected by env. Phaser, overlays, and `apply` must not import resolver internals.

Fallback: if the selected resolver is not authored and `resolve` raises or returns a missing/invalid `winningOptionId`, log a warning and run `AuthoredBoardVote` once. If authored itself cannot produce a valid winner, use the first available option. Do not recurse.

### 6.3 Authored majority

Voters: `chair`, `ceo`, `cfo`, `gc` only. Analyst and partner never appear in `ballots`.

Each boardroom beat adds:

```json
"boardVote": {
  "voters": ["chair", "ceo", "cfo", "gc"],
  "ballots": { "chair": "<optionId>", "ceo": "<optionId>", "cfo": "<optionId>", "gc": "<optionId>" }
}
```

Resolution:

1. Drop any ballot whose option id is not in `available_options` (flag-gated or unknown).
2. Majority of remaining ballots wins.
3. Tie (including 2–2 and 1–1–1–1) → Chair’s **remaining** ballot wins, and `tieBrokenBy` is `"chair"`.
4. If Chair’s ballot was dropped and the rest still tie, or no valid ballots remain → `winningOptionId` is the first available option. `tieBrokenBy` is omitted.

Authored ballots for `meridian-activist-01`:

| Beat   | chair | ceo | cfo | gc  | Default winner |
|--------|-------|-----|-----|-----|----------------|
| beat-4 | 4b    | 4b  | 4a  | 4b  | 4b (3–1)       |
| beat-7 | 7a    | 7a  | 7a  | 7b  | 7a (3–1)       |
| beat-9 | 9c    | 9c  | 9c  | 9c  | 9c (unanimous) |

Beat 9 uses `9c` (no `requires`) so a full game always has a valid winner even when `9a` / `9b` are gated.

### 6.4 History

After `apply`, the session sets on the latest history entry (does not change `optionId`, which remains the applied option):

- `motionId` — player card
- `ballots` — resolved map (valid votes only)
- `tieBrokenBy` — `"chair"` or omitted

Scorecard may later show “you asked for X, the board passed Y” from labels already on history. No deltas on any new UI.

### 6.5 Dialogue (static)

Keep existing `scriptedLines` for beats 4/7/9. If `motionId` is present, `DeterministicDebate` prepends one Chair line: `The activist proposes '{label}'.` using the motion’s public label. Then existing scripted lines and the current pro/con-per-option lines. Qualitative text only; never deltas.

Gateway / swarm keep their current stream behavior. They receive `motionId` in context for a later prompt change; this ship does not rewrite those prompts.

## 7. Client UI

### 7.1 Option cards

Reuse `OptionCards`. On boardroom beats they appear at `AWAIT_DECISION` **before** debate. Copy can stay “Your move” (motion, not final score). Cards hide when phase leaves `AWAIT_DECISION`.

### 7.2 Vote overlay

New React overlay, same layering as option cards. Shown on `board_vote`. Contents, labels only:

- “Your motion: {motion label}”
- Four rows: voter display name → option label
- “The board adopts: {winning label}”
- If `tieBrokenBy === "chair"`: “Chair breaks the tie.”
- “Press any key”

No KPI numbers, no deltas, no grade. Dismiss on any key or click. Side-panel KPIs may already have updated from `kpi_patch`; that is intended.

### 7.3 Events

New SSE + bus events:

| SSE           | Bus              | Payload |
|---------------|------------------|---------|
| `convene`     | `game:convene`   | `{ beatId, motionId }` |
| `board_vote`  | `game:boardVote` | `{ motionId, motionLabel, votes: [{ speakerId, name, optionId, label }], winningOptionId, winningLabel, tieBrokenBy? }` |

Existing `debate_delta`, `debate_complete`, `options`, `kpi_patch`, `phase` stay. `board_vote.votes[].name` uses this fixed map (same labels as `officeMap.ts`): `ceo` CEO, `cfo` CFO, `gc` General Counsel, `chair` Independent Chair. Client may ignore `name` and map `speakerId` itself; both must match.

`GET /sessions/{id}` snapshot for boardroom `AWAIT_DECISION` includes `options` as today. After decide, snapshot `phase` follows §4.2. Snapshot may include `motionId` while the meeting is in progress.

## 8. Failures

| Case | Behavior |
|------|----------|
| NPC stuck on furniture | Snap to seat (walk-in) or spawn (walk-out) after 1000 ms |
| Empty debate stream | Skip to vote overlay |
| Invalid / gated ballot | Drop that vote; resolve with the rest (§6.3) |
| Resolver throw / bad winner | Fall back to `AuthoredBoardVote` |
| `decide` in the wrong phase | 409 |
| Backend unreachable | Existing news toast; no partial `apply` |

## 9. Tests

Unit (`resolve_board_vote` / `AuthoredBoardVote`):

- 3–1 majority → majority option
- 2–2 → Chair’s ballot, `tieBrokenBy == "chair"`
- 1–1–1–1 → Chair’s ballot, `tieBrokenBy == "chair"`
- Gated ballot dropped; winner from remaining
- All ballots invalid → first available option
- Factory unknown name → authored
- Resolver exception → authored fallback

API:

- Non-boardroom interact still emits `debate_delta` before `options`; `decide` applies the player option and `kpi_patch` follows immediately.
- Boardroom interact emits `options` with **no** preceding `debate_delta`.
- Boardroom `decide` does not emit `kpi_patch` before `board_vote`.
- After boardroom `decide`, `history[-1].optionId` is the authored winner (e.g. beat-4 → `4b`) even when `motionId` is `4a`.
- `history[-1].motionId` equals the posted card.
- Snapshot / SSE payloads never include raw deltas on `options` or `board_vote`.

Headless `simulate.py` goes through the session API (or engine + resolver) and must not wait on Phaser or keys. Win-rate will change because beats 4/7/9 no longer apply the simulated player pick; do not retune deltas in this change. Record the new rate in the implementation notes if `simulate.py` is run.

Frontend: `npm run build` green. Manual: walk to boardroom on beat 4 → cards first → agents sit → key through lines → vote overlay → KPIs update → agents leave.

## 10. Files likely to change

- `backend/app/engine/protocols.py` — `DebateContext.motionId`, `BoardVote`, `BoardVoteResolver`
- `backend/app/engine/board_vote.py` — authored resolver, majority / tie-break, and `create_board_vote_resolver` (new)
- `backend/app/api/sessions.py` — boardroom branch of `_run_beat` / `decide`
- `backend/app/providers/deterministic.py` — chair motion preface when `motionId` set
- `backend/scenarios/meridian-activist-01.json` — `boardVote` on beats 4, 7, 9
- `backend/tests/test_engine.py` / new `test_board_vote.py`
- `backend/tests/test_api.py` / `test_scenario.py`
- `frontend/src/game/officeMap.ts` — `BOARD_SEATS`, camera target, player gallery
- `frontend/src/game/OfficeScene.ts` — convene / dismiss / key-gated bubbles
- `frontend/src/game/eventBus.ts`, `frontend/src/net/session.ts`
- `frontend/src/ui/BoardVoteOverlay.tsx` (new)
- `pixel-simulator-game/SPEC.md` — phase table and new events (implementation plan updates this)

## 11. Success criteria

- Beats 4, 7, 9: cards → sit → key-advanced debate → vote overlay → `apply(winner)` → walk-out.
- Other beats unchanged.
- Deltas never appear on cards, bubbles, or the vote overlay.
- `ScoringEngine.apply` signature and KPI math unchanged.
- Vote result is swappable via `BOARD_VOTE_RESOLVER` without touching Phaser.
- Unit + API tests above pass. `npm run build` green.
