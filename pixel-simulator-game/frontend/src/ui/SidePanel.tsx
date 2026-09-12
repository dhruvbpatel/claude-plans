import { useEffect, useRef, useState } from 'react';
import { GameEvents, gameBus } from '../game/eventBus';
import { scenarioIdFromUrl, zoneLabel } from '../net/session';
import { setTranscriptOpen, useGame } from '../state/store';
import { SPEAKER_NAMES } from '../types';

type Kpis = Record<string, number>;

const NOVATECH_META: { key: string; label: string; group: string; fmt: (v: number) => string }[] = [
  { key: 'sharePrice', label: 'Share price', group: 'Market', fmt: (v) => v.toFixed(1) },
  { key: 'confidence', label: 'Confidence', group: 'Market', fmt: (v) => `${Math.round(v)}` },
  { key: 'reputation', label: 'Reputation', group: 'Market', fmt: (v) => `${Math.round(v)}` },
  { key: 'cash', label: 'Cash', group: 'Financial', fmt: (v) => `$${v.toFixed(0)}M` },
  { key: 'debt', label: 'Debt', group: 'Financial', fmt: (v) => `$${v.toFixed(0)}M` },
  { key: 'revenue', label: 'Revenue', group: 'Financial', fmt: (v) => `$${v.toFixed(0)}M` },
  { key: 'margin', label: 'Margin', group: 'Financial', fmt: (v) => `${v.toFixed(1)}%` },
  { key: 'innovation', label: 'Innovation', group: 'Ops', fmt: (v) => `${Math.round(v)}` },
  { key: 'marketShare', label: 'Share', group: 'Ops', fmt: (v) => `${v.toFixed(1)}` },
  { key: 'morale', label: 'Morale', group: 'People', fmt: (v) => `${Math.round(v)}` },
  { key: 'integrationRisk', label: 'Integration', group: 'Risk', fmt: (v) => `${Math.round(v)}` },
  { key: 'regulatoryRisk', label: 'Regulatory', group: 'Risk', fmt: (v) => `${Math.round(v)}` },
];

const MERIDIAN_META: { key: string; label: string; group: string; fmt: (v: number) => string }[] = [
  { key: 'stockPrice', label: 'Stock Price', group: 'KPIs', fmt: (v) => `$${v.toFixed(2)}` },
  { key: 'boardResistance', label: 'Board Resistance', group: 'KPIs', fmt: (v) => `${v}` },
  { key: 'ownershipPct', label: 'Ownership', group: 'KPIs', fmt: (v) => `${v}%` },
  { key: 'warChest', label: 'War Chest', group: 'KPIs', fmt: (v) => `$${v}M` },
  { key: 'mediaHeat', label: 'Media Heat', group: 'KPIs', fmt: (v) => `${v}` },
];

/** HUD: phase badge, grouped metrics, rival pressure, quarter, recent lines. */
export function SidePanel() {
  const phase = useGame((s) => s.serverPhase);
  const kpis = useGame((s) => s.kpis);
  const beat = useGame((s) => s.beat);
  const nextBeat = useGame((s) => s.nextBeat);
  const seed = useGame((s) => s.session?.seed ?? null);
  const visibleLines = useGame((s) => s.visibleLines);
  const recent = visibleLines.slice(-6);
  const [deltas, setDeltas] = useState<Record<string, number>>({});
  const [devLock, setDevLock] = useState(false);
  const prevKpis = useRef<Kpis>(kpis);
  const deltaTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const prev = prevKpis.current;
    prevKpis.current = kpis;
    const changed: Record<string, number> = {};
    for (const key of Object.keys(kpis)) {
      const diff = kpis[key] - (prev[key] ?? kpis[key]);
      if (Math.abs(diff) > 1e-9 && key in prev) changed[key] = diff;
    }
    if (Object.keys(changed).length === 0) return;
    setDeltas(changed);
    if (deltaTimer.current) clearTimeout(deltaTimer.current);
    deltaTimer.current = setTimeout(() => setDeltas({}), 2400);
  }, [kpis]);

  const toggleDevLock = (locked: boolean) => {
    setDevLock(locked);
    gameBus.emit(GameEvents.INPUT_LOCK, { locked });
  };

  const exploring = phase === 'EXPLORE';
  const nova = !scenarioIdFromUrl().includes('meridian');
  const meta = nova ? NOVATECH_META : MERIDIAN_META;
  const groups = [...new Set(meta.map((m) => m.group))];
  const pressure = kpis.rivalPressure ?? 0;

  return (
    <aside className="panel" aria-label="Game HUD">
      <div className="panel-section">
        <h2>Phase</h2>
        <p className="phase-badge">{phase}</p>
        {nova && beat && <p className="quarter-line">Quarter {beat.n} / 8</p>}
        {exploring && nextBeat && (
          <p className="next-hint">
            Next: <strong>{nextBeat.title}</strong> — go to {zoneLabel(nextBeat.zoneId)}
          </p>
        )}
      </div>

      {nova && (
        <div className="panel-section">
          <h2>Rival pressure</h2>
          <div className="pressure-track" aria-label="Rival pressure">
            <div
              className="pressure-fill"
              style={{ width: `${Math.max(0, Math.min(100, pressure))}%` }}
            />
            <div className="pressure-mark" style={{ left: '55%' }} title="Attack threshold" />
          </div>
          <p className="pressure-value">{Math.round(pressure)} / 100</p>
        </div>
      )}

      {groups.map((group) => (
        <div className="panel-section" key={group}>
          <h2>{group}</h2>
          <div className="kpi-grid">
            {meta
              .filter((m) => m.group === group)
              .map(({ key, label, fmt }) => {
                const delta = deltas[key];
                return (
                  <div
                    key={key}
                    className={`kpi-card${
                      delta !== undefined ? (delta >= 0 ? ' kpi-up' : ' kpi-down') : ''
                    }`}
                  >
                    <span className="kpi-label">{label}</span>
                    <span className="kpi-value">{fmt(kpis[key] ?? 0)}</span>
                    {delta !== undefined && (
                      <span className={`kpi-delta ${delta >= 0 ? 'up' : 'down'}`}>
                        {delta > 0 ? '+' : ''}
                        {Math.round(delta * 100) / 100}
                      </span>
                    )}
                  </div>
                );
              })}
          </div>
        </div>
      ))}

      {!exploring && beat && (
        <div className="panel-section">
          <h2>
            {nova ? 'Quarter' : 'Beat'} {beat.n} — {beat.title}
          </h2>
          <p className="beat-situation">{beat.situation}</p>
        </div>
      )}

      <div className="panel-section panel-transcript">
        <h2>Recent</h2>
        {recent.length === 0 ? (
          <p className="placeholder">
            {exploring ? 'Walk to the highlighted room and press E.' : 'Debate starting…'}
          </p>
        ) : (
          <ul>
            {recent.map((line) => (
              <li key={`${line.blockKey}-${line.index}`}>
                <strong>{SPEAKER_NAMES[line.speakerId] ?? line.speakerId}:</strong> {line.text}
              </li>
            ))}
          </ul>
        )}
        <button
          type="button"
          className="transcript-open"
          onClick={() => setTranscriptOpen(true)}
        >
          Open transcript (T)
        </button>
      </div>

      <div className="panel-section">
        <label className="dev-lock">
          <input
            type="checkbox"
            checked={devLock}
            onChange={(e) => toggleDevLock(e.target.checked)}
          />
          Soft-lock input (dev)
        </label>
        {seed !== null && <p className="seed-line">seed {seed}</p>}
      </div>
    </aside>
  );
}
