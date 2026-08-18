import { scenarioIdFromUrl } from '../net/session';
import { setUiMode } from '../state/store';

const COPY: Record<string, { who: string; against: string; objective: string }> = {
  'novatech-proxy-war-01': {
    who: 'You are NovaTech’s CEO.',
    against: 'An activist is running a proxy war for the company.',
    objective: 'Steer eight quarters of war-room decisions and outlast them.',
  },
  'meridian-activist-01': {
    who: 'You are the activist.',
    against: 'Meridian Dynamics is undervalued and the board is in the way.',
    objective: 'Build a stake, apply pressure, and force structural change.',
  },
};

const FALLBACK = {
  who: 'You are in the campaign.',
  against: 'The other side wants the company.',
  objective: 'Walk the floor, press E to interact, and pick your moves.',
};

export function IntroBanner() {
  const copy = COPY[scenarioIdFromUrl()] ?? FALLBACK;

  return (
    <div className="intro-banner" role="dialog" aria-label="Campaign briefing">
      <div className="intro-card">
        <p className="intro-kicker">Briefing</p>
        <h2>{copy.who}</h2>
        <p>{copy.against}</p>
        <p>{copy.objective}</p>
        <div className="intro-actions">
          <button type="button" className="scorecard-again" onClick={() => setUiMode('TOUR')}>
            Continue
          </button>
          <button
            type="button"
            className="scorecard-again scorecard-new"
            onClick={() => setUiMode('PLAYING')}
          >
            Skip
          </button>
        </div>
      </div>
    </div>
  );
}
