import { useEffect } from 'react';
import {
  cursorBack,
  cursorForward,
  proceed,
  useGame,
} from '../state/store';
import { SPEAKER_COLORS, SPEAKER_NAMES } from '../types';

/** Visual-novel line reader. Mounted only while a debate is being read. */
export function DialogueDock() {
  const block = useGame((s) => s.debates.find((d) => d.key === s.activeKey) ?? null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft') {
        e.preventDefault();
        cursorBack();
      } else if (e.key === 'ArrowRight' || e.key === ' ') {
        e.preventDefault();
        cursorForward();
      } else if (e.key === 'Enter') {
        e.preventDefault();
        proceed();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  if (!block) return null;

  const line = block.cursor >= 0 ? block.lines[block.cursor] : null;
  const n = block.lines.length;
  const last = n - 1;
  const caughtUp = n === 0 || block.cursor >= last;
  const typing = !block.complete && caughtUp;
  const canProceed = block.complete && n > 0 && block.cursor === last;
  const color = line ? (SPEAKER_COLORS[line.speakerId] ?? '#8aa0b8') : '#8aa0b8';
  const name = line ? (SPEAKER_NAMES[line.speakerId] ?? line.speakerId) : '…';

  return (
    <div className="dialogue-dock" role="region" aria-label="Debate dialogue">
      <div className="dialogue-speaker">
        <span className="dialogue-swatch" style={{ background: color }} />
        <strong>{name}</strong>
      </div>
      <p className="dialogue-text">{line?.text ?? (typing ? 'Waiting for the first line…' : '')}</p>
      <div className="dialogue-nav">
        <button
          type="button"
          className="dialogue-btn"
          disabled={block.cursor <= 0}
          onClick={() => cursorBack()}
          aria-label="Previous line"
        >
          ◀
        </button>
        <span className="dialogue-count">
          Line {Math.max(block.cursor + 1, 0)} of {n}
          {block.complete ? '' : '+'}
        </span>
        <button
          type="button"
          className="dialogue-btn"
          disabled={caughtUp}
          onClick={() => cursorForward()}
          aria-label="Next line"
        >
          ▶
        </button>
        {typing && <span className="dialogue-typing">typing…</span>}
        {canProceed && (
          <button type="button" className="dialogue-enter" onClick={() => proceed()}>
            Continue <kbd>Enter</kbd>
          </button>
        )}
      </div>
    </div>
  );
}
