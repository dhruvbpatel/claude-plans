# Pixel Boardroom — Implementation Handoff Plan

> **How to use this file:** This is a self-contained handoff plan. Give the whole file to an orchestrator agent, or give an individual **Task Brief** (T1–T7) to a sub-agent. Every brief lists its objective, inputs, steps, contracts, and acceptance criteria, and does not require any other conversation context. Phase 0 makes the plan portable to any repo — run it first and record its answers in `docs/RECON.md`; later tasks reference those answers instead of hardcoded paths.

---

## 1. Mission & Context

Build a playable, pixel-art, multi-agent boardroom simulation game for financial services:

- **Scenario:** the player is an **activist investor**. Objective: raise the target company's stock price by turn 10 while keeping board trust and a cash war chest alive. (An M&A "acquirer" scenario is a follow-up — same engine, new scenario file.)
- **Loop:** 9–10 turns, <20 minutes total. Each turn: AI board members (CEO, CFO, Risk Officer, Head of Finance, moderated by a **Board Chairman**) debate the situation in a pixel boardroom → player picks 1 of 3–4 option cards → deterministic scoring updates KPIs → world reacts → next turn.
- **Presentation:** AI-Town-style pixel office. Agents walk to the boardroom table for debates, speech bubbles + transcript panel show the discussion, player can walk up to an agent between turns for a 1:1 "lobbying" chat.
- **Base:** fork/adapt **[harishkotra/agent-office](https://github.com/harishkotra/agent-office)** (MIT; Phaser.js canvas + React overlay + Colyseus sync + SQLite; agents driven via an OpenAI-compatible LLM adapter). If the internal repo already contains this fork or a similar pixel-office base, adapt rather than re-fork (Phase 0 decides).

### Hard constraints (all agents must respect these)

1. **LLM access is a Claude API key only.** No Claude Code, no CLI tools, no other providers. Use the official `@anthropic-ai/sdk` (TypeScript). Model: `claude-opus-5` by default; do not silently downgrade models for cost — flag cost concerns to the human instead.
2. **Never put the API key in client/browser code.** All Claude calls go through the server (agent-office already has a server package; route through it).
3. **Deterministic game, LLM-flavored dialogue.** The scenario graph and KPI scoring are hand-authored and deterministic. LLMs generate *debate text and personality only*, never scores. The game must be fully playable (headless) with the LLM mocked.
4. Free/open-source assets only; keep everything web-playable (`npm run dev` → browser).
5. Keep changes additive where possible: new packages/dirs (`engine/`, `scenarios/`, `agents/personas/`) rather than deep rewrites of the base renderer.

---

## 2. Target Architecture

```
[React overlay]  option cards · transcript panel · KPI HUD · scorecard
      │  (state via shared store / events)
[Phaser scene]   office tilemap · agent sprites · pathfinding · speech bubbles
      │
[Server (Node/TS)]
   ├─ engine/        turn state machine + scoring (pure TS, no I/O, unit-tested)
   ├─ scenarios/     activist-01.json (decision graph, deterministic deltas)
   ├─ agents/        Anthropic adapter + persona prompts + Chairman orchestrator
   └─ (Colyseus)     existing realtime sync — reuse; multiplayer is out of MVP scope
```

Turn flow (the core contract everything hangs on):

```
TURN_START → BOARD_DEBATE (Chairman orchestrates; personas speak; streamed to UI)
           → AWAIT_DECISION (player picks option) → APPLY_SCORING (deterministic)
           → WORLD_REACTION (news ticker, sprites disperse) → TURN_START | GAME_END
```

---

## 3. Task Briefs

Dependency order: **T0 → T1 → (T2 ∥ T3) → T4 → T5 → T6 → T7.** T2 and T3 are independent and parallelizable. T5+ depend on T2–T4.

---

### T0 — Repo Recon (run first, output feeds every other task)

**Objective:** Map the target repo and record integration points so the rest of this plan binds to real paths.

**Steps:**
1. Determine the base: is agent-office (or a fork/equivalent pixel-office codebase) already present? If not, vendor/fork `harishkotra/agent-office` per the repo's conventions.
2. Locate and record in `docs/RECON.md`:
   - Package layout (server, game/canvas, UI packages; build tooling; how `npm run dev` works).
   - The LLM adapter: where `OpenAICompatibleAdapter` (or equivalent) lives, its interface (method signatures, streaming support), and where it's constructed/configured.
   - Agent definition: where personalities/system prompts/sprites are declared per agent.
   - The canvas↔UI bridge: how the Phaser scene and React UI share state/events today.
   - Office layout: where maps are defined and whether the drag-and-drop layout editor works.
   - Anything to rip out: autonomous task loops ("hire interns", code execution, web search) — list the modules that drive agent self-direction so T5 can disable them.
3. Confirm the repo runs locally end-to-end with a mock or local LLM before any changes.

**Acceptance:** `docs/RECON.md` exists with all six bullets answered with file paths; the base app runs and agents visibly walk/idle.

---

### T1 — Claude Adapter

**Objective:** Server-side Anthropic adapter conforming to the base repo's LLM adapter interface (from RECON).

**Steps:**
1. `npm install @anthropic-ai/sdk` in the server package. Config via `ANTHROPIC_API_KEY` env var (never committed, never sent to client).
2. Implement `AnthropicAdapter` matching the existing adapter interface. Requirements:
   - Model `claude-opus-5`, streaming via `client.messages.stream(...)` with `.finalMessage()`; forward text deltas to the existing streaming path so speech bubbles can render token-by-token.
   - Persona/system prompt passed as `system` blocks with `cache_control: {type: "ephemeral"}` on the last stable block (debates re-send the same prefix every turn — caching matters).
   - `max_tokens` ~1024 for debate utterances.
   - Typed error handling chain (`RateLimitError` → `APIStatusError` → `APIConnectionError`); on failure, return a graceful fallback line (e.g. "*The CFO shuffles papers…*") so the game never hard-blocks on an API hiccup.
3. Optional fast smoke path: the base's OpenAI-compatible adapter pointed at `https://api.anthropic.com/v1/` with the Anthropic key verifies wiring, but the deliverable is the native adapter.
4. Add a `MockAdapter` (canned persona lines, zero network) selected by env flag — used by tests and by anyone developing without a key.

**Acceptance:** a script or dev route makes one streamed persona call through the adapter and prints the reply; mock adapter passes the same call shape; no key reaches the client bundle.

---

### T2 — Scenario Content: `scenarios/activist-01.json` (parallel-safe; no code deps)

**Objective:** Hand-authored 10-turn activist-investor decision graph. This file *is* the game design.

**Schema (contract for T3/T4 — keep field names exactly):**
```jsonc
{
  "id": "activist-01",
  "title": "Barbarians in the Boardroom",
  "kpis": { "stockPrice": 42.00, "boardTrust": 50, "ownershipPct": 6.5, "warChest": 120 }, // starting values
  "winCondition": { "kpi": "stockPrice", "gte": 60, "byTurn": 10 },
  "loseConditions": [ { "kpi": "boardTrust", "lte": 0 }, { "kpi": "warChest", "lte": 0 } ],
  "turns": [
    {
      "n": 1,
      "situation": "…2–4 sentence setup shown to the player and fed to the debate…",
      "debateTopic": "…one-line question the Chairman poses to the board…",
      "options": [
        {
          "id": "1a",
          "label": "Demand two board seats publicly",
          "deltas": { "stockPrice": +2.5, "boardTrust": -15, "warChest": -5 },
          "consequence": "…one-line outcome text for the news ticker…",
          "unlocks": ["press_war"],          // optional event flags
          "requires": []                     // optional flags gating availability
        }
        // 3–4 options per turn
      ]
    }
    // 10 turns; later turns may branch on flags via "requires"
  ]
}
```

**Design rules:** every option has meaningful trade-offs (no strictly-dominant choices); at least two distinct viable paths to a win; a reckless-path loss reachable by turn ~6; balance so a reasonable mixed strategy finishes in a win ~40–60% of the time. Financial flavor should be realistic (buybacks, divestitures, proxy fights, poison pills, leaks to press, white knights).

**Acceptance:** JSON validates against the schema; a design note at the top of a companion `scenarios/activist-01.md` explains the intended paths and balance reasoning.

---

### T3 — Turn Engine (parallel-safe; pure TS)

**Objective:** `engine/` package: deterministic state machine + scoring. **No I/O, no LLM, no rendering** — takes a scenario object, exposes:

```ts
createGame(scenario): GameState
getPhase(state): "TURN_START"|"BOARD_DEBATE"|"AWAIT_DECISION"|"APPLY_SCORING"|"WORLD_REACTION"|"GAME_END"
availableOptions(state): Option[]          // filters by "requires" flags
applyDecision(state, optionId): GameState  // deltas, flags, clamping, win/lose eval
advancePhase(state): GameState
summary(state): { turn, kpis, history[], outcome: "playing"|"won"|"lost", grade }
```

**Rules:** KPIs clamp to sane bounds; win/lose evaluated after every apply; `history` records every (turn, optionId, deltas) for the end scorecard; a letter grade (S/A/B/C/F) computed from final KPIs + turns survived. State must be serializable (plain JSON) so it can live in the server room state.

**Acceptance:** unit tests cover — every option in the scenario is reachable and terminates by turn 10; KPI math exact; win path, both lose paths, and flag-gated options each tested; a headless driver script plays a scripted 10-turn run with the scenario file from T2 (use a fixture scenario until T2 lands).

---

### T4 — Board Debate Orchestration

**Objective:** `agents/` module that turns a scenario turn into a streamed multi-persona debate, using T1's adapter.

**Steps:**
1. **Personas** (`agents/personas/*.ts`): system prompts for CEO (defensive of management, charismatic), CFO (numbers-first, cautious), Risk Officer (worst-case thinker), Head of Finance (deal mechanics), Chairman (neutral moderator, synthesizes). Each ≤300 words, includes voice/personality and the standing instruction: *stay in character, 2–4 sentences per utterance, never mention being an AI, never reveal or invent numeric score effects.*
2. **Debate script** per turn (deterministic structure, LLM fills the words): Chairman states `debateTopic` → each persona responds once (given: situation, the option labels, prior utterances this turn) → one rebuttal round for the two most opposed personas → Chairman summarizes *without recommending* ("The board awaits your move."). ~7 utterances/turn — keeps a 10-turn game inside the 20-minute budget.
3. Stream each utterance to the UI channel as `{turn, speakerId, text-delta}` events; emit `debate_complete` when done.
4. **1:1 lobbying chat:** reuse the base repo's per-agent chat, but scope it: same persona prompt + current game summary; cap at 3 exchanges; on completion emit a `lobbied:{agentId}` flag the engine may consume (small `boardTrust` delta, defined in engine, not by the LLM).
5. All calls sequential per turn (cheap, ordered); a whole-debate timeout falls back to `MockAdapter` lines so the game never stalls.

**Acceptance:** dev route runs one full turn's debate against the real API and against the mock; transcript event stream matches the contract; utterances stay in character and within length.

---

### T5 — World & UI Integration

**Objective:** Wire engine + debate into the pixel world and React overlay.

**Steps:**
1. **Rip out** the base repo's autonomous agent loop (modules listed in RECON): agents act only when the turn engine or a player chat drives them.
2. **Boardroom map:** using the layout editor or map files, build one office: boardroom (table + 6 seats) + 4 exec offices + player spawn. During `BOARD_DEBATE`, agents pathfind to their seats; during `WORLD_REACTION`/`TURN_START`, they return to offices (existing pathfinding).
3. **Speech bubbles** render the streamed debate deltas above the current speaker; full text mirrors into a scrollable **transcript panel** (React).
4. **Decision UI:** on `AWAIT_DECISION`, show option cards (label + flavor; *never* the numeric deltas). On pick → engine `applyDecision` → consequence line to a **news ticker** → KPI HUD animates (stock sparkline, trust bar, war chest, ownership %).
5. **Game frame:** title/start screen (scenario intro), turn counter, and `GAME_END` scorecard (outcome, grade, decision history, restart button).
6. Player avatar walk + click-agent-to-lobby only enabled between turns.

**Acceptance:** full 10-turn game playable in browser with the mock adapter (no key needed); phases visibly drive sprite behavior; no numeric deltas leak to the player before a decision.

---

### T6 — End-to-End with Live Claude + Balance Pass

**Objective:** Prove the real experience.

**Steps:** play ≥3 full games with the live adapter; record duration (target <20 min), token spend per game, and outcome spread; tune T2 deltas / T4 utterance counts as needed; verify error-fallback path by simulating an API failure mid-debate.

**Acceptance:** a `docs/PLAYTEST.md` with the three runs' timings, costs, outcomes, and any scenario tuning applied.

---

### T7 — Polish & Stretch (only after T6 passes)

Sound cues (gavel at debate start, ticker blip), sprite variety via **Universal LPC Spritesheet Generator** (free, browser) or **Kenney CC0** packs, an `acquirer-01.json` M&A scenario (engine unchanged), and multiplayer via the existing Colyseus layer (players as rival activists) — each as an independent brief.

---

## 4. Contracts Summary (for parallel agents)

| Contract | Owner | Consumers |
|---|---|---|
| Scenario JSON schema (§T2) | T2 | T3, T5 |
| Engine API (§T3) | T3 | T4, T5 |
| Adapter interface (from RECON) + `MockAdapter` | T1 | T4 |
| Debate event stream `{turn, speakerId, delta}` / `debate_complete` | T4 | T5 |
| Phase names (§2 turn flow) | T3 | T4, T5 |

Any agent needing to change a contract must update this file and flag it to the orchestrator — contracts are the only cross-task coupling.

## 5. Definition of Done

- `npm run dev` → browser → complete a 10-turn activist game in under 20 minutes with live Claude-driven board debates.
- Same game completes headless with `MockAdapter` (CI-safe, no key).
- Engine test suite green; scenario balance notes and playtest log committed.
- No API key in client code; no LLM influence on scoring.
