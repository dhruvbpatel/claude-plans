import { useEffect, useRef, useState } from 'react';
import { GameEvents, gameBus } from '../game/eventBus';
import { zoneLabel, type NextBeatHint } from '../net/session';

type Kpis = Record<string, number>;

const KPI_DEFAULTS: Kpis = {
  stockPrice: 42.0,
  boardResistance: 55,
  ownershipPct: 6.5,
  warChest: 120,
  mediaHeat: 20,
};

const KPI_META: { key: string; label: string; fmt: (v: number) => string }[] = [
  { key: 'stockPrice', label: 'Stock Price', fmt: (v) => `$${v.toFixed(2)}` },
  { key: 'boardResistance', label: 'Board Resistance', fmt: (v) => `${v}` },
  { key: 'ownershipPct', label: 'Ownership', fmt: (v) => `${v}%` },
  { key: 'warChest', label: 'War Chest', fmt: (v) => `$${v}M` },
  { key: 'mediaHeat', label: 'Media Heat', fmt: (v) => `${v}` },
];

interface SpeechLine {
  speakerId: string;
  text: string;
}

interface BeatInfo {
  beatId: string;
  n: number;
  title: string;
  situation: string;
}

const SPEAKER_NAMES: Record<string, string> = {
  ceo: 'CEO',
  cfo: 'CFO',
  gc: 'General Counsel',
  chair: 'Chair',
  analyst: 'Analyst',
  partner: 'Partner',
};

/** HUD: phase badge, animated KPI cards, current beat, transcript, next-beat hint. */
export function SidePanel() {
  const [phase, setPhase] = useState('EXPLORE');
  const [kpis, setKpis] = useState<Kpis>(KPI_DEFAULTS);
  const [deltas, setDeltas] = useState<Record<string, number>>({});
  const [transcript, setTranscript] = useState<SpeechLine[]>([]);
  const [beat, setBeat] = useState<BeatInfo | null>(null);
  const [nextBeat, setNextBeat] = useState<NextBeatHint | null>(null);
  const [seed, setSeed] = useState<number | null>(null);
  const [devLock, setDevLock] = useState(false);
  const transcriptEnd = useRef<HTMLDivElement>(null);
  const deltaTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const unsubs = [
      gameBus.on(GameEvents.PHASE, (p) => setPhase((p as { phase: string }).phase)),
      gameBus.on(GameEvents.KPI, (p) => {
        const next = (p as { kpis: Kpis }).kpis;
        setKpis((prev) => {
          const changed: Record<string, number> = {};
          for (const key of Object.keys(next)) {
            const diff = next[key] - (prev[key] ?? 0);
            if (Math.abs(diff) > 1e-9) changed[key] = diff;
          }
          if (Object.keys(changed).length > 0) {
            setDeltas(changed);
            if (deltaTimer.current) clearTimeout(deltaTimer.current);
            deltaTimer.current = setTimeout(() => setDeltas({}), 2400);
          }
          return { ...prev, ...next };
        });
      }),
      gameBus.on(GameEvents.SPEECH, (p) =>
        setTranscript((prev) => [...prev.slice(-40), p as SpeechLine]),
      ),
      gameBus.on(GameEvents.BEAT, (p) => {
        setBeat(p as BeatInfo);
        setTranscript([]);
      }),
      gameBus.on(GameEvents.NEXT_BEAT, (p) => setNextBeat(p as NextBeatHint)),
      gameBus.on(GameEvents.SESSION, (p) => setSeed((p as { seed: number }).seed)),
    ];
    return () => unsubs.forEach((unsub) => unsub());
  }, []);

  useEffect(() => {
    transcriptEnd.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [transcript]);

  const toggleDevLock = (locked: boolean) => {
    setDevLock(locked);
    gameBus.emit(GameEvents.INPUT_LOCK, { locked });
  };

  const exploring = phase === 'EXPLORE';

  return (
    <aside className="panel" aria-label="Game HUD">
      <div className="panel-section">
        <h2>Phase</h2>
        <p className="phase-badge">{phase}</p>
        {exploring && nextBeat && (
          <p className="next-hint">
            Next: <strong>{nextBeat.title}</strong> — go to {zoneLabel(nextBeat.zoneId)}
          </p>
        )}
      </div>

      <div className="panel-section">
        <h2>KPIs</h2>
        <div className="kpi-grid">
          {KPI_META.map(({ key, label, fmt }) => {
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

      {!exploring && beat && (
        <div className="panel-section">
          <h2>
            Beat {beat.n} — {beat.title}
          </h2>
          <p className="beat-situation">{beat.situation}</p>
        </div>
      )}

      <div className="panel-section panel-transcript">
        <h2>Transcript</h2>
        {transcript.length === 0 ? (
          <p className="placeholder">
            {exploring ? 'Walk to the highlighted room and press E.' : 'Debate starting…'}
          </p>
        ) : (
          <ul>
            {transcript.map((line, i) => (
              <li key={i}>
                <strong>{SPEAKER_NAMES[line.speakerId] ?? line.speakerId}:</strong> {line.text}
              </li>
            ))}
          </ul>
        )}
        <div ref={transcriptEnd} />
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
