import { setTranscriptOpen, useGame } from '../state/store';
import { SPEAKER_NAMES, type DebateBlock } from '../types';

function gatedLines(block: DebateBlock) {
  const max =
    block.complete && block.proceeded ? block.lines.length - 1 : block.maxSeen;
  return block.lines.filter((line) => line.index <= max);
}

export function TranscriptDrawer() {
  const open = useGame((s) => s.transcriptOpen);
  const debates = useGame((s) => s.debates);

  if (!open) return null;

  const groups = new Map<number, DebateBlock[]>();
  for (const block of debates) {
    const list = groups.get(block.quarter) ?? [];
    list.push(block);
    groups.set(block.quarter, list);
  }
  const quarters = [...groups.keys()].sort((a, b) => a - b);

  return (
    <div className="transcript-drawer" role="dialog" aria-label="Transcript">
      <div className="transcript-panel">
        <header className="transcript-head">
          <h2>Transcript</h2>
          <button
            type="button"
            className="dialogue-btn"
            onClick={() => setTranscriptOpen(false)}
            aria-label="Close transcript"
          >
            ✕
          </button>
        </header>
        {quarters.length === 0 ? (
          <p className="placeholder">No lines yet. Interact to start a beat.</p>
        ) : (
          quarters.map((q) => (
            <section key={q} className="transcript-quarter">
              <h3>Quarter {q}</h3>
              {(groups.get(q) ?? []).map((block) => {
                const lines = gatedLines(block);
                return (
                  <div key={block.key} className="transcript-beat">
                    <h4>{block.title || block.beatId}</h4>
                    {lines.length === 0 ? (
                      <p className="placeholder">Nothing revealed yet.</p>
                    ) : (
                      <ul>
                        {lines.map((line) => (
                          <li key={`${block.key}-${line.index}`}>
                            <strong>
                              {SPEAKER_NAMES[line.speakerId] ?? line.speakerId}:
                            </strong>{' '}
                            {line.text}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                );
              })}
            </section>
          ))
        )}
      </div>
    </div>
  );
}
