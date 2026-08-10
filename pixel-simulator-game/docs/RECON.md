# Phase 0 Recon

**Date:** 2026-08-11  
**Updated:** 2026-08-13 (repo layout + POC status)  
**Verdict:** Greenfield — no teammate FastAPI / Phaser / agent-office scaffold in this repo.

## Findings

| Question | Answer |
|----------|--------|
| Existing app? | No. Repo originally had planning docs and a Cursor plan only. |
| agent-office fork? | Not present. Do **not** fork for this POC — plan locks Phaser 3 + FastAPI greenfield. |
| Handoff vs plan | `PIXEL-BOARDROOM-HANDOFF.md` is an older Node/Anthropic/agent-office brief. **Active contracts** are `SPEC.md` (FastAPI, Copilot gateway env, KPIs including `boardResistance` / `mediaHeat`). |
| Scenario | `backend/scenarios/meridian-activist-01.json` — full 9-beat campaign (Phases 2–6). |

## Integration stance

Keep `ScoringEngine` / `DebateProvider` in `backend/app/engine/protocols.py` and `backend/app/providers/protocols.py` stable. Adapt teammate line-graph or FastAPI code at the provider/API boundary only.

## POC progress (post-recon)

| Phase | Status |
|-------|--------|
| 0 Recon | Done |
| 1 Scaffold + SPEC | Done |
| 2 ScoringEngine + scenario + pytest | Done |
| 3 Phaser office | Done |
| 4 REST/SSE + deterministic debate | Done |
| 5 GatewayDebate + SwarmDebate stub | Done |
| 6 Polish (ticker, lobby, seed, balance) | Done |
| 7 Multiplayer | Not started (post–POC sign-off) |
