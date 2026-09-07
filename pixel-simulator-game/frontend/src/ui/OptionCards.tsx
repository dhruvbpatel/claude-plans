import { useEffect, useState } from 'react';
import { GameEvents, gameBus } from '../game/eventBus';

interface OptionCard {
  id: string;
  label: string;
  pros: string[];
  cons: string[];
}

/** Decision overlay for AWAIT_DECISION — label + pros/cons only, never deltas. */
export function OptionCards() {
  const [options, setOptions] = useState<OptionCard[] | null>(null);
  const [picked, setPicked] = useState<string | null>(null);
  const [rec, setRec] = useState<string | null>(null);

  useEffect(() => {
    const unsubs = [
      gameBus.on(GameEvents.WAR_ROOM, (p) => {
        const room = p as { recommendedLabel?: string };
        setRec(room.recommendedLabel ?? null);
      }),
      gameBus.on(GameEvents.OPTIONS, (p) => {
        setOptions((p as { options: OptionCard[] }).options);
        setPicked(null);
      }),
      gameBus.on(GameEvents.PHASE, (p) => {
        const { phase } = p as { phase: string };
        if (phase !== 'AWAIT_DECISION') {
          setOptions(null);
          setPicked(null);
          setRec(null);
        }
      }),
    ];
    return () => unsubs.forEach((unsub) => unsub());
  }, []);

  if (!options) return null;

  const choose = (id: string) => {
    if (picked) return;
    setPicked(id);
    gameBus.emit(GameEvents.DECIDE, { optionId: id });
  };

  return (
    <div className="option-overlay" role="dialog" aria-label="Choose your move">
      <p className="option-title">Your move</p>
      {rec && <p className="option-rec">Chair recommends: {rec}</p>}
      <div className={`option-cards${options.length >= 4 ? ' four' : ''}`}>
        {options.map((opt) => (
          <button
            key={opt.id}
            className={`option-card${picked === opt.id ? ' picked' : ''}`}
            disabled={picked !== null}
            onClick={() => choose(opt.id)}
          >
            <span className="option-label">{opt.label}</span>
            <ul className="option-pros">
              {opt.pros.map((pro, i) => (
                <li key={i}>+ {pro}</li>
              ))}
            </ul>
            <ul className="option-cons">
              {opt.cons.map((con, i) => (
                <li key={i}>− {con}</li>
              ))}
            </ul>
          </button>
        ))}
      </div>
    </div>
  );
}
