# Activist Pixel Sim

Local-first activist-investor pixel RPG: Vite + React + Phaser 3 client, FastAPI backend. Contracts and phase checklist live in [`SPEC.md`](SPEC.md).

**POC status:** Phases **0–6 complete**, plus a boardroom meeting cutscene on beats 4 / 7 / 9. Phase 7 (multiplayer) is out of scope until local sign-off.

## How to run

You need **two terminals**. Backend on `:8000`, frontend on `:5173`. Vite proxies `/health` and `/sessions` to the API, so the browser only talks to `:5173`.

### 1. Backend

From `pixel-simulator-game/`:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example ../.env         # optional; defaults need no API key
uvicorn app.main:app --reload --port 8000
```

If you already created a venv named `venv/` instead of `.venv/`, activate that and skip `python3 -m venv`.

Health check: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health) → `{"status":"ok","debate_provider":"deterministic"}`.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open **[http://localhost:5173](http://localhost:5173)**. Leave both processes running.

Replay a seeded curveball with `http://localhost:5173/?seed=42`.

### 3. How to play

- **Move:** WASD or arrow keys. **Interact:** `E` or click an NPC / yellow zone pad.
- Follow the side-panel hint (next beat + room).
- **Office beats** (1–3, 5, 6, 8): walk to the room, interact, watch the debate, pick a card. Your pick applies immediately.
- **Boardroom beats** (4, 7, 9): walk to the **Boardroom** pad or the Chair. Pick your motion first. Agents walk to the table; **any key or click** shows the next line. After the last line, the board vote overlay appears (labels only — no KPI numbers). The **board’s** choice is what scores; then agents walk back to their desks.
- Lobby pad: once-per-beat war-chest bonus, not a beat.

### Tests

```bash
cd backend
python -m pytest tests/ -q          # or: .venv/bin/python -m pytest tests/ -q
python scripts/simulate.py          # headless balance / replay
cd ../frontend && npm run build
```

### Env

Copy `.env.example` to `.env` (gitignored). Default `DEBATE_PROVIDER=deterministic` and `BOARD_VOTE_RESOLVER=authored` need **no API key**. Gateway vars are only for `DEBATE_PROVIDER=gateway`.

Never commit `.env`, `venv/`, `.venv/`, or API keys.

## Layout

```
frontend/                 # Vite + React + Phaser 3
backend/
  app/main.py             # FastAPI + CORS + /health
  app/api/                # sessions, decide, debate SSE
  app/engine/             # ScoringEngine (deterministic KPIs)
  app/providers/          # deterministic | gateway | swarm
  scenarios/              # meridian-activist-01.json
  scripts/simulate.py     # headless 9-beat / balance runs
  tests/
docs/RECON.md
SPEC.md
```

## What works

| Area | Notes |
|------|--------|
| Full 9-beat campaign | Explore → interact → debate SSE → decide → KPI patch |
| Boardroom (beats 4, 7, 9) | Cards first → sit → key-advance lines → board vote applies |
| Scoring | Authored deltas only; LLM never sets KPIs |
| Providers | `deterministic` (default), `gateway` (fallback on error), `swarm` stub |
| Phase 6 polish | News ticker, lobby once-per-beat bonus, seed replay, ~40–60% win band |
| Office | Phaser tilemap, WASD, NPC/zone pads, speech bubbles |

## Docs

| Doc | Purpose |
|-----|---------|
| [`SPEC.md`](SPEC.md) | Agent bible: contracts, API, phases, DoD |
| [`docs/RECON.md`](docs/RECON.md) | Phase 0 greenfield recon |
| [`PIXEL-BOARDROOM-HANDOFF.md`](PIXEL-BOARDROOM-HANDOFF.md) | Older Node/Anthropic brief (superseded by SPEC) |
| [`REBUILD-HANDOFF.md`](REBUILD-HANDOFF.md) | Rebuild-from-scratch handoff for another agent |
