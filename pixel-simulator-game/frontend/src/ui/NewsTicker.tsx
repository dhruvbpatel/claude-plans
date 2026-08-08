import { useEffect, useState } from 'react';
import { GameEvents, gameBus } from '../game/eventBus';

interface TickerEntry {
  id: number;
  text: string;
}

/** Ambient wire copy shown before any game news arrives. */
const AMBIENT: string[] = [
  'MRDN flat in early trading as the street waits for the activist\u2019s next move',
  'Meridian Dynamics AGM approaches; governance watchers circle the boardroom',
  'Orbital division margins under scrutiny after another soft quarter',
  'Event-driven desks report fresh inflows \u2014 someone smells a campaign',
];

const MAX_ENTRIES = 12;
const ROTATE_MS = 6000;

let seq = AMBIENT.length;

interface TickerState {
  entries: TickerEntry[];
  idx: number;
}

/**
 * Persistent bottom news ticker (Phase 6). Seeded with ambient headlines,
 * fed by SSE `news` events; a fresh headline jumps to the front of rotation.
 */
export function NewsTicker() {
  const [state, setState] = useState<TickerState>({
    entries: AMBIENT.map((text, i) => ({ id: i, text })),
    idx: 0,
  });

  useEffect(() => {
    const timer = setInterval(
      () => setState((s) => ({ ...s, idx: (s.idx + 1) % s.entries.length })),
      ROTATE_MS,
    );
    const unsub = gameBus.on(GameEvents.NEWS, (payload) => {
      const { text } = payload as { text: string };
      setState((s) => {
        const entries = [...s.entries.slice(-(MAX_ENTRIES - 1)), { id: seq++, text }];
        return { entries, idx: entries.length - 1 };
      });
    });
    return () => {
      clearInterval(timer);
      unsub();
    };
  }, []);

  const item = state.entries[state.idx % state.entries.length];
  return (
    <div className="ticker" role="marquee" aria-label="News ticker">
      <span className="ticker-tag">MRDN WIRE</span>
      <span className="ticker-text" key={`${item.id}-${state.idx}`}>
        {item.text}
      </span>
    </div>
  );
}
