# Activist Pixel Sim — Complete Rebuild Handoff

This document is self-contained. An agent with **no access to the original code** can rebuild the finished game from this file alone: same decisions, same look and feel, same playability, same content, same contracts. Everything authored (scenario content, map coordinates, color palettes, balance numbers) is included verbatim. Where implementation details are obvious (React boilerplate, standard FastAPI wiring), use your judgment — but do not deviate from anything specified here.

---

## 1. What you are building

A **local-first activist-investor pixel RPG**. The player is an activist fund lead running a hostile campaign against fictitious **Meridian Dynamics**. They walk a top-down pixel-art office HQ (Pixel Agents / Stardew-office vibe), talk to executives, and play through a **9-beat campaign**: build a stake, pressure the board, survive a seeded curveball, and win an endgame vote — driving the stock from $42 to $60+ without blowing up their war chest or maxing out board resistance.

**The player experience, end to end:**

1. Game boots into a dark fintech-styled page: title bar ("Meridian Dynamics — Activist Campaign"), the Phaser canvas center-left, a side panel on the right (phase badge, 5 KPI cards, transcript, next-objective hint, seed display), a scrolling news ticker along the bottom ("MRDN WIRE"), and toast notifications top-left over the canvas.
2. Player spawns in the lobby, walks with WASD/arrows, collides with walls and furniture. Camera follows. Six named NPCs wander their offices.
3. Side panel says "Next: Stake build — go to Trading Floor". Player walks there; near the zone pad (a highlighted floor mat) a pill-shaped prompt appears: "E · Trading Floor". Press `E` (or click).
4. Movement soft-locks. A beat-intro panel shows the situation. Then a **debate**: NPCs argue in speech bubbles above their heads in-world (camera pans to each speaker), mirrored line-by-line in the side-panel transcript. Allies (analyst, partner) argue pros; skeptics (CEO, CFO, GC, chair) argue cons.
5. Option cards appear (2–4): label, pros, cons — **never numbers**. Player picks one.
6. KPI cards flash green/red with delta badges as the authored numbers land. A consequence headline hits the ticker and toasts. Back to free-walk, next objective shown.
7. Beat 6 is a curveball: one of three crisis variants (chosen by the session seed) with its own shock deltas and response options.
8. Visiting the lobby pad between beats grants a once-per-beat +$5M war-chest bonus ("one favor per move").
9. After beat 9 (or an early bust): a scorecard — outcome, letter grade A–F, final KPIs, per-beat decision history, seed, "Run it back (same seed)" and "New campaign" buttons.

A full run takes under 20 minutes and works completely offline — no API key, no network.

---

## 2. Hard constraints (do not violate)

| Rule | Detail |
|------|--------|
| Local-first | Runs with `uvicorn` + `vite` only; no cloud services required |
| Deterministic scoring | All KPI math is authored in the scenario JSON and applied by a pure Python engine. **An LLM never sets or influences KPI deltas.** |
| LLM optional | The only LLM integration is an optional OpenAI-compatible gateway (`OPENAI_BASE_URL` + `OPENAI_API_KEY`) for debate *dialogue flavor* — behind an env flag, with automatic fallback |
| Default provider | `DEBATE_PROVIDER=deterministic` (scripted). Game is fully playable with zero config |
| No delta leaks | Option cards, debate text, SSE `options` events, and session snapshots expose label/pros/cons only. Raw deltas never leave the server pre-decision |
| Engine purity | Scoring engine is pure Python: no FastAPI, no Phaser, no LLM imports |
| Stable contracts | `ScoringEngine` and `DebateProvider` protocols (§8, §9) are frozen so teammate code (FastAPI routes, line-graph swarm) can drop in |
| Multiplayer | Out of scope entirely (was "phase 7 after sign-off"; do not build) |

---

## 3. Tech stack

- **Frontend:** Vite + React 19 + TypeScript + **Phaser 3** (3.88.x). No other runtime deps. Lint with oxlint (or eslint — not load-bearing).
- **Backend:** Python 3.11+, FastAPI ≥0.115, uvicorn, pydantic v2, httpx (used by the gateway provider and tests), python-dotenv, pytest. No `openai` package — the gateway speaks raw HTTP via httpx.
- **No database.** Sessions are in-memory dicts. No auth.
- **No downloaded art assets.** All textures are generated at runtime onto canvases (§12). Zero licensing concerns.

Repo layout:

```
frontend/                     # Vite + React + Phaser 3
  src/game/                   #   PhaserGame.tsx (mount), OfficeScene.ts, officeMap.ts, textures.ts, eventBus.ts
  src/net/session.ts          #   session bootstrap + SSE→bus bridge
  src/ui/                     #   SidePanel, OptionCards, InteractPrompt, ToastLog, NewsTicker, Scorecard
backend/
  app/main.py                 # FastAPI app, CORS, /health
  app/api/sessions.py         # session REST + SSE + phase machine
  app/engine/                 # protocols.py, scoring.py  (pure)
  app/providers/              # protocols.py, deterministic.py, gateway.py, swarm.py, factory.py
  scenarios/meridian-activist-01.json
  scripts/simulate.py         # headless balance simulator
  tests/                      # pytest
SPEC.md                       # living contract doc (recreate from this handoff)
.env.example
```

Env vars (`.env.example`):

| Variable | Default | Purpose |
|----------|---------|---------|
| `DEBATE_PROVIDER` | `deterministic` | `deterministic` \| `gateway` \| `swarm` |
| `CORS_ORIGINS` | Vite localhost | comma-separated origins |
| `OPENAI_BASE_URL` | — | gateway chat-completions base URL |
| `OPENAI_API_KEY` | — | gateway key (server-side only, never in client) |
| `GATEWAY_MODEL` | `gpt-4o-mini` | model for gateway provider |
| `GATEWAY_TIMEOUT_S` | `20` | gateway read timeout (connect capped at 5s) → fallback |
| `DEBATE_DELAY_MS` | `600` | pacing between streamed debate lines; set `0` in tests |

Run commands: backend `cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/uvicorn app.main:app --reload --port 8000`; frontend `cd frontend && npm install && npm run dev` (http://localhost:5173, Vite proxies `/health` and `/sessions*` to :8000).

---

## 4. Recommended build order

Build in this order; each stage has a verification gate. A single agent does all stages including final testing.

1. **Scaffold** — both apps boot; `GET /health` → `{"status":"ok","debate_provider":"deterministic"}`; `npm run build` green.
2. **Engine + scenario** — pure engine (§8) + full scenario JSON (§7) + pytest (§15). Gate: all engine tests green, headless full 9-beat run works.
3. **Pixel office** — walkable office (§12–13) with NPCs, zone pads, interact prompt, before any backend wiring. Gate: walk every room, prompts appear, `game:interact` fires.
4. **Wire the loop** — session REST + SSE + phase machine + deterministic debate (§9–11). Gate: full 9-beat game completable in the browser offline; scripted API run reaches `GAME_END`.
5. **Providers** — gateway + swarm stub + factory (§9). Gate: provider unit tests green (mocked HTTP, no network).
6. **Polish + balance** — ticker, lobby bonus, seed replay (§14); verify balance against §16 targets with the simulator.

---

## 5. Core game model

**KPIs** (shown as cards, in this order): `stockPrice` ($, float), `boardResistance` (0–100), `ownershipPct` (%), `warChest` ($M), `mediaHeat` (0–100).

**Win:** `stockPrice ≥ 60` evaluated after beat 9. **Lose (checked after every beat, takes precedence):** `boardResistance ≥ 100` or `warChest ≤ 0`.

**Session phase machine:**

```
EXPLORE → BEAT_INTRO → DEBATE → AWAIT_DECISION → APPLY → EXPLORE | GAME_END
```

Free walking only in `EXPLORE`; player input soft-locked in every other phase. `APPLY` is instantaneous server-side (KPI patch + consequence news + phase event). The curveball is not a separate phase — beat 6 itself is the curveball: its seeded variant's situation streams at intro and its `eventDeltas` apply inside the engine when the option is applied.

**Beats and where they happen** (trigger = the beat's zone pad *or* its primary NPC):

| # | Title | Zone | NPC |
|---|-------|------|-----|
| 1 | Stake build | `trading_floor` | `analyst` |
| 2 | Private letter | `ceo_office` | `ceo` |
| 3 | Public thesis | `press_bay` | `partner` |
| 4 | Board seats vs review | `boardroom` | `chair` |
| 5 | Capital return vs breakup | `cfo_office` | `cfo` |
| 6 | Curveball (seeded, 3 variants) | `war_room` | `analyst` |
| 7 | Settle vs proxy | `boardroom` | `chair` |
| 8 | Swing holders / ISS | `war_room` | `partner` |
| 9 | Endgame vote | `boardroom` | `chair` |

**Cast** (id → role): `ceo` Marcus Hale, CEO (antagonist); `cfo` Priya Ramanathan, CFO (pragmatic); `gc` General Counsel (hostile-formal); `chair` Diane Okafor, Independent Chair (neutral broker); `analyst` Your Analyst (ally, numbers); `partner` Activist Partner (ally, aggressive). Interact target ids are `npc:{id}` / `zone:{id}`.

---

## 6. ID tables (frozen)

NPCs: `ceo`, `cfo`, `gc`, `chair`, `analyst`, `partner`.
Zones: `lobby`, `trading_floor`, `war_room`, `ceo_office`, `cfo_office`, `gc_office`, `boardroom`, `press_bay`.
(`gc_office` and `lobby` never trigger beats — GC office is flavor; lobby is the bonus zone.)

---

## 7. Scenario content — `backend/scenarios/meridian-activist-01.json` (verbatim, authoritative)

This is the complete authored game content **after the balance pass** — reproduce it exactly, including every delta. Schema notes follow in §8.

```json
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
    "lobby", "trading_floor", "war_room", "ceo_office",
    "cfo_office", "gc_office", "boardroom", "press_bay"
  ],
  "beats": [
    {
      "id": "beat-1",
      "n": 1,
      "title": "Stake build",
      "zoneId": "trading_floor",
      "npcId": "analyst",
      "situation": "Meridian Dynamics trades at 42 — half of sum-of-parts. Your fund holds 6.5%. Time to size the position before anyone notices the accumulation.",
      "debateTopic": "How fast and how loud do we build the stake?",
      "scriptedLines": [
        { "speakerId": "analyst", "text": "Volume is thin. We can add 2% without moving the tape if we drip it over two weeks." },
        { "speakerId": "partner", "text": "Or we file the 13D now and let the pop pay for the position." }
      ],
      "options": [
        {
          "id": "1a",
          "label": "Quietly accumulate to 8.5%",
          "pros": ["Cheap entry before the market catches on", "Board stays asleep a little longer"],
          "cons": ["Ties up a big slug of the war chest", "Slow — no immediate catalyst"],
          "deltas": { "stockPrice": 0.5, "boardResistance": 2, "ownershipPct": 2, "warChest": -15, "mediaHeat": 0 },
          "consequence": "Unusual volume in MRDN goes unremarked; your stake quietly crosses 8%.",
          "requires": [],
          "unlocks": ["stake_built"]
        },
        {
          "id": "1b",
          "label": "Build exposure via swaps and options",
          "pros": ["Far cheaper on cash", "Keeps footprint nearly invisible"],
          "cons": ["Less hard voting power when it matters", "Disclosure fight if the GC smells derivatives"],
          "deltas": { "stockPrice": 0.5, "boardResistance": 1, "ownershipPct": 1.5, "warChest": -8, "mediaHeat": 2 },
          "consequence": "Prime brokers whisper about a mystery buyer in Meridian derivatives.",
          "requires": [],
          "unlocks": ["stake_built"]
        },
        {
          "id": "1c",
          "label": "File the 13D now and announce 9%",
          "pros": ["Instant credibility and a stock pop", "Forces the board to engage on your clock"],
          "cons": ["Board goes straight into bunker mode", "You pay top-of-tape prices to finish the stake"],
          "deltas": { "stockPrice": 2.5, "boardResistance": 6, "ownershipPct": 2.5, "warChest": -18, "mediaHeat": 12 },
          "consequence": "MRDN jumps 6% as your 13D hits the wire: 'intends to engage with management.'",
          "requires": [],
          "unlocks": ["stake_built", "public_stance"]
        }
      ],
      "curveball": false
    },
    {
      "id": "beat-2",
      "n": 2,
      "title": "Private letter",
      "zoneId": "ceo_office",
      "npcId": "ceo",
      "situation": "CEO Marcus Hale agreed to a meeting. He thinks you are a tourist. The tone of your first letter will set the temperature of the whole campaign.",
      "debateTopic": "Constructive engagement or a shot across the bow?",
      "scriptedLines": [
        { "speakerId": "ceo", "text": "We always welcome shareholder input. Through the proper channels, of course." },
        { "speakerId": "analyst", "text": "Translation: he'll bury us in IR boilerplate unless the letter has teeth." }
      ],
      "options": [
        {
          "id": "2a",
          "label": "Send a constructive private letter",
          "pros": ["Keeps a settlement path open", "Signals sophistication to the board"],
          "cons": ["Easy for Hale to slow-walk", "No public pressure backing it"],
          "deltas": { "stockPrice": 1, "boardResistance": 3, "ownershipPct": 0, "warChest": -2, "mediaHeat": 5 },
          "consequence": "Hale acknowledges your letter and promises a 'thorough review of the ideas.'",
          "requires": [],
          "unlocks": ["private_diplomacy"]
        },
        {
          "id": "2b",
          "label": "Send a blunt demand letter",
          "pros": ["No ambiguity about your intentions", "Rattles the C-suite into mistakes"],
          "cons": ["Board circles the wagons early", "Leaks make you look hostile"],
          "deltas": { "stockPrice": 1.5, "boardResistance": 10, "ownershipPct": 0, "warChest": -3, "mediaHeat": 8 },
          "consequence": "Your demand letter leaks within hours; Meridian calls it 'short-term financial engineering.'",
          "requires": [],
          "unlocks": ["hardline"]
        },
        {
          "id": "2c",
          "label": "Back-channel through the independent Chair",
          "pros": ["Builds an ally inside the boardroom", "Keeps Hale guessing"],
          "cons": ["Slow and deniable", "Chair may report everything back to Hale"],
          "deltas": { "stockPrice": 0.5, "boardResistance": -2, "ownershipPct": 0, "warChest": -2, "mediaHeat": 0 },
          "consequence": "Chair Diane Okafor takes your call and listens longer than expected.",
          "requires": [],
          "unlocks": ["chair_ally"]
        }
      ],
      "curveball": false
    },
    {
      "id": "beat-3",
      "n": 3,
      "title": "Public thesis",
      "zoneId": "press_bay",
      "npcId": "partner",
      "situation": "The private track is moving slowly. Your 80-page thesis — margins, capital misallocation, the failing Orbital division — is ready. Publishing changes the campaign forever.",
      "debateTopic": "Go public with the full thesis, leak selectively, or hold fire?",
      "scriptedLines": [
        { "speakerId": "partner", "text": "The deck is airtight. Page 44 alone — Orbital's ROIC — ends the debate." },
        { "speakerId": "analyst", "text": "Once it's public there is no settling quietly. Everyone will be watching the tape." }
      ],
      "options": [
        {
          "id": "3a",
          "label": "Publish the full 80-page thesis",
          "pros": ["Sets the narrative for the entire street", "Other holders start doing your work for you"],
          "cons": ["Board hardens — no more quiet deals", "You own every number in that deck now"],
          "deltas": { "stockPrice": 4, "boardResistance": 8, "ownershipPct": 0, "warChest": -6, "mediaHeat": 25 },
          "consequence": "MERIDIAN'S LOST DECADE hits every terminal; sell-side scrambles to update models.",
          "requires": [],
          "unlocks": ["public_campaign"]
        },
        {
          "id": "3b",
          "label": "Leak selective pages to a friendly columnist",
          "pros": ["Pressure without full commitment", "Deniability if numbers get challenged"],
          "cons": ["Half the impact of the full deck", "Journalists hate being used and remember it"],
          "deltas": { "stockPrice": 2.5, "boardResistance": 4, "ownershipPct": 0, "warChest": -3, "mediaHeat": 12 },
          "consequence": "A well-sourced column asks why Meridian's Orbital division still exists.",
          "requires": [],
          "unlocks": ["media_whisper"]
        },
        {
          "id": "3c",
          "label": "Hold fire — keep working the private track",
          "pros": ["Preserves goodwill from the letter", "Board owes you one for the restraint"],
          "cons": ["Zero public pressure", "Street starts wondering if you've gone soft"],
          "deltas": { "stockPrice": 0.5, "boardResistance": -3, "ownershipPct": 0, "warChest": -1, "mediaHeat": -5 },
          "consequence": "Silence from your fund; Meridian's IR team exhales — for now.",
          "requires": ["private_diplomacy"],
          "unlocks": ["good_faith"]
        }
      ],
      "curveball": false
    },
    {
      "id": "beat-4",
      "n": 4,
      "title": "Board seats vs review",
      "zoneId": "boardroom",
      "npcId": "chair",
      "situation": "Chair Okafor convenes a governance session. The board will entertain 'reasonable requests.' This is the moment to convert pressure into structural power.",
      "debateTopic": "Demand board seats, a strategic review, or both?",
      "scriptedLines": [
        { "speakerId": "chair", "text": "The board is prepared to discuss governance enhancements. Within reason." },
        { "speakerId": "gc", "text": "Any demand letter will be evaluated against our fiduciary obligations — all of them." },
        { "speakerId": "partner", "text": "Seats give us permanent leverage. A review gives us a catalyst. Pick your weapon." }
      ],
      "options": [
        {
          "id": "4a",
          "label": "Demand two board seats",
          "pros": ["Permanent inside leverage", "Signals long-term commitment to other holders"],
          "cons": ["Board fights nominee fights hardest", "Insiders get slow-rolled by committee"],
          "deltas": { "stockPrice": 2.5, "boardResistance": 9, "ownershipPct": 0, "warChest": -5, "mediaHeat": 6 },
          "consequence": "You put forward two nominees; Meridian says the board is 'already well-composed.'",
          "requires": [],
          "unlocks": ["seats_demanded", "board_pressure"]
        },
        {
          "id": "4b",
          "label": "Demand a formal strategic review",
          "pros": ["Creates a concrete catalyst with a deadline", "Harder for the board to refuse publicly"],
          "cons": ["Reviews can be slow-walked into oblivion", "No guarantee the conclusion favors you"],
          "deltas": { "stockPrice": 2.5, "boardResistance": 6, "ownershipPct": 0, "warChest": -4, "mediaHeat": 5 },
          "consequence": "Meridian announces a strategic review 'with independent advisors' — your fingerprints everywhere.",
          "requires": [],
          "unlocks": ["review_demanded", "board_pressure"]
        },
        {
          "id": "4c",
          "label": "Demand both seats and a review",
          "pros": ["Maximum pressure on every front", "Whichever concession lands, you win"],
          "cons": ["Board unites against overreach", "Expensive two-front campaign"],
          "deltas": { "stockPrice": 3.5, "boardResistance": 16, "ownershipPct": 0, "warChest": -10, "mediaHeat": 10 },
          "consequence": "Meridian's board calls your demands 'a hostile attempt to seize control without paying a premium.'",
          "requires": ["public_campaign"],
          "unlocks": ["seats_demanded", "review_demanded", "board_pressure"]
        }
      ],
      "curveball": false
    },
    {
      "id": "beat-5",
      "n": 5,
      "title": "Capital return vs breakup",
      "zoneId": "cfo_office",
      "npcId": "cfo",
      "situation": "CFO Priya Ramanathan controls the model. She privately concedes the balance sheet is lazy. What is the value-creation ask: return the cash, or break the company apart?",
      "debateTopic": "Buyback and dividend, full breakup, or operational fix?",
      "scriptedLines": [
        { "speakerId": "cfo", "text": "We have 3.2 billion in cash earning nothing. I won't pretend otherwise." },
        { "speakerId": "analyst", "text": "Sum-of-parts says the pieces are worth 70. The conglomerate discount is the whole thesis." }
      ],
      "options": [
        {
          "id": "5a",
          "label": "Push a $2B buyback plus special dividend",
          "pros": ["Immediate, mechanical support for the stock", "CFO privately agrees — easy win"],
          "cons": ["One-time sugar hit, not a re-rating", "Leaves the broken structure intact"],
          "deltas": { "stockPrice": 3.5, "boardResistance": 4, "ownershipPct": 0, "warChest": -4, "mediaHeat": 4 },
          "consequence": "Meridian 'evaluates capital return options'; the stock firms on the headline.",
          "requires": [],
          "unlocks": ["capital_return"]
        },
        {
          "id": "5b",
          "label": "Push a breakup — spin off Orbital",
          "pros": ["Unlocks the full sum-of-parts value", "The review gives it procedural cover"],
          "cons": ["Multi-year execution risk", "CEO will fight to keep his empire whole"],
          "deltas": { "stockPrice": 5, "boardResistance": 9, "ownershipPct": 0, "warChest": -8, "mediaHeat": 10 },
          "consequence": "Breakup speculation sends MRDN to a 52-week high; Hale calls the idea 'value-destructive.'",
          "requires": ["review_demanded"],
          "unlocks": ["breakup_plan"]
        },
        {
          "id": "5c",
          "label": "Push operational cost cuts",
          "pros": ["Least confrontational value lever", "Margin math is undeniable"],
          "cons": ["Slowest path to 60", "Management claims credit for your plan"],
          "deltas": { "stockPrice": 1.5, "boardResistance": 3, "ownershipPct": 0, "warChest": -3, "mediaHeat": 2 },
          "consequence": "Meridian unveils a cost program suspiciously similar to page 61 of your deck.",
          "requires": [],
          "unlocks": ["ops_plan"]
        }
      ],
      "curveball": false
    },
    {
      "id": "beat-6",
      "n": 6,
      "title": "Curveball",
      "zoneId": "war_room",
      "npcId": "analyst",
      "situation": "Your analyst bursts into the war room. Something just hit the tape — and it changes the board math.",
      "debateTopic": "React to the shock without losing the campaign.",
      "scriptedLines": [
        { "speakerId": "analyst", "text": "You need to see this. Right now." },
        { "speakerId": "partner", "text": "Whatever it is — we decide fast and we decide once." }
      ],
      "options": [],
      "curveball": true,
      "variants": [
        {
          "id": "cv-earnings-miss",
          "title": "Earnings shock",
          "situation": "Meridian pre-announces a brutal Q3 miss — Orbital bleeding worse than even your model assumed. The stock gaps down.",
          "eventDeltas": { "stockPrice": -4, "mediaHeat": 10 },
          "options": [
            {
              "id": "6a-buy-dip",
              "label": "Buy the dip aggressively",
              "pros": ["Average down at panic prices", "Bigger stake means bigger vote"],
              "cons": ["Burns serious war chest", "Catching a falling knife if it worsens"],
              "deltas": { "stockPrice": 1, "boardResistance": 1, "ownershipPct": 2.5, "warChest": -20, "mediaHeat": 0 },
              "consequence": "Filings later reveal your fund bought the entire panic — stake now over 11%.",
              "requires": [],
              "unlocks": ["dip_bought"]
            },
            {
              "id": "6a-press-narrative",
              "label": "Press the mismanagement narrative",
              "pros": ["The miss proves your thesis for free", "Momentum with wavering holders"],
              "cons": ["Kicking them while down alienates the board", "You look gleeful about bad news"],
              "deltas": { "stockPrice": 1.5, "boardResistance": 6, "ownershipPct": 0, "warChest": -2, "mediaHeat": 12 },
              "consequence": "'WE TOLD YOU SO' — your statement runs everywhere next to Hale's grim guidance call.",
              "requires": [],
              "unlocks": ["narrative_momentum"]
            }
          ]
        },
        {
          "id": "cv-poison-pill",
          "title": "Poison pill adopted",
          "situation": "Meridian's board adopts a 12% shareholder rights plan overnight — a poison pill aimed squarely at your fund.",
          "eventDeltas": { "boardResistance": 8, "mediaHeat": 5 },
          "options": [
            {
              "id": "6b-sue",
              "label": "Challenge the pill in Delaware",
              "pros": ["Pills this naked rarely survive review", "Discovery unearths board emails"],
              "cons": ["Litigation is slow and expensive", "Judges dislike activists who sue first"],
              "deltas": { "stockPrice": 1, "boardResistance": -4, "ownershipPct": 0, "warChest": -12, "mediaHeat": 6 },
              "consequence": "Your Delaware complaint calls the pill 'an entrenchment device masquerading as governance.'",
              "requires": [],
              "unlocks": ["pill_challenged"]
            },
            {
              "id": "6b-standstill",
              "label": "Negotiate a standstill for pill removal",
              "pros": ["Defuses the crisis cheaply", "Board reads it as good faith"],
              "cons": ["Caps your stake during the fight", "Looks like blinking to the street"],
              "deltas": { "stockPrice": 0.5, "boardResistance": -8, "ownershipPct": 0, "warChest": -3, "mediaHeat": -5 },
              "consequence": "Meridian rescinds the pill; both sides announce 'constructive dialogue.'",
              "requires": [],
              "unlocks": ["standstill"]
            }
          ]
        },
        {
          "id": "cv-white-knight",
          "title": "White-knight rumor",
          "situation": "A wire report: Meridian has quietly courted a friendly acquirer at a modest premium — a white knight to dilute you out of the story.",
          "eventDeltas": { "stockPrice": 4, "mediaHeat": 10 },
          "options": [
            {
              "id": "6c-oppose-sale",
              "label": "Publicly oppose a sweetheart sale",
              "pros": ["Blocks a lowball exit below intrinsic value", "Rallies long-term holders to you"],
              "cons": ["You're now fighting a takeover premium", "Arbs flood in with short horizons"],
              "deltas": { "stockPrice": 1, "boardResistance": 4, "ownershipPct": 0, "warChest": -3, "mediaHeat": 8 },
              "consequence": "Your open letter: 'Meridian is worth 70 broken up — not 52 in a fire sale to friends.'",
              "requires": [],
              "unlocks": ["sale_opposed"]
            },
            {
              "id": "6c-demand-auction",
              "label": "Demand a formal auction process",
              "pros": ["If it sells, it sells at the top", "Puts the board's fiduciary duty on record"],
              "cons": ["Auction may attract a buyer you can't beat", "Campaign becomes an M&A trade"],
              "deltas": { "stockPrice": 2.5, "boardResistance": 6, "ownershipPct": 0, "warChest": -5, "mediaHeat": 6 },
              "consequence": "You demand a full auction with independent bankers; the stock rips on deal math.",
              "requires": [],
              "unlocks": ["auction_demanded"]
            }
          ]
        }
      ]
    },
    {
      "id": "beat-7",
      "n": 7,
      "title": "Settle vs proxy",
      "zoneId": "boardroom",
      "npcId": "chair",
      "situation": "The nomination window opens in ten days. Chair Okafor floats a settlement framework. Take the deal on the table, or take it to a vote.",
      "debateTopic": "Settle now or launch the proxy fight?",
      "scriptedLines": [
        { "speakerId": "chair", "text": "There is a framework the board could live with. It requires both sides to stop performing." },
        { "speakerId": "gc", "text": "If you go to a vote, we will run the full playbook. All of it." },
        { "speakerId": "partner", "text": "Settlements are certain and small. Proxy fights are expensive and total." }
      ],
      "options": [
        {
          "id": "7a",
          "label": "Negotiate a settlement",
          "pros": ["Locks in real gains without vote risk", "Preserves capital for the next campaign"],
          "cons": ["Board keeps effective control", "Street may read it as declaring victory early"],
          "deltas": { "stockPrice": 4.5, "boardResistance": -10, "ownershipPct": 0, "warChest": -5, "mediaHeat": -5 },
          "consequence": "Settlement announced: one board seat, capital-return committee, mutual non-disparagement.",
          "requires": ["board_pressure"],
          "unlocks": ["settled"]
        },
        {
          "id": "7b",
          "label": "Launch the proxy fight",
          "pros": ["Winner takes the whole board agenda", "Your thesis gets a shareholder verdict"],
          "cons": ["Burns enormous cash on solicitation", "Losing the vote ends the campaign dead"],
          "deltas": { "stockPrice": 2, "boardResistance": 10, "ownershipPct": 0, "warChest": -25, "mediaHeat": 15 },
          "consequence": "You nominate a full slate; Meridian files its proxy calling your fund 'a self-dealing raider.'",
          "requires": [],
          "unlocks": ["proxy_launched"]
        }
      ],
      "curveball": false
    },
    {
      "id": "beat-8",
      "n": 8,
      "title": "Swing holders and ISS",
      "zoneId": "war_room",
      "npcId": "partner",
      "situation": "The vote math lives on the war room whiteboard: index funds 28%, ISS-followers 20%, retail 15%. Whoever wins the middle wins Meridian.",
      "debateTopic": "Where do we spend the final persuasion budget?",
      "scriptedLines": [
        { "speakerId": "partner", "text": "ISS moves twenty points of the vote in one report. Nothing else comes close." },
        { "speakerId": "analyst", "text": "The index funds won't meet twice. One pitch, perfect, or nothing." }
      ],
      "options": [
        {
          "id": "8a",
          "label": "Pitch ISS and Glass Lewis",
          "pros": ["One recommendation swings 20% of the vote", "Proxy advisors love a governance story"],
          "cons": ["All-or-nothing meeting", "Their process is a black box"],
          "deltas": { "stockPrice": 3.5, "boardResistance": -8, "ownershipPct": 0, "warChest": -8, "mediaHeat": 5 },
          "consequence": "ISS recommends FOR two of your nominees, citing 'sustained underperformance and board entrenchment.'",
          "requires": ["proxy_launched"],
          "unlocks": ["iss_backed"]
        },
        {
          "id": "8b",
          "label": "Court the index funds directly",
          "pros": ["28% of the register in three meetings", "Stewardship teams already dislike the pill era"],
          "cons": ["Institutionally cautious — they default to management", "No public momentum even if they flip"],
          "deltas": { "stockPrice": 2.5, "boardResistance": -5, "ownershipPct": 0, "warChest": -5, "mediaHeat": 2 },
          "consequence": "Two of the big three stewardship teams take the second meeting. That never happens.",
          "requires": [],
          "unlocks": ["index_support"]
        },
        {
          "id": "8c",
          "label": "Run a retail media blitz",
          "pros": ["15% retail skews anti-incumbent", "Cheap impressions via financial TV"],
          "cons": ["Retail rarely returns proxy cards", "High heat invites regulator attention"],
          "deltas": { "stockPrice": 2, "boardResistance": 2, "ownershipPct": 0, "warChest": -6, "mediaHeat": 15 },
          "consequence": "Your fund's campaign site and TV hits trend; #FixMeridian does numbers.",
          "requires": ["public_campaign"],
          "unlocks": ["retail_wave"]
        }
      ],
      "curveball": false
    },
    {
      "id": "beat-9",
      "n": 9,
      "title": "Endgame vote",
      "zoneId": "boardroom",
      "npcId": "chair",
      "situation": "Annual meeting day. The boardroom is standing-room only. The inspector of elections is ready. This is where the campaign ends — one way or the other.",
      "debateTopic": "Force the vote, ratify the deal, or take the last-minute compromise?",
      "scriptedLines": [
        { "speakerId": "chair", "text": "The meeting will come to order. We have one item of business that matters." },
        { "speakerId": "ceo", "text": "Whatever happens today, I built this company. Remember that." },
        { "speakerId": "analyst", "text": "Final tally projections are on your phone. It's going to be close." }
      ],
      "options": [
        {
          "id": "9a",
          "label": "Force the vote on your slate",
          "pros": ["Total victory rewrites the whole board", "Your mandate becomes undeniable"],
          "cons": ["Vote-day surprises are legendary", "No fallback if the tally breaks wrong"],
          "deltas": { "stockPrice": 6, "boardResistance": -12, "ownershipPct": 0, "warChest": -6, "mediaHeat": 5 },
          "consequence": "Preliminary tally: your nominees carry the vote. Hale concedes at the podium.",
          "requires": ["proxy_launched"],
          "unlocks": ["vote_won"]
        },
        {
          "id": "9b",
          "label": "Ratify the settlement on stage",
          "pros": ["Certain, clean, and value-accretive", "Board partnership for the breakup ahead"],
          "cons": ["Less upside than total board control", "Critics call it a half-win"],
          "deltas": { "stockPrice": 5.5, "boardResistance": -8, "ownershipPct": 0, "warChest": -2, "mediaHeat": -10 },
          "consequence": "The settlement is ratified to applause; joint statement promises 'a new chapter at Meridian.'",
          "requires": ["settled"],
          "unlocks": ["deal_ratified"]
        },
        {
          "id": "9c",
          "label": "Take the eleventh-hour compromise",
          "pros": ["Salvages something from a weak hand", "Keeps the relationship for round two"],
          "cons": ["Smallest value unlock of the three", "Street writes the campaign off as a draw"],
          "deltas": { "stockPrice": 1.5, "boardResistance": -5, "ownershipPct": 0, "warChest": -3, "mediaHeat": 0 },
          "consequence": "A midnight compromise: one observer seat and a capital-return study. The tape shrugs.",
          "requires": [],
          "unlocks": ["compromise_taken"]
        }
      ],
      "curveball": false
    }
  ]
}
```

Content invariants: 9 beats; 26 options total; curveball beat has `options: []` and 3 `variants`; every beat/variant keeps at least one option with empty `requires` so no path soft-locks; every flag in a `requires` is unlockable by an earlier beat.

---

## 8. Scoring engine (pure Python, `backend/app/engine/`)

**Protocol (frozen — teammate code depends on it):**

```python
class ScoringEngine(Protocol):
    def create(self, scenario: Scenario) -> GameState: ...
    def available_options(self, state: GameState) -> list[Option]: ...
    def apply(self, state: GameState, option_id: str) -> GameState: ...
    def summary(self, state: GameState) -> Summary: ...
```

Concrete class: `MeridianScoringEngine`. Plain dicts or pydantic models both work for `GameState`; the state must carry at least: `kpis`, `beatIndex` (0-based, count of beats applied), `flags` (set/list of unlocked flag strings), `history` (per-beat record of option chosen + deltas applied), `outcome` (`"playing" | "won" | "lost"`), `seed`, `curveballVariantId`, `lobbyClaimedBeats`.

**Rules (all implemented behaviors, verbatim from the shipped engine):**

1. `create(scenario, seed=0)` — initial KPIs from the scenario; picks the curveball variant with `random.Random(seed).choice(variants)` and stores its id as `curveballVariantId`. Same seed → same variant, always.
2. `available_options(state)` — options of the current beat whose `requires` flags are ALL present in `state.flags` (AND semantics). Gated options are omitted entirely (client never sees them). On the curveball beat, options come from the selected variant.
3. `apply(state, option_id)` — **pure**: deep-copies, never mutates the input. Raises/rejects on unknown ids and on gated options. On the curveball beat, the variant's `eventDeltas` apply **before** the option's deltas; both are recorded in history. Adds the option's `unlocks` to flags. Advances `beatIndex`.
4. Clamping after every delta application: `boardResistance`, `ownershipPct`, `mediaHeat` ∈ [0, 100]; `stockPrice` ≥ 0; `warChest` unclamped (may go negative — that fires the lose condition).
5. Outcome: lose conditions checked after **every** beat; win condition (`stockPrice ≥ 60`) only after beat 9; **lose takes precedence** if both would trigger.
6. `summary(state)` — scorecard: outcome, letter grade, final KPIs, history. Grading: win margin over the stock target ≥10 → **A**, ≥5 → **B**, else **C**; finished all 9 beats but missed target → **D**; blew a lose condition → **F**.
7. `apply_lobby_bonus(state)` (extra method beyond the protocol) — grants authored `LOBBY_BONUS_DELTAS = {"warChest": +5}` at most once per `beatIndex`, tracked in `lobbyClaimedBeats`. Returns a new state, or `None` if already claimed this beat or game over. Deliberately touches no `stockPrice` so it cannot disturb win-rate balance.

No FastAPI, Phaser, or LLM imports anywhere in the engine.

---

## 9. Debate providers (`backend/app/providers/`)

**Protocol (frozen):**

```python
class DebateProvider(Protocol):
    async def stream(self, ctx: DebateContext) -> AsyncIterator[DebateDelta]: ...
```

`DebateContext` is a dict with the beat's `situation`, `debateTopic`, `scriptedLines`, `npcs` (the six ids), and `options` (full option dicts *including* deltas — providers must never surface deltas in output text). `DebateDelta` = `{"speakerId": "<npc id>", "text": "<line or chunk>", "done": bool?}` — `speakerId` must be one of the six NPC ids or the speech bubble cannot be placed.

**`DeterministicDebate`** (default): streams the beat's authored `scriptedLines` first, then for each available option one ally line arguing a pro (speaker `analyst` or `partner`) and one skeptic line arguing a con (speaker from `gc`/`chair`/`cfo`/`ceo`). Qualitative text only. Sleeps `DEBATE_DELAY_MS` (default 600 ms; `0` in tests) between lines.

**`GatewayDebate`**: streams `POST {OPENAI_BASE_URL}/chat/completions` with `stream: true`, model `GATEWAY_MODEL`, bearer `OPENAI_API_KEY`, via httpx. Prompt = situation + NPC personas + option labels/pros/cons **only** (never deltas, never KPI names as targets). Instructs the model to emit `speaker_id: text` lines; parser reassembles token chunks into per-line `DebateDelta`s, maps unknown speakers to the beat's `npcId` (fallback `analyst`), marks the final delta `done: true`. **Fallback:** missing config, connect error, timeout (`GATEWAY_TIMEOUT_S`, connect capped 5 s), HTTP error, empty or mid-stream-broken response → log a warning and continue the debate with `DeterministicDebate` from that point. The game must never stall.

**`SwarmDebate`**: a documented stub for a teammate line-graph multi-agent system. Module docstring states: implement `stream` to this exact signature; map agent utterances → `DebateDelta`s; do not emit internal events (routing/tool calls); never compute KPI deltas. The stub itself emits a plausible fake 7-line multi-agent debate (paced by `DEBATE_DELAY_MS`) so `DEBATE_PROVIDER=swarm` is playable.

**`factory.py`**: `create_debate_provider(name=None)` reads `DEBATE_PROVIDER`, case-insensitive; unknown values log a warning and return deterministic. Resolved **per session at `POST /sessions` time** so env changes apply to new sessions without a restart.

---

## 10. REST + SSE API (`backend/app/api/sessions.py`)

In-memory session store (dict keyed by uuid). Each session owns an `asyncio.Queue` of SSE events; **events emitted before the client connects are buffered** so nothing is lost on late subscribe. Keepalive comments every 15 s.

`nextBeat` hint shape used throughout: `{ beatId, n, title, zoneId, npcId }`, `null` after game end.

### `POST /sessions`
Request `{ "scenarioId": "meridian-activist-01", "seed": 42 }` (both optional; seed defaults to a random int). Response:

```json
{
  "sessionId": "uuid", "phase": "EXPLORE", "beatIndex": 0,
  "kpis": { "stockPrice": 42.0, "boardResistance": 55, "ownershipPct": 6.5, "warChest": 120, "mediaHeat": 20 },
  "flags": [], "seed": 42,
  "nextBeat": { "beatId": "beat-1", "n": 1, "title": "Stake build", "zoneId": "trading_floor", "npcId": "analyst" }
}
```

### `GET /sessions/{id}`
Snapshot for polling/headless play: `{ sessionId, phase, beatIndex, kpis, flags, outcome, nextBeat }` plus `options` (public shape, **no deltas**) when phase is `AWAIT_DECISION`.

### `POST /sessions/{id}/interact`
Request `{ "targetId": "npc:ceo", "beatId": "beat-2" }` (`beatId` optional). Accepts when `targetId` matches the current beat's `zone:{zoneId}` **or** `npc:{npcId}` (and `beatId` matches if sent) and phase is `EXPLORE`. On accept → `{ "phase": "BEAT_INTRO", "beatId": "…", "accepted": true }` and a background task runs BEAT_INTRO → DEBATE → AWAIT_DECISION, streaming over SSE. On wrong target/phase → `{ "accepted": false, "phase": "…", "nextBeat": {…} }`.

**Lobby special case:** `{ "targetId": "zone:lobby" }` during EXPLORE (when lobby isn't the current beat's zone) calls `apply_lobby_bonus` instead: response adds `"lobbyBonus": "granted" | "spent"` with `accepted: false`; a grant emits `kpi_patch` + a `news` line over SSE. Claims reset each time a beat is applied.

### `POST /sessions/{id}/decide`
Request `{ "optionId": "2a" }`. **409** outside `AWAIT_DECISION`; **400** for unknown/gated options. Applies via the engine, emits `kpi_patch` + `news` (consequence) + `phase` + `next_beat` (or `game_end`), responds `{ "phase": "EXPLORE", "kpis": {…}, "consequence": "…", "outcome": "playing" }`.

### `GET /sessions/{id}/events` — SSE
Named events, JSON payloads:

| event | payload |
|-------|---------|
| `phase` | `{ phase }` |
| `beat` | `{ beatId, n, title, situation, zoneId, npcId }` — at BEAT_INTRO; curveball variant's title/situation merged in |
| `debate_delta` | `{ speakerId, text }` |
| `debate_complete` | `{}` |
| `options` | `{ options: [{ id, label, pros, cons }] }` — **no deltas** |
| `kpi_patch` | `{ kpis }` (full KPI object) |
| `news` | `{ text }` — consequences, curveball headline, lobby bonus, hints |
| `next_beat` | nextBeat hint — on session start and each return to EXPLORE |
| `game_end` | `{ outcome, grade, summary }` |

Wire format example: `event: debate_delta\ndata: {"speakerId":"ceo","text":"We reject your premise."}\n\n`

### `GET /health`
`{ "status": "ok", "debate_provider": "<resolved provider>" }`

---

## 11. Phaser ↔ React event bus (frontend)

A tiny shared EventTarget/mitt-style bus bridges the Phaser scene, the React UI, and the SSE client (`src/net/session.ts` boots the session on mount — make it React StrictMode-safe — and forwards bus↔REST/SSE):

| Event | Direction | Payload |
|-------|-----------|---------|
| `game:interact` | Phaser → net layer | `{ targetId, beatId? }` |
| `game:prompt` | Phaser → React | `{ targetId, label }` \| `null` — show/hide interact pill |
| `game:phase` | net → Phaser+React | `{ phase }` — Phaser soft-locks input when ≠ `EXPLORE` |
| `game:speech` | SSE → Phaser | `{ speakerId, text }` — speech bubble over that NPC |
| `game:kpi` | SSE → React | `{ kpis }` |
| `game:options` | SSE → React | `{ options }` |
| `game:news` | SSE → React | `{ text }` — feeds ToastLog **and** NewsTicker |
| `game:beat` | SSE → React | `{ beatId, n, title, situation }` — beat intro panel |
| `game:nextBeat` | SSE → React | nextBeat hint — "Next: Trading Floor" |
| `game:session` | net → React | `{ sessionId, seed }` — once after POST /sessions |
| `game:end` | SSE → React | `{ outcome, grade, summary }` |
| `ui:decide` | React → net | `{ optionId }` |
| `ui:inputLock` | React → Phaser | `{ locked }` |

---

## 12. Look and feel — pixel office (reproduce faithfully)

**Rendering:** 16 px tiles, Phaser config `pixelArt: true`, canvas 800×480, camera zoom **2**, camera follows player within world bounds. All art generated at runtime on canvases — a 10-tile tileset, 7 character spritesheets (8 frames each: down0 down1 left0 left1 right0 right1 up0 up1, 16×16), and ~12 furniture pieces drawn with fillRect primitives (desks with monitors, boardroom table, wall screen, reception counter, podium, sofas, shelves, cabinets, water cooler, plants, chairs).

**World:** 60×40 tiles (960×640 px). Default fill = hallway floor; rooms are wall-perimeter rectangles with door gaps punched after all perimeters are drawn (so shared walls stay open); a solid wall border rings the whole map. Wall tile: dark navy `#3d4763` with top highlight `#55658a` and a darker lower band `#262d40`. Floors: base color + subtle grid lines + 3 fleck pixels per tile.

**Room rectangles** (tile coords, inclusive `x0,y0 → x1,y1`), floor base colors, and doors:

| Room | Rect | Floor base | Doors (tile x,y) |
|------|------|-----------|------------------|
| War Room | 0,0 → 17,11 | `#5d6b7e` slate | (8,11) (9,11) |
| Boardroom | 17,0 → 42,11 | `#9c5a5a` oxblood | (29,11) (30,11) |
| CEO Office | 42,0 → 59,11 | `#a0724d` wood | (50,11) (51,11) |
| Trading Floor | 0,14 → 24,27 | `#7f96b2` blue | (11,14) (12,14) (24,20) (24,21) |
| CFO Office | 41,14 → 59,21 | `#7ba190` sage | (41,17) (41,18) |
| GC Office | 41,21 → 59,28 | `#a08298` mauve | (41,24) (41,25) |
| Press Bay | 0,28 → 24,39 | `#8a86ac` violet | (24,32) (24,33) |
| Lobby | 24,28 → 41,39 | `#c2a878` tan | (30,28) (31,28) (32,28) (33,28) (41,33) (41,34) |

Hallway floor: `#9aa1af` gray. Each room gets a small text label rendered on the floor.

**Zone pads** (2×2 tile highlighted floor mats at tile x,y): lobby (31,33), trading_floor (7,19), war_room (3,6), ceo_office (46,6), cfo_office (45,17), gc_office (45,25), boardroom (28,7), press_bay (17,31).

**Player:** spawns at tile (32,36) (lobby). Palette: skin `#e8b98a`, hair `#2e2a26`, shirt `#2f6db5` (blue), pants `#26314a`. Arcade physics body, normalized diagonal speed, 2-frame walk animation per direction.

**NPCs** (spawn tile, wander rect, palette skin/hair/shirt/pants) — each has a floating name tag and wanders its rect with straight-line moves + stuck detection; NPCs freeze during debates:

| id | Name tag | Spawn | Wander rect | Palette |
|----|----------|-------|-------------|---------|
| ceo | CEO | (50,6) | 44,3→57,9 | `#f0c8a0` / `#9aa0a8` gray hair / `#3a3f4a` charcoal suit / `#2b2f38` |
| cfo | CFO | (50,18) | 43,16→57,19 | `#c98a5e` / `#4a3324` / `#274768` navy / `#1e2c40` |
| gc | General Counsel | (51,26) | 43,23→57,26 | `#e8b98a` / `#1f1b18` / `#6b2f3a` maroon / `#33222a` |
| chair | Independent Chair | (30,8) | 19,7→40,10 | `#f0c8a0` / `#e8e4dc` white hair / `#4a5d3a` olive / `#3a3328` |
| analyst | Your Analyst | (13,20) | 2,16→21,25 | `#b97a50` / `#2a241f` / `#2f8f7a` teal / `#3d4450` |
| partner | Activist Partner | (7,8) | 2,3→14,9 | `#e8b98a` / `#5a3a28` / `#5d3a78` purple / `#2e2440` |

**Furniture placement** (texture @ tile, solid ⇒ collider): boardroom — board_table@(25,3) solid, 7 chairs around it, 2 plants; CEO — desk@(48,4)+chair, shelf@(54,1), sofa@(44,8), plant; CFO — desk@(48,16)+chair, cabinet@(56,15), plant; GC — desk@(48,24)+chair, shelf@(43,22), plant; trading floor — 6 desks in a 3×2 grid @(4/10/16, 17/21), cooler@(22,15), plant; war room — screen@(5,1), table@(6,5)+4 chairs, plant; press bay — podium@(12,30), 8 audience chairs in 2 rows @(5–14, 33/36), 2 plants; lobby — reception@(34,30), sofa@(26,35), 2 plants; bottom-right lounge — sofa@(46,31), cooler@(43,29), plant. Desks/tables/shelves/counters/podium/sofas/coolers are solid; chairs and plants are walk-through.

**Interaction:** interact radius ≈42 px around NPCs; standing on a zone pad or in radius shows the prompt and enables `E`/click.

**UI theme (React overlay):** dark fintech. Page background `#0d1219`, text `#e8eef7`, panel borders `#2a3548`, muted text `#8aa0b8`, header gradient `#152032 → #0d1219`, kbd-style keys on `#1d2942` with `#4a5a74` borders. Font: IBM Plex Sans / Segoe UI fallback. Layout: CSS grid — full-width header row; main row = stage (canvas, max 800 px wide, aspect 800/480) + right side panel (240–300 px); full-width ticker footer. Interact prompt: pill, `rgba(13,18,25,0.88)` background, centered at canvas bottom. Toasts top-left over the canvas. KPI cards flash green/red with a delta badge on change. Option cards: label + pros (green accents) + cons (red accents), click to decide. Scorecard: modal/panel with grade, final KPIs, history list, seed, "Run it back (same seed)" + "New campaign" buttons. NewsTicker: fixed bottom bar labeled **MRDN WIRE**, seeds with ~4 ambient headlines, rotates every 6 s, jumps immediately on fresh `game:news`.

---

## 13. Frontend behavior details

- Boot: read `?seed=` from URL → `POST /sessions` (with seed if present) → emit `game:session` → open SSE → emit `game:nextBeat` hint.
- Debate: each `debate_delta` shows a speech bubble above the matching NPC (camera pans to speaker) and appends to the side-panel transcript.
- Soft-lock: Phaser stops player movement (and hides prompt) whenever phase ≠ EXPLORE or `ui:inputLock` is true.
- Seed display: side panel (subtle) and scorecard. "Run it back" reloads with `?seed=<seed>`; "New campaign" clears the query.
- Deltas never render pre-decision anywhere: cards and debates are qualitative; KPI numbers only change after `kpi_patch`.

---

## 14. Polish features (all shipped, all required)

1. **News ticker** — as described in §12; fed by SSE `news`.
2. **Lobby once-per-beat bonus** — engine + API behavior per §8.7/§10; UX: first `E` on the lobby pad grants "+$5M war chest" with KPI flash + news line; a second visit that beat shows "The lobby is quiet — one favor per move."
3. **Seed replay** — `?seed=123` in the URL reproduces the identical run (same curveball variant); effective seed echoed by the API and shown in UI.
4. **Qualitative-only audit** — verify no numeric deltas appear in cards/debate/snapshots.

---

## 15. Testing requirements

Backend (pytest; the original suite has 81 tests — match the coverage, not the count):

- **Engine:** delta application + clamping; input-state immutability; flag gates (hidden from `available_options`, rejected by `apply`); win via both archetype paths across seeds; loss by boardResistance and by warChest; seeded curveball reproducibility (same seed → identical full run; ~30 seeds cover all 3 variants); summary grading A–F; headless seeded full 9-beat random runs with exact replay verification.
- **Scenario validation:** 9 beats in order; zone/NPC ids match §6; option shape/counts; unique ids; curveball structure; every `requires` flag unlockable earlier.
- **API (FastAPI TestClient):** create/interact/decide happy path; wrong-target and wrong-phase rejections; 409/400 on decide; full 9-beat run to `GAME_END`; SSE event ordering; lobby bonus grant/spent cycle + reset on beat apply.
- **Providers:** factory selection (default/env/unknown/case-insensitive); gateway happy path via `httpx.MockTransport` (line parsing across chunk boundaries, auth+model in request); prompt safety (pros/cons present, no deltas or KPI names); every fallback trigger; swarm stub stream shape. No real network anywhere; set `DEBATE_DELAY_MS=0`.

Frontend: `npm run build` green. Browser E2E (Playwright or manual): walk to trading floor → E → debate streams → cards → decide → KPI animation → EXPLORE with next hint; lobby bonus once-per-beat; `?seed=` reproduces the curveball variant; full offline run reaches the scorecard.

**Balance verification** — `backend/scripts/simulate.py`: a uniform-random policy over N seeds plus scripted archetype paths (aggressive proxy-fight line and settlement-diplomacy line) across all 3 curveball variants. Targets with the §7 numbers: random-walk win rate **≈54% at 500 seeds / ≈57% at 2000 seeds** (band 40–60%); proxy path finishes ≈$63.50–71.50, settlement ≈$61.50–69.50, both winning on all variants; max-aggression busts boardResistance by ~beat 5; a timid run finishes but misses $60. If your numbers drift outside the band, re-check the deltas against §7 before touching balance.

---

## 16. Hard-won gotchas (fix these preemptively)

1. **React StrictMode double-mount vs Phaser:** effects run twice in dev. Guard session creation, and detach scene event-bus listeners on **both** `SHUTDOWN` and `DESTROY` — a `game.destroy()` remount skips `SHUTDOWN`, leaving stale listeners that crash on the next SSE event.
2. **SSE before subscribe:** the interact background task starts emitting immediately; buffer per-session events in a queue so a late-connecting EventSource misses nothing.
3. **Decide race:** `decide` must be rejected (409) until the debate task has reached `AWAIT_DECISION`.
4. **`DEBATE_DELAY_MS=0` in all tests**, or the suite crawls.
5. **Door punching order:** punch all doors after drawing all room perimeters, or shared-wall doors get re-walled by the neighboring room.
6. **Speaker ids:** any debate text with a speakerId outside the six NPC ids has no bubble anchor — map unknowns to the beat's npcId.
7. **Lose precedence:** check lose conditions after every beat and before the win check; warChest may legitimately go negative and must end the game.
8. **Vite proxy:** proxy `/sessions` (including the SSE route) and `/health` to :8000; SSE needs no buffering middleware in dev.

---

## 17. Definition of Done

- Fresh clone → two commands (backend, frontend) → complete 9-beat game in <20 min, WASD + interacts, offline, `DEBATE_PROVIDER=deterministic`, no API key.
- All backend tests green; KPI math provably independent of any LLM.
- Balance inside the 40–60% band per §15.
- Gateway provider works when configured and falls back cleanly when not.
- Swarm stub playable and documented for teammate replacement.
- A `SPEC.md` (regenerated from this document's contracts) accurate to the built system.

**Out of scope:** multiplayer, Claude Code hooks, Pixel Agents VS Code extension, cloud deploy, other scenarios (the engine supports them via new JSON only — no code changes).
