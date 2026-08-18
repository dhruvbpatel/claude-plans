import { useState } from 'react';
import { GameEvents, gameBus } from '../game/eventBus';
import { useGame } from '../state/store';

/** Decision cards for AWAIT_DECISION — label + pros/cons only, never deltas. */
export function OptionCards() {
  const options = useGame((s) => s.pendingOptions);
  const warRoom = useGame((s) => s.warRoom);
  const [picked, setPicked] = useState<string | null>(null);

  if (!options) return null;

  const choose = (id: string) => {
    if (picked) return;
    setPicked(id);
    gameBus.emit(GameEvents.DECIDE, { optionId: id });
  };

  return (
    <div className="option-dock" role="dialog" aria-label="Choose your move">
      <p className="option-title">Your move</p>
      {warRoom && (
        <>
          <p className="option-rec">
            Chair recommends: {warRoom.recommendedLabel} ({warRoom.confidence})
          </p>
          {warRoom.dissents.length > 0 && (
            <ul className="vote-rows">
              {warRoom.dissents.map((d) => (
                <li key={d.seatId}>
                  <strong>{d.name}</strong> prefers {d.preferredLabel}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
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
