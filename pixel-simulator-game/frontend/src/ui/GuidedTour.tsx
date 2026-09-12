import { useCallback, useEffect, useMemo, useState } from 'react';
import { GameEvents, gameBus } from '../game/eventBus';
import { tourStepsFor } from '../game/tourSteps';
import { scenarioIdFromUrl } from '../net/session';
import { setTourActive, setUiMode, useGame } from '../state/store';

const AUTO_MS = 3500;

export function GuidedTour() {
  const uiMode = useGame((s) => s.uiMode);
  const replay = useGame((s) => s.tourActive);
  const steps = useMemo(() => tourStepsFor(scenarioIdFromUrl()), []);
  const [stepIndex, setStepIndex] = useState(0);
  const step = steps[stepIndex];

  const finish = useCallback(() => {
    gameBus.emit(GameEvents.TOUR_END);
    if (replay) setTourActive(false);
    if (uiMode === 'TOUR') setUiMode('PLAYING');
  }, [replay, uiMode]);

  useEffect(() => {
    if (!step) return;
    gameBus.emit(GameEvents.TOUR_FOCUS, {
      kind: step.kind,
      id: step.id,
    });
  }, [step]);

  useEffect(() => {
    if (!step) return;
    const t = window.setTimeout(() => {
      if (stepIndex + 1 >= steps.length) finish();
      else setStepIndex((i) => i + 1);
    }, AUTO_MS);
    return () => window.clearTimeout(t);
  }, [finish, step, stepIndex, steps.length]);

  if (!step) return null;

  return (
    <div className="tour-caption" role="status">
      <p className="tour-title">{step.title}</p>
      <p className="tour-text">{step.caption}</p>
      <div className="tour-nav">
        <button
          type="button"
          className="dialogue-btn"
          onClick={() => {
            if (stepIndex + 1 >= steps.length) finish();
            else setStepIndex((i) => i + 1);
          }}
        >
          Next
        </button>
        <button type="button" className="dialogue-btn" onClick={finish}>
          Skip
        </button>
        <span className="tour-dots" aria-hidden>
          {steps.map((s, i) => (
            <span key={s.id} className={i === stepIndex ? 'on' : ''} />
          ))}
        </span>
      </div>
    </div>
  );
}
