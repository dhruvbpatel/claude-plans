# Activist Pixel Sim — SPEC

Agent implementation bible for the **Meridian Dynamics** (v1) 9-beat campaign.

**NovaTech / v2 is the default shipped game.** See
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and
[`../docs/superpowers/specs/2026-08-13-proxy-war-realignment-design.md`](../docs/superpowers/specs/2026-08-13-proxy-war-realignment-design.md).
This file remains the Meridian contract so v1 tests and `?scenario=meridian-activist-01` stay stable.

Keep `ScoringEngine` / `DebateProvider` contracts stable so teammate FastAPI or swarm code can drop in without reshaping the tree.

---

## 1. Mission and hard constraints

**Mission:** Local-first activist fund lead POC at fictitious **Meridian Dynamics** HQ. Player walks a Pixel Agents–style office (Phaser 3), completes a **9-beat** campaign with authored deterministic scoring and pluggable debate providers.

**Hard constraints:**

| Rule | Detail |
|------|--------|
| Local-first | Runnable with `uvicorn` + `vite`; no cloud deploy required for POC |
| LLM | Optional **OpenAI-compatible GitHub Copilot gateway** only — no Claude Code / CLI |
| Scoring | Authored + deterministic; **LLM never sets KPI deltas** |
| Default debate | `DEBATE_PROVIDER=deterministic` (scripted); gateway and swarm are pluggable |
| Engine | Phaser **3** (not a Pixel Agents visualizer fork) |
| Backend | Python **FastAPI** |
| Multiplayer | Out of POC; Phase 7 only after local sign-off |
| UI cards | Show pros/cons only — **never raw deltas** pre-decision |

**Player:** activist fund lead. **Control:** full RPG (WASD, collide, `E`/click interact).

---

## 2. Monorepo layout and run commands

```
frontend/                 # Vite + React + Phaser 3
backend/
  app/main.py             # FastAPI app, CORS, /health
  app/api/                # sessions, decide, debate SSE (Phase 4)
  app/engine/             # pure scoring state machine (Phase 2)
  app/providers/          # deterministic | gateway | swarm stub
  scenarios/              # meridian-activist-01.json
SPEC.md                   # this file
.env.example
```

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example ../.env  # optional
uvicorn app.main:app --reload --port 8000
```

Health: `GET http://127.0.0.1:8000/health` → `{ "status": "ok", "debate_provider": "deterministic" }`

Engine tests: `cd backend && .venv/bin/python -m pytest tests/ -q`

### Frontend

```bash
cd frontend
npm install
npm run dev                 # http://localhost:5173
```

Proxy API in Phase 4 via Vite `server.proxy` or `VITE_API_BASE=http://127.0.0.1:8000`.

Play: WASD + `E`/click. Open http://localhost:5173 with both processes running. Boardroom beats (4, 7, 9) present cards first; any key advances debate lines; the vote overlay is labels only. Full loop: `README.md`.

### Env (see `.env.example`)

| Variable | Default | Purpose |
|----------|---------|---------|
| `DEBATE_PROVIDER` | `deterministic` | `deterministic` \| `gateway` \| `swarm` |
| `CORS_ORIGINS` | Vite localhost | Comma-separated origins |
| `OPENAI_BASE_URL` | — | Copilot gateway chat-completions base URL (Phase 5) |
| `OPENAI_API_KEY` | — | Gateway key (never in client) |
| `GATEWAY_MODEL` | `gpt-4o-mini` | Model for `DEBATE_PROVIDER=gateway` |
| `GATEWAY_TIMEOUT_S` | `20` | Gateway request timeout (connect capped at 5s); on expiry → deterministic fallback |
| `GAME_SEED` | — | Seeded curveball / replay (Phase 6) |
| `DEBATE_DELAY_MS` | `600` | Pacing between streamed debate lines; `0` for headless tests |
| `BOARD_VOTE_RESOLVER` | `authored` | Boardroom vote plugin (`authored` now; later agentic). Unknown → authored |

---

## 3. Scenario JSON schema

File: `backend/scenarios/meridian-activist-01.json`

```jsonc
{
  "id": "meridian-activist-01",
  "title": "Meridian Dynamics — Activist Campaign",
  "kpis": {
    "stockPrice": 42.0,
    "boardResistance": 55,
    "ownershipPct": 6.5,
    "warChest": 120,
    "mediaHeat": 20
  },
  "winCondition": { "kpi": "stockPrice", "gte": 60, "byBeat": 9 },
  "loseConditions": [
    { "kpi": "boardResistance", "gte": 100 },
    { "kpi": "warChest", "lte": 0 }
  ],
  "npcs": ["ceo", "cfo", "gc", "chair", "analyst", "partner"],
  "zones": [
    "lobby", "trading_floor", "war_room",
    "ceo_office", "cfo_office", "gc_office",
    "boardroom", "press_bay"
  ],
  "beats": [
    {
      "id": "beat-1",
      "n": 1,
      "title": "Stake build",
      "zoneId": "trading_floor",
      "npcId": "analyst",          // optional primary interact target
      "situation": "…",
      "debateTopic": "…",
      "scriptedLines": [            // used by DeterministicDebate
        { "speakerId": "analyst", "text": "…" }
      ],
      "options": [
        {
          "id": "1a",
          "label": "Quietly accumulate another 2%",
          "pros": ["…"],
          "cons": ["…"],
          "deltas": {
            "stockPrice": 0.5,
            "boardResistance": 2,
            "ownershipPct": 2,
            "warChest": -15,
            "mediaHeat": 0
          },
          "consequence": "…news ticker line…",
          "requires": [],           // ALL listed flags must be set (AND)
          "unlocks": ["stake_built"]
        }
      ],
      "curveball": false            // beat 6 sets true — see below
    },
    {
      "id": "beat-6",
      "n": 6,
      "title": "Curveball",
      "zoneId": "war_room",
      "npcId": "analyst",
      "situation": "…",
      "debateTopic": "…",
      "scriptedLines": [ /* … */ ],
      "options": [],                // unused — options come from the variant
      "curveball": true,
      "variants": [                 // one picked per session from the seed
        {
          "id": "cv-earnings-miss",
          "title": "Earnings shock",
          "situation": "…",
          "eventDeltas": { "stockPrice": -5, "mediaHeat": 10 },
          "options": [ /* same option shape as above */ ]
        }
      ]
    }
  ]
}
```

**Curveball semantics:** `MeridianScoringEngine.create(scenario, seed=0)` picks one variant via `random.Random(seed)` and stores its id on the state as `curveballVariantId` — same seed always replays the same curveball. On that beat, `available_options` serves the variant's options, and `apply` adds the variant's `eventDeltas` before the chosen option's deltas (both recorded in history).

**Engine rules:** `apply` returns a new state (input untouched) and rejects unknown or flag-gated options. KPIs clamp to `boardResistance`/`ownershipPct`/`mediaHeat` ∈ [0, 100], `stockPrice` ≥ 0; `warChest` may go negative (fires the lose condition). Lose conditions are checked after every beat; the win condition after beat 9; lose takes precedence. `summary` grades: win margin over the stock target ≥10 → A, ≥5 → B, else C; loss by missed target → D, loss by blown condition → F.

**Lobby bonus (Phase 6):** `MeridianScoringEngine.apply_lobby_bonus(state)` grants the authored `LOBBY_BONUS_DELTAS` (`warChest +5`) at most once per `beatIndex`, tracked on the state as `lobbyClaimedBeats`. Returns a new state like `apply`, or `None` if already claimed this beat / game over. Deterministic; deliberately excluded from `stockPrice` so it never disturbs the win-rate balance.

**Balance (Phase 6):** a 2000-seed uniform-random headless run wins ≈57% (target band 40–60%); both archetype paths (proxy fight, settlement diplomacy) win on all three curveball variants with ≥$1.50 margin. Re-measure with `backend/scripts/simulate.py` after any delta change.

**Nine beats (content Phase 2):**

1. Stake build — trading floor  
2. Private letter — CEO  
3. Public thesis — press bay  
4. Board seats vs review — boardroom  
5. Capital return vs breakup — CFO  
6. Mid-game curveball (seeded)  
7. Settle vs proxy — boardroom  
8. Swing holders / ISS pitch — war room  
9. Endgame vote — boardroom  

**KPIs:** `stockPrice`, `boardResistance`, `ownershipPct`, `warChest`, `mediaHeat`.

---

## 4. ScoringEngine / DebateProvider protocols

Python (see `backend/app/engine/protocols.py`):

```python
class ScoringEngine(Protocol):
    def create(self, scenario: Scenario) -> GameState: ...
    def available_options(self, state: GameState) -> list[Option]: ...
    def apply(self, state: GameState, option_id: str) -> GameState: ...
    def summary(self, state: GameState) -> Summary: ...

class DebateProvider(Protocol):
    async def stream(self, ctx: DebateContext) -> AsyncIterator[DebateDelta]: ...
```

**Game phases (non-boardroom):** `EXPLORE` → `BEAT_INTRO` → `DEBATE` → `AWAIT_DECISION` → `APPLY` → `EXPLORE` | `GAME_END`.

**Game phases (boardroom, `zoneId == "boardroom"`):** `EXPLORE` → `BEAT_INTRO` → `AWAIT_DECISION` (player motion) → `CONVENE` → `DEBATE` → `BOARD_VOTE` → `APPLY` (board winner, not the motion) → `EXPLORE` | `GAME_END`.

**Implementations:**

| Module | Class | Phase |
|--------|-------|-------|
| `app/engine/scoring.py` | `MeridianScoringEngine` (done; `StubScoringEngine` kept as alias) | 2 |
| `app/providers/deterministic.py` | `DeterministicDebate` (done: scripted lines + ally-pro / skeptic-con lines per option, paced by `DEBATE_DELAY_MS`) | 4 |
| `app/providers/gateway.py` | `GatewayDebate` (done: OpenAI-compatible streaming + deterministic fallback) | 5 |
| `app/providers/swarm.py` | `SwarmDebate` (stub done: documented contract + plausible fake stream; teammates replace `stream`) | 5 |
| `app/providers/factory.py` | `create_debate_provider(name=None)` — reads `DEBATE_PROVIDER` | 5 |
| `app/engine/board_vote.py` | `AuthoredBoardVote` + `create_board_vote_resolver` / `safe_resolve` — majority + Chair tie-break |  |

**Provider selection:** `create_debate_provider()` resolves `DEBATE_PROVIDER=deterministic|gateway|swarm` per session at `POST /sessions` time (new sessions pick up env changes without a restart). Unknown values log a warning and fall back to `deterministic` — the game is always playable with zero config.

**GatewayDebate (Phase 5):**

- Streams `POST {OPENAI_BASE_URL}/chat/completions` (`stream: true`, model from `GATEWAY_MODEL`, bearer `OPENAI_API_KEY`) via `httpx`.
- Prompt = beat situation + NPC personas + option labels/pros/cons **only**; option `deltas` are never sent, and nothing the LLM says feeds scoring — `ScoringEngine.apply` is the only KPI path.
- The model emits `speaker_id: text` lines; the parser reassembles token chunks into per-line `DebateDelta`s, maps unknown speakers to the beat's `npcId` (or `analyst`), and flags the last delta `done: true`.
- **Fallback:** missing config, connect/read timeout, HTTP error, or an empty/broken stream logs a warning and switches to `DeterministicDebate` mid-beat, so the debate always completes and the game never stalls.

---

## 5. REST + SSE API

Base URL: `http://127.0.0.1:8000` (implemented in Phase 4, `app/api/sessions.py`; sessions are in-memory).

`nextBeat` hint shape (used below): `{ beatId, n, title, zoneId, npcId }` — the client renders "Next: Trading Floor" from it. `null` once the game ends.

### `POST /sessions`

The client reads an optional `?seed=123` URL query at boot and passes it here; the response echoes the effective seed (same seed → same curveball variant). The seed is shown subtly in the side panel and on the scorecard, whose "Run it back (same seed)" button reloads with `?seed=` preserved ("New campaign" clears it).

```json
// request (both fields optional; seed defaults to a random int)
{ "scenarioId": "meridian-activist-01", "seed": 42 }

// response
{
  "sessionId": "uuid",
  "phase": "EXPLORE",
  "beatIndex": 0,
  "kpis": { "stockPrice": 42.0, "boardResistance": 55, "ownershipPct": 6.5, "warChest": 120, "mediaHeat": 20 },
  "flags": [],
  "seed": 42,
  "nextBeat": { "beatId": "beat-1", "n": 1, "title": "Stake build", "zoneId": "trading_floor", "npcId": "analyst" }
}
```

### `GET /sessions/{id}`

Snapshot for polling/headless play: `{ sessionId, phase, beatIndex, kpis, flags, outcome, nextBeat }` plus `options` (public shape, no deltas) when phase is `AWAIT_DECISION`.

### `POST /sessions/{id}/interact`

A beat activates when `targetId` matches the current beat's `zone:{zoneId}` or `npc:{npcId}` trigger (and `beatId`, if sent, matches). On accept, the server runs BEAT_INTRO → DEBATE → AWAIT_DECISION in the background, streaming over SSE.

```json
// request (beatId optional)
{ "targetId": "npc:ceo", "beatId": "beat-2" }

// response (accepted)
{ "phase": "BEAT_INTRO", "beatId": "beat-2", "accepted": true }

// response (wrong target / wrong phase)
{ "phase": "EXPLORE", "beatId": "beat-2", "accepted": false, "nextBeat": { "…": "…" } }
```

**Lobby bonus (Phase 6):** `{ "targetId": "zone:lobby" }` during `EXPLORE` (when the lobby is not the current beat's zone) grants the engine's once-per-beat bonus instead of activating a beat. Response adds `"lobbyBonus": "granted" | "spent"` with `accepted: false`; on grant the server emits `kpi_patch` plus a `news` line over SSE. Claims reset each time a beat is applied.

### `POST /sessions/{id}/decide`

Only valid in `AWAIT_DECISION` (else **409**); unknown/flag-gated option → **400**.

On a **boardroom** beat (`zoneId == "boardroom"`), `optionId` is the player's **motion**. The server emits `convene`, streams debate (with `motionId` in the provider context), emits `board_vote`, then `apply`s the resolver winner. History records `motionId` / `ballots` / optional `tieBrokenBy` on the applied entry. `ScoringEngine.apply` is unchanged.

```json
// request
{ "optionId": "2a" }

// response
{
  "phase": "EXPLORE",
  "kpis": { "...": "..." },
  "consequence": "…",
  "outcome": "playing"
}
```

### `GET /sessions/{id}/events` (SSE)

Named events with JSON `data:` payloads. Events emitted before the client connects are buffered per session, so nothing is lost on late subscribe. Keepalive comments every 15s.

| `type` | Payload highlights |
|--------|--------------------|
| `phase` | `{ phase }` |
| `beat` | `{ beatId, n, title, situation, zoneId, npcId }` — at BEAT_INTRO; curveball variant's title/situation merged in |
| `debate_delta` | `{ speakerId, text }` |
| `debate_complete` | `{}` |
| `convene` | `{ beatId, motionId }` — boardroom only; agents walk to seats |
| `board_vote` | `{ motionId, motionLabel, votes: [{ speakerId, name, optionId, label }], winningOptionId, winningLabel, tieBrokenBy? }` — **no deltas** |
| `options` | `{ options: [{ id, label, pros, cons }] }` — **no deltas** |
| `kpi_patch` | `{ kpis }` |
| `news` | `{ text }` — consequences, curveball headline, lobby bonus, hints; feeds the toasts **and** the persistent bottom news ticker |
| `next_beat` | nextBeat hint — on session start and each return to EXPLORE |
| `game_end` | `{ outcome, grade, summary }` |

Example stream line:

```
event: debate_delta
data: {"speakerId":"ceo","text":"We reject your premise."}
```

### `GET /health`

```json
{ "status": "ok", "debate_provider": "deterministic" }
```

---

## 6. Phaser ↔ React event bus

Client bridge (Phase 3–4): a tiny EventTarget / mitt bus shared by Phaser scene and React HUD.

| Event | Direction | Payload |
|-------|-----------|---------|
| `game:interact` | Phaser → React/API | `{ targetId, beatId? }` — `beatId` omitted client-side until Phase 4 maps beats |
| `game:prompt` | Phaser → React | `{ targetId, label }` \| `null` — show/hide interact prompt (Phase 3) |
| `game:phase` | React/store → Phaser | `{ phase }` — soft-lock input when not `EXPLORE` |
| `game:speech` | SSE → Phaser | `{ speakerId, text }` — speech bubble (ignored during a boardroom meeting) |
| `game:debateLine` | SSE → Phaser | `{ speakerId, text }` — queued for key-advance during a meeting |
| `game:convene` | SSE → Phaser | `{ beatId, motionId }` — walk to seats, hold camera on the table |
| `game:boardVote` | SSE → React | vote recap overlay (labels only) |
| `game:kpi` | SSE → React | `{ kpis }` |
| `game:options` | SSE → React | `{ options }` |
| `game:news` | SSE → React | `{ text }` — consumed by both `ToastLog` and the persistent `NewsTicker` bottom bar (ticker seeds itself with ambient headlines, rotates every 6s, jumps to fresh news) |
| `game:session` | client → React | `{ sessionId, seed }` — emitted once after `POST /sessions`; side panel + scorecard read the seed from it |
| `game:end` | SSE → React | `{ outcome, grade, summary }` |
| `game:beat` | SSE → React | `{ beatId, n, title, situation }` — beat intro panel |
| `game:nextBeat` | SSE → React | nextBeat hint — "Next: Trading Floor" |
| `ui:decide` | React → API | `{ optionId }` |
| `ui:inputLock` | React → Phaser | `{ locked: boolean }` |

Free walk only in `EXPLORE`; soft-lock during `DEBATE` / `AWAIT_DECISION` / `CONVENE` / `BOARD_VOTE`, and while a boardroom meeting is still showing queued lines.

---

## 7. NPC / zone ID table

| ID | Kind | Role / location |
|----|------|-----------------|
| `ceo` | NPC | CEO |
| `cfo` | NPC | CFO |
| `gc` | NPC | General Counsel |
| `chair` | NPC | Independent Chair |
| `analyst` | NPC | Your Analyst |
| `partner` | NPC | Activist Partner |
| `lobby` | zone | Lobby (once-per-beat bonus, Phase 6) |
| `trading_floor` | zone | Stake build |
| `war_room` | zone | Swing / ISS |
| `ceo_office` | zone | Private letter |
| `cfo_office` | zone | Capital return / breakup |
| `gc_office` | zone | Legal / GC |
| `boardroom` | zone | Seats, settle/proxy, endgame |
| `press_bay` | zone | Public thesis |

Interact payload `targetId` form: `npc:{id}` or `zone:{id}`.

---

## 8. Phase checklist & acceptance

| Phase | Deliverable | Acceptance | Status |
|-------|-------------|------------|--------|
| 0 | Recon | Greenfield or adapter map recorded | Done (`docs/RECON.md`) |
| 1 | Scaffold + SPEC | `uvicorn` health OK; `npm run build` or install OK | Done |
| 2 | ScoringEngine + full scenario JSON + pytest | Deltas, win/lose, flags, seeded curveball, headless full run | Done |
| 3 | Phaser office | Tilemap, WASD, 6 NPCs, zone pads, camera — empty office playable | Done |
| 4 | REST/SSE + deterministic debate | Full 9-beat game offline, no API key | Done |
| 5 | GatewayDebate + SwarmDebate stub | Env switch; gateway timeout → deterministic | Done |
| 6 | Polish | Ticker, lobby bonus, seed URL, balance ~40–60% mixed wins | Done |
| 7 | Multiplayer | Only after POC signed off | Not started |

---

## 9. Swarm / teammate integration notes

1. Implement `SwarmDebate.stream(ctx: DebateContext) -> AsyncIterator[DebateDelta]` in `app/providers/swarm.py` — keep the signature; the shipped stub emits a plausible fake multi-agent stream so `DEBATE_PROVIDER=swarm` is playable today, and its module docstring documents the full contract.
2. Emit deltas as `{ "speakerId": "<npc id>", "text": "<chunk or utterance>" }`; final chunk may set `"done": true`. `speakerId` must come from `ctx["npcs"]` (ceo, cfo, gc, chair, analyst, partner) or the speech bubble cannot be placed.
3. Map line-graph events → deltas: agent utterances/tokens become `DebateDelta`s; internal events (routing, tool calls, scratchpads) are not emitted; graph completion may set `done: true` on the last delta (the session loop also closes the debate when the iterator is exhausted).
4. Set `DEBATE_PROVIDER=swarm`.
5. **Do not** compute KPI deltas in the swarm — call into `ScoringEngine.apply` only via the session API path after the player decides. `ctx["options"]` includes engine `deltas`; your agents must not surface or act on them (qualitative pros/cons only).
6. Line-graph orchestration may live in a separate package; adapt at the `DebateProvider` boundary only.
7. If teammates already ship FastAPI routes, wrap them behind the contracts in §4–§5 rather than forking `ScoringEngine`.

---

## 10. Definition of Done (POC)

- Local `backend` + `frontend` → complete 9-beat activist game in &lt;20 minutes with WASD and boardroom/office interacts  
- Works with `DEBATE_PROVIDER=deterministic` and no gateway key  
- Engine tests green; KPI math independent of LLM  
- This `SPEC.md` sufficient for another agent to continue or swap in swarm scoring/orchestration  
- No multiplayer required  

**Out of scope for POC:** Claude Code hooks, Pixel Agents VS Code extension, deploying multiplayer, Capital-in-Peril / M&A scenarios (same engine later via new JSON only).
