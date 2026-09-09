# claude-plans

Plans and implementations for Claude/Cursor agent projects.

## Active project

**[Activist Pixel Sim](pixel-simulator-game/)** — local-first activist-investor pixel RPG (Vite + React + Phaser 3, FastAPI).

Default campaign is **NovaTech Proxy War**: 8 quarters, a 16-card deck, 13 metrics, a 6-seat war room, a deterministic rival, weighted composite scoring. Meridian’s 9-beat authored campaign remains a regression baseline (`?scenario=meridian-activist-01`).

**Run:** two terminals from `pixel-simulator-game/` — backend `cd backend && uvicorn app.main:app --reload --port 8000`, frontend `cd frontend && npm run dev` — then open [http://localhost:5173](http://localhost:5173).

| Doc | Purpose |
|-----|---------|
| [`pixel-simulator-game/README.md`](pixel-simulator-game/README.md) | How to run and play |
| [`pixel-simulator-game/docs/ARCHITECTURE.md`](pixel-simulator-game/docs/ARCHITECTURE.md) | Shipped system architecture |
| [`docs/superpowers/specs/2026-08-13-proxy-war-realignment-design.md`](docs/superpowers/specs/2026-08-13-proxy-war-realignment-design.md) | NovaTech / v2 design spec |
| [`pixel-simulator-game/SPEC.md`](pixel-simulator-game/SPEC.md) | Meridian v1 agent bible (still the v1 contract) |
