import { useEffect, useState } from 'react';
import { GameEvents, gameBus } from '../game/eventBus';

interface Dissent {
  seatId: string;
  name: string;
  preferredLabel: string;
  concern: string;
}

interface WarRoomPayload {
  quarter: number;
  recommendedCardId: string;
  recommendedLabel: string;
  tally: Record<string, number>;
  confidence: string;
  dissents: Dissent[];
}

/** Recommendation overlay after the war room votes; cards follow. */
export function WarRoomOverlay() {
  const [room, setRoom] = useState<WarRoomPayload | null>(null);

  useEffect(() => {
    const unsubs = [
      gameBus.on(GameEvents.WAR_ROOM, (p) => setRoom(p as WarRoomPayload)),
      gameBus.on(GameEvents.OPTIONS, () => setRoom(null)),
      gameBus.on(GameEvents.PHASE, (p) => {
        const { phase } = p as { phase: string };
        if (phase === 'AWAIT_DECISION' || phase === 'EXPLORE' || phase === 'GAME_END') {
          setRoom(null);
        }
      }),
    ];
    return () => unsubs.forEach((unsub) => unsub());
  }, []);

  if (!room) return null;

  return (
    <div
      className="option-overlay vote-overlay"
      role="dialog"
      aria-label="War room recommendation"
    >
      <p className="option-title">War room</p>
      <p className="vote-adopt">
        Chair recommends: {room.recommendedLabel} ({room.confidence})
      </p>
      {room.dissents.length > 0 && (
        <ul className="vote-rows">
          {room.dissents.map((d) => (
            <li key={d.seatId}>
              <strong>{d.name}</strong> prefers {d.preferredLabel}
            </li>
          ))}
        </ul>
      )}
      <p className="vote-hint">Cards up next — follow or defy</p>
    </div>
  );
}
