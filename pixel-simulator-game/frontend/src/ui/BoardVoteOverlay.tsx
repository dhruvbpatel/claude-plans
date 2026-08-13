import { useEffect, useState } from 'react';
import { GameEvents, gameBus } from '../game/eventBus';

interface VoteRow {
  speakerId: string;
  name: string;
  optionId: string;
  label: string;
}

interface BoardVotePayload {
  motionId: string;
  motionLabel: string;
  votes: VoteRow[];
  winningOptionId: string;
  winningLabel: string;
  tieBrokenBy?: string;
}

export function BoardVoteOverlay() {
  const [vote, setVote] = useState<BoardVotePayload | null>(null);

  useEffect(() => {
    const unsub = gameBus.on(GameEvents.BOARD_VOTE, (p) => {
      setVote(p as BoardVotePayload);
    });
    const onKey = () => setVote(null);
    window.addEventListener('keydown', onKey);
    return () => {
      unsub();
      window.removeEventListener('keydown', onKey);
    };
  }, []);

  if (!vote) return null;

  return (
    <div
      className="option-overlay vote-overlay"
      role="dialog"
      aria-label="Board vote"
      onClick={() => setVote(null)}
    >
      <p className="option-title">Board vote</p>
      <p className="vote-motion">Your motion: {vote.motionLabel}</p>
      <ul className="vote-rows">
        {vote.votes.map((row) => (
          <li key={row.speakerId}>
            <strong>{row.name}</strong> — {row.label}
          </li>
        ))}
      </ul>
      <p className="vote-adopt">The board adopts: {vote.winningLabel}</p>
      {vote.tieBrokenBy === 'chair' ? (
        <p className="vote-tie">Chair breaks the tie.</p>
      ) : null}
      <p className="vote-hint">Press any key</p>
    </div>
  );
}
