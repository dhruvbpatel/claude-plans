import { useEffect } from 'react';
import { boardVoteDismissed, useGame } from '../state/store';

export function BoardVoteSummary() {
  const vote = useGame((s) => s.boardVote);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Enter') return;
      e.preventDefault();
      boardVoteDismissed();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  if (!vote) return null;

  return (
    <div className="option-dock vote-dock" role="dialog" aria-label="Board vote">
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
      <button type="button" className="dialogue-enter" onClick={() => boardVoteDismissed()}>
        Continue <kbd>Enter</kbd>
      </button>
    </div>
  );
}
