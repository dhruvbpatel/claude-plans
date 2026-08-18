# Activist Pixel Sim

Local-first activist-investor pixel RPG: Vite + React + Phaser 3 client, FastAPI backend.

**Default campaign:** NovaTech Proxy War — 8 quarters, 16-card deck, 13 metrics, 6-seat war room, deterministic rival, weighted composite score (≥110 wins).

**Meridian baseline:** `http://localhost:5173/?scenario=meridian-activist-01` (9 authored beats).

Architecture: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). NovaTech design: [`../docs/superpowers/specs/2026-08-13-proxy-war-realignment-design.md`](../docs/superpowers/specs/2026-08-13-proxy-war-realignment-design.md). Meridian contracts: [`SPEC.md`](SPEC.md).

## How to run

You need **Python 3**, **Node.js** (npm), and **two terminals**. Backend on `:8000`, frontend on `:5173`. Vite proxies `/health` and `/sessions` to the API, so the browser only talks to `:5173`.

From `pixel-simulator-game/`:

**macOS / Linux**

```bash
./run-backend.sh     # terminal 1 — venv, pip install, uvicorn :8000
./run-frontend.sh    # terminal 2 — npm install, Vite :5173
```

**Windows** (Command Prompt, or double-click the `.bat` files)

```bat
run-backend.bat
run-frontend.bat
```

Each script is idempotent: it creates `backend/.venv` if missing (or reuses `backend/venv/`), installs dependencies, copies `.env.example` to `.env` when needed, then starts the service.

Open **[http://localhost:5173](http://localhost:5173)**. Leave both processes running.

Health check: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health) → `{"status":"ok","debate_provider":"deterministic"}`.

Replay a seeded run: `http://localhost:5173/?seed=42`.

## How to play (NovaTech)

On load you get a briefing, then an in-engine camera tour of rooms and board members. **Continue** starts the tour; **Skip** jumps into play. Replay the tour later with **Help (`?`)** in the HUD (only while exploring, not mid-debate).

- **Move:** WASD or arrow keys. **Interact:** `E` or click a yellow zone pad / NPC.
- Walk to the **Boardroom** or **War Room** pad (or a debate NPC) and press **E**.
- Debate lines play in the **dock under the map** (speaker, line, `4 / 12` counter). ◀ / ▶ or Left / Right / Space browse at your pace; the in-world bubble mirrors the dock. Options appear only after the last line **and** **Enter**.
- Pick a card (pros/cons only). You may follow or defy the chair. That card is what scores.
- After the quarter resolves, walk back to the pad for the next quarter (8 total).
- **Transcript (`T`)** or the sidebar “Recent” strip opens a full-history drawer (Esc closes). Unread lines stay gated.
- The canvas fills the stage; larger windows show more map at the same integer pixel scale.
- Soft-lock input checkbox in the side panel is a **dev** tool — leave it unchecked.

Meridian (`?scenario=meridian-activist-01`): office beats debate-then-cards; boardroom beats 4 / 7 / 9 are motion-then-vote (board’s choice scores). Some boardroom beats have no debate — vote in the dock, then **Enter**.

## Tests

```bash
cd backend
python -m pytest tests/ -q          # or: .venv/bin/python -m pytest tests/ -q
python scripts/simulate.py          # headless balance / replay
cd ../frontend && npm run build
```

## Env

Copy `.env.example` to `.env` (gitignored). Defaults need **no API key**.

| Variable | Default | Purpose |
|----------|---------|---------|
| `DEBATE_PROVIDER` | `deterministic` | `deterministic` \| `gateway` \| `swarm` |
| `WAR_ROOM_PROVIDER` | `deterministic` | `deterministic` \| `swarm` (stub) |
| `CARD_DEALER` | `deterministic` | seeded hands |
| `RIVAL_POLICY` | `deterministic` | pressure-gauge rival |
| `SCORING_MODEL` | `deterministic` | weighted composite |
| `EVENT_DECK` | `deterministic` | quarterly news |
| `BOARD_VOTE_RESOLVER` | `authored` | Meridian boardroom ballots |
| `VITE_SCENARIO_ID` | `novatech-proxy-war-01` | frontend default; URL `?scenario=` wins |

Never commit `.env`, `venv/`, `.venv/`, or API keys.

## Layout

```
run-backend.sh / .bat     # venv + uvicorn :8000
run-frontend.sh / .bat    # npm + Vite :5173
frontend/                 # Vite + React + Phaser 3
backend/
  app/main.py             # FastAPI + CORS + /health
  app/api/sessions.py     # REST + SSE; v1 beats / v2 quarters
  app/engine/             # scoring, dealer, rival, war room, composite
  app/providers/          # debate: deterministic | gateway | swarm stub
  scenarios/
    novatech-proxy-war-01.json
    meridian-activist-01.json
  scripts/simulate.py
  tests/
docs/ARCHITECTURE.md
docs/RECON.md
SPEC.md                   # Meridian v1 bible
```

## What works

| Area | Notes |
|------|--------|
| NovaTech 8-quarter loop | Deal → snap convene → debate → player card → knock-ons / settle / rival |
| Meridian 9-beat loop | Still playable via `?scenario=` |
| Scoring | Authored / config deltas only; LLM never sets KPIs |
| War room | 6 seats + chair; forced dissent; player may defy |
| Rival | Pressure gauge; attacks / interrupts from scenario JSON |
| Providers | Deterministic defaults; swarm / gateway are plug points |
| Office | Phaser tilemap, WASD, 7 NovaTech NPCs; canvas fills the stage |
| Onboarding | Intro briefing + skippable camera tour; Help (`?`) replays |
| Debate dock | Player-paced lines under the map; options gated until last line + Enter |
| Transcript | Full-history drawer (`T`); sidebar shows recent lines only |

## Docs

| Doc | Purpose |
|-----|---------|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Shipped v2 architecture |
| [`SPEC.md`](SPEC.md) | Meridian v1 agent bible |
| [`docs/RECON.md`](docs/RECON.md) | Phase 0 greenfield recon |
| [`PIXEL-BOARDROOM-HANDOFF.md`](PIXEL-BOARDROOM-HANDOFF.md) | Older Node/Anthropic brief (superseded) |
| [`REBUILD-HANDOFF.md`](REBUILD-HANDOFF.md) | Rebuild-from-scratch handoff |
