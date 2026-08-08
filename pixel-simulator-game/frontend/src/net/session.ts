/**
 * Session client (Phase 4): creates the backend session, bridges the SSE
 * stream onto the game bus, and forwards interact/decide bus events to REST.
 * API shapes per SPEC.md §5; bus names per SPEC.md §6.
 */
import { GameEvents, gameBus } from '../game/eventBus';

export interface NextBeatHint {
  beatId: string;
  n: number;
  title: string;
  zoneId: string;
  npcId?: string | null;
}

const ZONE_LABELS: Record<string, string> = {
  lobby: 'Lobby',
  trading_floor: 'Trading Floor',
  war_room: 'War Room',
  ceo_office: 'CEO Office',
  cfo_office: 'CFO Office',
  gc_office: 'GC Office',
  boardroom: 'Boardroom',
  press_bay: 'Press Bay',
};

export function zoneLabel(zoneId: string): string {
  return ZONE_LABELS[zoneId] ?? zoneId;
}

let started = false;
let sessionId: string | null = null;
let sessionSeed: number | null = null;
let deciding = false;

/** Seed of the live session (known once the backend responds). */
export function getSeed(): number | null {
  return sessionSeed;
}

/** Optional replay seed from the URL: `?seed=123`. */
function seedFromUrl(): number | undefined {
  const raw = new URLSearchParams(window.location.search).get('seed');
  if (raw === null) return undefined;
  const n = Number(raw);
  return Number.isSafeInteger(n) && n >= 0 ? n : undefined;
}

/** Idempotent boot (React StrictMode double-mounts effects in dev). */
export function startSession(): void {
  if (started) return;
  started = true;
  void boot();
}

async function boot(): Promise<void> {
  try {
    const seed = seedFromUrl();
    const res = await fetch('/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        scenarioId: 'meridian-activist-01',
        ...(seed !== undefined ? { seed } : {}),
      }),
    });
    if (!res.ok) throw new Error(`POST /sessions → ${res.status}`);
    const data = await res.json();
    sessionId = data.sessionId as string;
    sessionSeed = data.seed as number;
    gameBus.emit(GameEvents.SESSION, { sessionId, seed: sessionSeed });
    connectEvents(sessionId);
    wireOutbound();
  } catch (err) {
    console.error('[session] boot failed', err);
    gameBus.emit(GameEvents.NEWS, { text: 'Backend unreachable — is uvicorn running on :8000?' });
    started = false; // allow a retry on next mount
  }
}

function connectEvents(id: string): void {
  const source = new EventSource(`/sessions/${id}/events`);

  const forward = (sse: string, bus: string) => {
    source.addEventListener(sse, (e) => {
      gameBus.emit(bus, JSON.parse((e as MessageEvent).data));
    });
  };

  source.addEventListener('phase', (e) => {
    const { phase } = JSON.parse((e as MessageEvent).data) as { phase: string };
    gameBus.emit(GameEvents.PHASE, { phase });
  });
  forward('debate_delta', GameEvents.SPEECH);
  forward('kpi_patch', GameEvents.KPI);
  forward('options', GameEvents.OPTIONS);
  forward('news', GameEvents.NEWS);
  forward('game_end', GameEvents.END);
  forward('beat', GameEvents.BEAT);
  forward('next_beat', GameEvents.NEXT_BEAT);

  source.onerror = () => {
    // EventSource auto-reconnects; the queue on the server buffers misses.
    console.warn('[session] SSE connection error — retrying');
  };
}

function wireOutbound(): void {
  gameBus.on(GameEvents.INTERACT, async (payload) => {
    if (!sessionId) return;
    const { targetId } = payload as { targetId: string };
    try {
      const res = await fetch(`/sessions/${sessionId}/interact`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ targetId }),
      });
      const data = await res.json();
      if (data.lobbyBonus === 'spent') {
        // Bonus already claimed this beat; 'granted' arrives via SSE news.
        gameBus.emit(GameEvents.NEWS, {
          text: 'The lobby is quiet — one favor per move.',
        });
      } else if (!data.accepted && !data.lobbyBonus && data.nextBeat) {
        const hint = data.nextBeat as NextBeatHint;
        gameBus.emit(GameEvents.NEWS, {
          text: `Nothing to do here. Next: ${hint.title} — ${zoneLabel(hint.zoneId)}`,
        });
      }
    } catch (err) {
      console.error('[session] interact failed', err);
    }
  });

  gameBus.on(GameEvents.DECIDE, async (payload) => {
    if (!sessionId || deciding) return;
    deciding = true;
    const { optionId } = payload as { optionId: string };
    try {
      const res = await fetch(`/sessions/${sessionId}/decide`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ optionId }),
      });
      if (!res.ok) console.error('[session] decide rejected', await res.text());
    } catch (err) {
      console.error('[session] decide failed', err);
    } finally {
      deciding = false;
    }
  });
}
