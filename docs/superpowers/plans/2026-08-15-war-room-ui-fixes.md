# War Room UI Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Widen the NovaTech War Room, zoom the meeting camera out to frame the whole table, show one speech bubble at a time during meetings, and pin the HUD so the transcript scrolls in-panel instead of scrolling the page.

**Architecture:** Frontend-only surgical edits. Room rects, wander boxes, furniture, and seats move in `officeMap.ts`; the table texture lengthens in `textures.ts`. `OfficeScene` zooms to 1.4 for meetings and restores 2 on walk-out, destroying all live bubbles and skipping the per-speaker pan during meetings. `App.css` pins a definite `100vh` grid with the transcript as the overflow container; `SidePanel` uses chat-style stickiness (`scrollTop = scrollHeight` only when already within 40px of the bottom) instead of `scrollIntoView`.

**Tech Stack:** Phaser 3 + React + TypeScript (frontend). No backend changes. No new files or dependencies. Verification is `npm run build` (`tsc -b && vite build`) and `npm run lint` (oxlint) plus manual QA — do not invent a test framework.

## Global Constraints

- Workdir for all verify commands: `pixel-simulator-game/frontend`. Backend untouched.
- Boardroom rect becomes `x0: 14, x1: 45`; Strategy Room `x1: 17 → 14`; Research `x0: 42 → 45`. Doors do not move (8/9, 29/30, 50/51 at y11 all stay interior — verified).
- Canvas stays 800×480; explore zoom stays 2; meeting zoom is exactly `1.4`, animated over `CAMERA_PAN_MS` (700ms).
- Seat columns move from x = 26/29/32/35 to 24/29/34/36 (5-tile spacing); rows stay y4/y8.
- Bubble `wordWrap` width (140) and lifetime math unchanged; ambient (non-meeting) bubble behavior byte-identical.
- Transcript stickiness threshold: `scrollHeight - scrollTop - clientHeight < 40`.
- Each task ends with its own commit (messages below); imperative, ending with a period.
- Match on quoted code, not line numbers. All quoted blocks were verified against branch `proxy-war-realignment`.

## File map

| File | Change |
|------|--------|
| `docs/superpowers/plans/2026-08-15-war-room-ui-fixes.md` | **Create** — this plan |
| `pixel-simulator-game/frontend/src/game/officeMap.ts` | Room rects, wander boxes, furniture, `BOARD_SEATS`, `PLAYER_GALLERY`, `BOARD_CAMERA` |
| `pixel-simulator-game/frontend/src/game/textures.ts` | `board_table` canvas 160×32 → 224×32 |
| `pixel-simulator-game/frontend/src/game/OfficeScene.ts` | Meeting zoom; one-bubble rule; no speaker pan during meetings |
| `pixel-simulator-game/frontend/src/App.css` | `100vh` grid, top-aligned stage, transcript scroll container, mobile fallback |
| `pixel-simulator-game/frontend/src/ui/SidePanel.tsx` | Sticky transcript auto-scroll replacing `scrollIntoView` |

---

### Task 1: Enlarge the boardroom (`officeMap.ts` + `textures.ts`)

**Files:**
- Modify: `pixel-simulator-game/frontend/src/game/officeMap.ts`
- Modify: `pixel-simulator-game/frontend/src/game/textures.ts`

**Interfaces:**
- Consumes: existing `ROOMS`, NPC `wander` boxes, `FURNITURE`, `BOARD_SEATS`, `PLAYER_GALLERY`, `BOARD_CAMERA`, `board_table` texture
- Produces: boardroom `x0: 14, x1: 45`; seat columns x = 24/29/34/36; `board_table` 224×32; `BOARD_CAMERA` (29, 6)

- [ ] **Step 1 — move the three top-row walls in lockstep.** In `ROOMS` (`officeMap.ts:23-38`): `war_room` `x1: 17` → `x1: 14`; `boardroom` `x0: 17, x1: 42` → `x0: 14, x1: 45`; `ceo_office` `x0: 42` → `x0: 45`. (Only those three numbers change; `buildGrid()` paints perimeters then punches doors, so lockstep edits keep shared walls consistent.)

- [ ] **Step 2 — shrink wander boxes to the new interiors.** Strategy Room interior is now x1..13, Research x46..58. Four NPC defs (match on the full def block — CEO/HR and PARTNER/OPERATOR share identical wander literals):
- `CEO` (spawn 50,6) and `HR` (spawn 52,8): `wander: { x0: 44, y0: 3, x1: 57, y1: 9 }` → `x0: 46`
- `PARTNER` (spawn 7,8) and `OPERATOR` (spawn 9,6): `wander: { x0: 2, y0: 3, x1: 14, y1: 9 }` → `x1: 13`

- [ ] **Step 3 — boardroom furniture** (`FURNITURE` block, `officeMap.ts:207-218`): `board_table` (25,6) → (22,6); chairs x 26/29/32 → 24/29/34 (both rows y4 and y8); head chairs x35 → x36 (y6 and y8). Leave boardroom plants (18,1)/(41,9) alone.

- [ ] **Step 4 — relocate furniture stranded by the moved walls** (hazard found during review): Strategy Room `{ texture: 'plant', x: 15, y: 1 }` → `x: 12` (x15,y1 is now under the boardroom's auto-drawn label at `(x0+1, y0+1)`); CEO-office `{ texture: 'sofa', x: 44, y: 8 }` → `x: 46` and `{ texture: 'plant', x: 43, y: 1 }` → `x: 57` (both were left inside the new boardroom).

- [ ] **Step 5 — seats + camera** (`officeMap.ts:284-300`): in `BOARD_SEATS` — `chair` (35,6)→(36,6); `ceo`/`analyst`/`hr`/`cto` x26→x24; `gc` x32→x34; `comms` (35,8)→(36,8); `cfo`/`partner`/`operator` stay x29. `PLAYER_GALLERY` (32,8)→(34,8). `BOARD_CAMERA` (30,7)→(29,6).

- [ ] **Step 6 — widen the table texture** (`textures.ts:185-191`), replace:

```typescript
  makeTexture(scene, 'board_table', 160, 32, (ctx) => {
    rect(ctx, 4, 4, 152, 24, '#5d3f2a');
    rect(ctx, 4, 4, 152, 5, '#6f4c32');
    rect(ctx, 8, 14, 144, 4, '#4e3523');
    rect(ctx, 4, 26, 152, 2, '#412c1c');
    for (const px of [20, 52, 84, 116, 140]) rect(ctx, px, 11, 5, 3, '#e8e4dc');
  });
```

with:

```typescript
  makeTexture(scene, 'board_table', 224, 32, (ctx) => {
    rect(ctx, 4, 4, 216, 24, '#5d3f2a');
    rect(ctx, 4, 4, 216, 5, '#6f4c32');
    rect(ctx, 8, 14, 208, 4, '#4e3523');
    rect(ctx, 4, 26, 216, 2, '#412c1c');
    for (const px of [20, 56, 92, 128, 164, 200]) rect(ctx, px, 11, 5, 3, '#e8e4dc');
  });
```

- [ ] **Verify:** `cd pixel-simulator-game/frontend && npm run build && npm run lint` → exit 0, no new lint errors.

- [ ] **Commit:** `Widen the boardroom, spread board seats, and lengthen the table.` (both files)

```bash
git add pixel-simulator-game/frontend/src/game/officeMap.ts \
        pixel-simulator-game/frontend/src/game/textures.ts
git commit -m "Widen the boardroom, spread board seats, and lengthen the table."
```

---

### Task 2: Meeting camera zoom (`OfficeScene.ts`)

**Files:**
- Modify: `pixel-simulator-game/frontend/src/game/OfficeScene.ts`

**Interfaces:**
- Consumes: `CAMERA_PAN_MS = 700`; `startConvene()` pan; `startWalkOut()` before `clearBubbles()`
- Produces: `EXPLORE_ZOOM = 2`; `MEETING_ZOOM = 1.4`; `cam.zoomTo` on convene and walk-out

- [ ] **Step 1 — constants** (after `const CAMERA_PAN_MS = 700;`, line 32): add

```typescript
const EXPLORE_ZOOM = 2;
const MEETING_ZOOM = 1.4;
```

- [ ] **Step 2 — `create()`** (~line 176): `cam.setZoom(2);` → `cam.setZoom(EXPLORE_ZOOM);`

- [ ] **Step 3 — `startConvene()`** (lines 485-489): after the existing `cam.pan(focus.x, focus.y, CAMERA_PAN_MS, 'Sine.easeInOut');` add:

```typescript
    cam.zoomTo(MEETING_ZOOM, CAMERA_PAN_MS, 'Sine.easeInOut');
```

- [ ] **Step 4 — `startWalkOut()`** (lines 509-510): between `this.hideAdvancePrompt();` and `this.clearBubbles();` insert:

```typescript
    this.cameras.main.zoomTo(EXPLORE_ZOOM, CAMERA_PAN_MS, 'Sine.easeInOut');
```

(`clearBubbles()` re-attaches `startFollow(this.player)`; Phaser runs follow and zoom effects concurrently. `layoutBubble` reads `cam.worldView`, so bubble clamping works at any zoom unchanged.)

- [ ] **Verify:** build + lint as above.

- [ ] **Commit:** `Zoom the camera out to frame the whole boardroom during meetings.`

```bash
git add pixel-simulator-game/frontend/src/game/OfficeScene.ts
git commit -m "Zoom the camera out to frame the whole boardroom during meetings."
```

---

### Task 3: One bubble at a time during meetings (`OfficeScene.ts`)

**Files:**
- Modify: `pixel-simulator-game/frontend/src/game/OfficeScene.ts`

**Interfaces:**
- Consumes: `showSpeech(speakerId, text)`; `this.meeting`; `NpcActor.bubble: Phaser.GameObjects.Text | null`
- Produces: meeting path destroys every NPC bubble before showing the new line; per-speaker `cam.pan` only when `!this.meeting`

- [ ] **Step 1 — destroy all live bubbles on a meeting line.** In `showSpeech()` (line 392), replace `npc.bubble?.destroy();` with:

```typescript
    if (this.meeting) {
      // Sequential debate: exactly one speaker's bubble on screen at a time.
      for (const other of this.npcs) {
        other.bubble?.destroy();
        other.bubble = null;
      }
    } else {
      npc.bubble?.destroy();
    }
```

(`NpcActor.bubble` is typed `Phaser.GameObjects.Text | null` — verified, assignment type-checks.)

- [ ] **Step 2 — skip the per-speaker pan while meeting.** Wrap the tail of `showSpeech()` (lines 409-412):

```typescript
    if (!this.meeting) {
      const cam = this.cameras.main;
      cam.stopFollow();
      // Aim a bit below the speaker so an above-head bubble stays in frame.
      cam.pan(npc.sprite.x, npc.sprite.y + 16, 280, 'Sine.easeInOut');
    }
```

Ambient behavior (SPEECH handler outside meetings, line 209-213) is untouched.

- [ ] **Verify:** build + lint.

- [ ] **Commit:** `Show one meeting speech bubble at a time and hold the table camera.`

```bash
git add pixel-simulator-game/frontend/src/game/OfficeScene.ts
git commit -m "Show one meeting speech bubble at a time and hold the table camera."
```

---

### Task 4: Definite-height grid — fixes top gap + page scroll (`App.css`)

**Files:**
- Modify: `pixel-simulator-game/frontend/src/App.css`

**Interfaces:**
- Consumes: `.app`, `.stage`, `.panel`, `.panel-transcript`, `@media (max-width: 720px)`
- Produces: definite `height: 100vh` desktop grid; transcript as scroll container; mobile `height: auto; min-height: 100vh`

Five exact replacements (all block quotes verified against current file):

- [ ] 1. `.app` (lines 17-23): `grid-template-rows: auto 1fr auto` → `auto minmax(0, 1fr) auto`; `min-height: 100vh` → `height: 100vh`.
- [ ] 2. `.stage` (lines 57-63): `align-items: center` → `align-items: flex-start`; add `min-height: 0;` and `overflow-y: auto;`.
- [ ] 3. `.panel` (lines 459-469): add `min-height: 0;` (after `gap: 1rem;`).
- [ ] 4. `.panel-transcript` (lines 557-560): add `overflow-y: auto;`.
- [ ] 5. `@media (max-width: 720px)` `.app` block (lines 584-593): add `height: auto; min-height: 100vh;` so mobile keeps natural document flow.

- [ ] **Verify:** `npm run build` → exit 0 (visual check in final QA).

- [ ] **Commit:** `Pin the app grid to the viewport and scroll only the transcript.`

```bash
git add pixel-simulator-game/frontend/src/App.css
git commit -m "Pin the app grid to the viewport and scroll only the transcript."
```

---

### Task 5: Sticky transcript auto-scroll (`SidePanel.tsx`)

**Files:**
- Modify: `pixel-simulator-game/frontend/src/ui/SidePanel.tsx`

**Interfaces:**
- Consumes: `transcript` state; `.panel-transcript` as overflow container (Task 4)
- Produces: `transcriptRef` + `stickToBottom`; `scrollTop = scrollHeight` only when `scrollHeight - scrollTop - clientHeight < 40`

- [ ] **Step 1** (line 77): replace `const transcriptEnd = useRef<HTMLDivElement>(null);` with:

```tsx
  const transcriptRef = useRef<HTMLDivElement>(null);
  const stickToBottom = useRef(true);
```

- [ ] **Step 2** (lines 112-114): replace the `scrollIntoView` effect with:

```tsx
  useEffect(() => {
    const el = transcriptRef.current;
    if (el && stickToBottom.current) el.scrollTop = el.scrollHeight;
  }, [transcript]);

  const onTranscriptScroll = () => {
    const el = transcriptRef.current;
    if (!el) return;
    stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
  };
```

- [ ] **Step 3** (~line 195): `<div className="panel-section panel-transcript">` → `<div className="panel-section panel-transcript" ref={transcriptRef} onScroll={onTranscriptScroll}>`; delete the sentinel `<div ref={transcriptEnd} />` (~line 210).

- [ ] **Verify:** build + lint — a leftover `transcriptEnd` reference fails `tsc -b`, guarding Step 3.

- [ ] **Commit:** `Stick the transcript to its own scroll container instead of the page.`

```bash
git add pixel-simulator-game/frontend/src/ui/SidePanel.tsx
git commit -m "Stick the transcript to its own scroll container instead of the page."
```

---

## Manual verification (after all tasks)

Run `./run-backend.sh` and `./run-frontend.sh` from repo root, open the Vite URL (default `http://localhost:5173`):

- **Top gap:** canvas sits directly under the header; no tall empty band; no window scrollbar at desktop widths.
- **Room size:** the top-middle War Room spans nearly Strategy-Room-to-Research; longer table, 5-tile chair gaps. Trigger a quarterly convene (walk to the highlighted War Room pad, press `E`): cast snaps to seats and the camera pans **and zooms out** so the whole table + all seats + "Press any key" prompt fit on screen.
- **Bubbles:** each keypress shows exactly one bubble; previous speakers' bubbles vanish; mashing keys never shows more than one; camera holds the table framing (no per-speaker lurch). After the meeting, camera zooms back in and follows the player; ambient NPC bubbles + pan outside meetings still work.
- **Panel:** during a debate the Transcript auto-follows at its bottom while page + KPI cards stay put; scrolling the transcript up mid-debate holds position while new lines arrive; scrolling back to the bottom resumes sticking.
- **Mobile:** below 720px width — single column, page scrolls normally, nothing clipped.
- Optional: repeat with `?scenario=meridian-activist-01`.

## Cross-checks already performed during planning

Door tiles remain interior after wall moves; `ZONES` pads (war_room 3,6; boardroom 28,9; ceo_office 46,6) remain on interior floor; all NPC spawns remain interior; seat-sharing pairs (ceo/cto, analyst/hr, partner/operator) belong to different scenario casts so no same-cast collisions; solid table tiles x22..35 × y6..7 overlap no seat or the player gallery; room labels derive from `ROOMS` and move automatically. Known pre-existing non-goal: the SidePanel shows debate lines as they stream while the canvas key-gates them (desync) — out of scope.

## Self-review

**Spec coverage**

| Problem / constraint | Task |
|----------------------|------|
| Boardroom too small — widen rect, shrink neighbors, spread seats, lengthen table | Task 1 |
| Stranded furniture after wall moves | Task 1 Step 4 |
| Meeting camera zooms to 1.4 and restores to 2 | Task 2 |
| Overlapping bubbles / one speaker at a time | Task 3 Step 1 |
| Per-speaker pan fights table framing | Task 3 Step 2 |
| Ambient (non-meeting) bubbles byte-identical | Task 3 (`else` + untouched SPEECH handler) |
| Empty band between header and canvas | Task 4 `.stage` top-align |
| Transcript `scrollIntoView` scrolls the page | Task 4 definite `100vh` grid + Task 5 sticky scroll |
| Stickiness threshold `< 40` | Task 5 |
| Mobile natural document flow | Task 4 media query |
| Frontend-only, no new files/deps, no invented tests | honored throughout |

**Placeholder scan:** none.

**Type consistency:** `EXPLORE_ZOOM` / `MEETING_ZOOM` named in Task 2 and used in convene/walk-out; `transcriptRef` / `stickToBottom` / `onTranscriptScroll` named in Task 5 Steps 1–3; `BOARD_CAMERA` (29, 6) produced by Task 1 and consumed by existing `startConvene()`.
