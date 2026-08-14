import { useEffect, useState } from 'react';
import { GameEvents, gameBus } from '../game/eventBus';
import { getSeed } from '../net/session';

interface HistoryEntry {
  beatId: string;
  label: string;
  consequence: string;
}

interface BreakdownRow {
  metricId: string;
  weight: number;
  opening: number;
  current: number;
  ratio: number;
  contribution: number;
}

interface GameEnd {
  outcome: string;
  grade: string;
  summary: {
    kpis: Record<string, number>;
    history: HistoryEntry[];
    composite?: number;
    band?: string;
    breakdown?: BreakdownRow[];
  };
}

const KPI_LABELS: Record<string, string> = {
  stockPrice: 'Stock Price',
  boardResistance: 'Board Resistance',
  ownershipPct: 'Ownership %',
  warChest: 'War Chest',
  mediaHeat: 'Media Heat',
  sharePrice: 'Share price',
  confidence: 'Confidence',
  reputation: 'Reputation',
  cash: 'Cash',
  debt: 'Debt',
  revenue: 'Revenue',
  margin: 'Margin',
  innovation: 'Innovation',
  marketShare: 'Market share',
  morale: 'Morale',
  integrationRisk: 'Integration risk',
  regulatoryRisk: 'Regulatory risk',
  rivalPressure: 'Rival pressure',
  companyValue: 'Company value',
};

/** End-of-game scorecard overlay: grade or composite breakdown, history. */
export function Scorecard() {
  const [end, setEnd] = useState<GameEnd | null>(null);

  useEffect(() => gameBus.on(GameEvents.END, (p) => setEnd(p as GameEnd)), []);

  if (!end) return null;

  const won = end.outcome === 'won';
  const seed = getSeed();
  const breakdown = end.summary.breakdown;
  const composite = end.summary.composite;
  const band = end.summary.band;

  const replay = (keepSeed: boolean) => {
    const url = new URL(window.location.href);
    if (keepSeed && seed !== null) url.searchParams.set('seed', String(seed));
    else url.searchParams.delete('seed');
    window.location.href = url.toString();
  };

  return (
    <div className="scorecard-backdrop" role="dialog" aria-label="Campaign scorecard">
      <div className="scorecard">
        <p className={`scorecard-outcome ${won ? 'won' : 'lost'}`}>
          {won ? 'CAMPAIGN WON' : 'CAMPAIGN LOST'}
        </p>
        <p className="scorecard-grade">
          {composite !== undefined
            ? `${composite.toFixed(1)} · ${band ?? end.grade}`
            : end.grade}
        </p>

        {breakdown && breakdown.length > 0 ? (
          <div className="scorecard-kpis">
            {breakdown.map((row) => (
              <div key={row.metricId} className="scorecard-kpi">
                <span>
                  {KPI_LABELS[row.metricId] ?? row.metricId} ({row.weight})
                </span>
                <strong>
                  {(row.ratio * 100).toFixed(0)}% → {row.contribution.toFixed(1)}
                </strong>
              </div>
            ))}
          </div>
        ) : (
          <div className="scorecard-kpis">
            {Object.entries(end.summary.kpis).map(([key, value]) => (
              <div key={key} className="scorecard-kpi">
                <span>{KPI_LABELS[key] ?? key}</span>
                <strong>{key === 'stockPrice' ? `$${value.toFixed(2)}` : value}</strong>
              </div>
            ))}
          </div>
        )}

        <ol className="scorecard-history">
          {end.summary.history.map((entry, i) => (
            <li key={i}>
              <strong>{entry.label}</strong>
              <span>{entry.consequence}</span>
            </li>
          ))}
        </ol>

        {seed !== null && <p className="scorecard-seed">seed {seed}</p>}
        <div className="scorecard-actions">
          <button className="scorecard-again" onClick={() => replay(true)}>
            Run it back (same seed)
          </button>
          <button className="scorecard-again scorecard-new" onClick={() => replay(false)}>
            New campaign
          </button>
        </div>
      </div>
    </div>
  );
}
