/**
 * Client game store. Mid-game refresh loses this history — restart is already
 * a full page reload today.
 */
import { useSyncExternalStore } from 'react';
import type {
  BeatInfo,
  BoardVotePayload,
  DebateBlock,
  DebateKind,
  NextBeatHint,
  OptionCard,
  ServerPhase,
  SessionInfo,
  UiMode,
  VisibleLine,
  WarRoomPayload,
} from '../types';

export interface GameSnapshot {
  uiMode: UiMode;
  tourActive: boolean;
  serverPhase: ServerPhase;
  session: SessionInfo | null;
  kpis: Record<string, number>;
  beat: BeatInfo | null;
  nextBeat: NextBeatHint | null;
  debates: DebateBlock[];
  activeKey: string | null;
  pendingOptions: OptionCard[] | null;
  warRoom: WarRoomPayload | null;
  boardVote: BoardVotePayload | null;
  transcriptOpen: boolean;
  visibleLines: VisibleLine[];
}

function initialState(): GameSnapshot {
  return {
    uiMode: 'INTRO',
    tourActive: false,
    serverPhase: 'EXPLORE',
    session: null,
    kpis: {},
    beat: null,
    nextBeat: null,
    debates: [],
    activeKey: null,
    pendingOptions: null,
    warRoom: null,
    boardVote: null,
    transcriptOpen: false,
    visibleLines: [],
  };
}

const listeners = new Set<() => void>();
let state: GameSnapshot = initialState();

function emit(): void {
  for (const listener of listeners) listener();
}

function computeVisibleLines(debates: DebateBlock[]): VisibleLine[] {
  const out: VisibleLine[] = [];
  for (const block of debates) {
    const max =
      block.complete && block.proceeded ? block.lines.length - 1 : block.maxSeen;
    for (const line of block.lines) {
      if (line.index <= max) out.push({ ...line, blockKey: block.key });
    }
  }
  return out;
}

function commit(partial: Partial<GameSnapshot>): void {
  const next: GameSnapshot = { ...state, ...partial };
  if (partial.debates) next.visibleLines = computeVisibleLines(next.debates);
  else next.visibleLines = state.visibleLines;
  state = next;
  emit();
}

function activeBlock(s: GameSnapshot = state): DebateBlock | undefined {
  if (!s.activeKey) return undefined;
  return s.debates.find((d) => d.key === s.activeKey);
}

function patchActive(fn: (block: DebateBlock) => DebateBlock): void {
  const key = state.activeKey;
  if (!key) return;
  let changed = false;
  const debates = state.debates.map((block) => {
    if (block.key !== key) return block;
    const next = fn(block);
    if (next !== block) changed = true;
    return next;
  });
  if (changed) commit({ debates });
}

export function getState(): GameSnapshot {
  return state;
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function useGame<T>(selector: (s: GameSnapshot) => T): T {
  return useSyncExternalStore(
    subscribe,
    () => selector(state),
    () => selector(state),
  );
}

export function resetStore(): void {
  state = initialState();
  emit();
}

export function optionsGateOpen(s: GameSnapshot = state): boolean {
  if (!s.pendingOptions) return false;
  const active = activeBlock(s);
  return !active || active.proceeded;
}

export function voteGateOpen(s: GameSnapshot = state): boolean {
  if (!s.boardVote) return false;
  const active = activeBlock(s);
  return !active || active.proceeded;
}

export function readingActive(s: GameSnapshot = state): boolean {
  const active = activeBlock(s);
  return Boolean(active && !active.proceeded);
}

export function phaseChanged(phase: ServerPhase): void {
  const leaveDecision = phase !== 'AWAIT_DECISION';
  commit({
    serverPhase: phase,
    ...(leaveDecision ? { pendingOptions: null, warRoom: null } : {}),
  });
}

export function sessionStarted(session: SessionInfo): void {
  commit({ session });
}

export function kpisPatched(kpis: Record<string, number>): void {
  commit({ kpis: { ...state.kpis, ...kpis } });
}

export function beatReceived(beat: BeatInfo): void {
  commit({ beat });
}

export function nextBeatReceived(nextBeat: NextBeatHint): void {
  commit({ nextBeat });
}

export function debateOpened(input: { kind: DebateKind; beatId?: string }): void {
  const beat = state.beat;
  const beatId = input.beatId ?? beat?.beatId ?? 'unknown';
  const ordinal = state.debates.filter((d) => d.beatId === beatId).length;
  const block: DebateBlock = {
    key: `${beatId}#${ordinal}`,
    beatId,
    quarter: beat?.n ?? 0,
    title: beat?.title ?? '',
    kind: input.kind,
    lines: [],
    complete: false,
    cursor: -1,
    maxSeen: -1,
    proceeded: false,
  };
  commit({ debates: [...state.debates, block], activeKey: block.key });
}

export function lineReceived(payload: { speakerId: string; text: string }): void {
  const active = activeBlock();
  if (!active || active.proceeded) {
    debateOpened({ kind: 'free_roam' });
  }
  patchActive((block) => {
    const index = block.lines.length;
    const first = block.cursor < 0;
    return {
      ...block,
      lines: [...block.lines, { speakerId: payload.speakerId, text: payload.text, index }],
      cursor: first ? 0 : block.cursor,
      maxSeen: first ? 0 : block.maxSeen,
    };
  });
}

export function debateCompleted(): void {
  patchActive((block) => (block.complete ? block : { ...block, complete: true }));
}

export function cursorForward(): void {
  patchActive((block) => {
    const last = block.lines.length - 1;
    if (last < 0 || block.cursor >= last) return block;
    const cursor = block.cursor + 1;
    return { ...block, cursor, maxSeen: Math.max(block.maxSeen, cursor) };
  });
}

export function cursorBack(): void {
  patchActive((block) => {
    if (block.cursor <= 0) return block;
    return { ...block, cursor: block.cursor - 1 };
  });
}

export function proceed(): void {
  patchActive((block) => {
    const last = block.lines.length - 1;
    if (!block.complete || last < 0 || block.cursor !== last || block.proceeded) {
      return block;
    }
    return { ...block, proceeded: true };
  });
}

export function optionsReceived(options: OptionCard[]): void {
  commit({ pendingOptions: options });
}

export function warRoomReceived(warRoom: WarRoomPayload): void {
  commit({ warRoom });
}

export function boardVoteReceived(boardVote: BoardVotePayload): void {
  commit({ boardVote });
}

export function boardVoteDismissed(): void {
  commit({ boardVote: null });
}

export function setUiMode(uiMode: UiMode): void {
  commit({ uiMode });
}

export function setTourActive(tourActive: boolean): void {
  commit({ tourActive });
}

export function setTranscriptOpen(transcriptOpen: boolean): void {
  commit({ transcriptOpen });
}
