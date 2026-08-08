# Activist Pixel Sim

Local-first activist-investor pixel RPG: Vite + React + Phaser 3 client, FastAPI backend. Contracts and phase checklist live in [`SPEC.md`](SPEC.md).

**POC status:** Phases **0–6 complete** (scaffold → scoring → office → REST/SSE → gateway/swarm providers → polish). Phase 7 (multiplayer) is out of scope until local sign-off.

## Quick start

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Health: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

Tests: `python -m pytest tests/ -q`

Headless balance / replay: `python scripts/simulate.py`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). Vite proxies `/health` and `/sessions` to the backend.

### Env

Copy `.env.example` to `.env` (gitignored). Default `DEBATE_PROVIDER=deterministic` needs **no API key**. Gateway vars are only for `DEBATE_PROVIDER=gateway`.

Never commit `.env`, `venv/`, or API keys.

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
