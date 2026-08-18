import { zoneLabel } from '../net/session';
import {
  optionsGateOpen,
  readingActive,
  useGame,
  voteGateOpen,
} from '../state/store';
import { BoardVoteSummary } from './BoardVoteSummary';
import { DialogueDock } from './DialogueDock';
import { OptionCards } from './OptionCards';

/** Dock below the map: vote → options → dialogue → explore hint. */
export function BottomDock() {
  const showVote = useGame((s) => voteGateOpen(s));
  const showOptions = useGame((s) => optionsGateOpen(s));
  const showReading = useGame((s) => readingActive(s));
  const nextBeat = useGame((s) => s.nextBeat);
  const exploring = useGame((s) => s.serverPhase === 'EXPLORE');

  let body;
  if (showVote) body = <BoardVoteSummary />;
  else if (showOptions) body = <OptionCards />;
  else if (showReading) body = <DialogueDock />;
  else {
    body = (
      <div className="dock-hint">
        {exploring && nextBeat ? (
          <p>
            Next: <strong>{nextBeat.title}</strong> — go to {zoneLabel(nextBeat.zoneId)}
          </p>
        ) : (
          <p>Walk the floor. Yellow pads and people can be interacted with.</p>
        )}
        <p className="dock-controls">
          <kbd>WASD</kbd> / arrows move · <kbd>E</kbd> interact · <kbd>T</kbd> transcript
        </p>
      </div>
    );
  }

  return (
    <section className="dock" aria-label="Dialogue and decisions">
      <div className="dock-inner">{body}</div>
    </section>
  );
}
