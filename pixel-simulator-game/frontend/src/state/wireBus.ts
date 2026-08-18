import { GameEvents, gameBus } from '../game/eventBus';
import type {
  BeatInfo,
  BoardVotePayload,
  NextBeatHint,
  OptionCard,
  ServerPhase,
  WarRoomPayload,
} from '../types';
import {
  beatReceived,
  boardVoteReceived,
  debateCompleted,
  debateOpened,
  getState,
  kpisPatched,
  lineReceived,
  nextBeatReceived,
  optionsReceived,
  phaseChanged,
  sessionStarted,
  subscribe,
  warRoomReceived,
} from './store';

let wired = false;
let lastShownSig = '';
let dismissedKey: string | null = null;

/** Idempotent bus→store bridge. The only place SSE/bus events mutate the store. */
export function wireStore(): void {
  if (wired) return;
  wired = true;

  gameBus.on(GameEvents.PHASE, (payload) => {
    phaseChanged((payload as { phase: ServerPhase }).phase);
  });
  gameBus.on(GameEvents.SESSION, (payload) => {
    const { sessionId, seed } = payload as { sessionId: string; seed: number };
    sessionStarted({ sessionId, seed });
  });
  gameBus.on(GameEvents.KPI, (payload) => {
    kpisPatched((payload as { kpis: Record<string, number> }).kpis);
  });
  gameBus.on(GameEvents.BEAT, (payload) => {
    beatReceived(payload as BeatInfo);
  });
  gameBus.on(GameEvents.NEXT_BEAT, (payload) => {
    nextBeatReceived(payload as NextBeatHint);
  });
  gameBus.on(GameEvents.CONVENE, (payload) => {
    const { beatId, motionId } = payload as { beatId?: string; motionId?: string };
    debateOpened({
      kind: motionId ? 'board_motion' : 'war_room',
      beatId,
    });
  });
  gameBus.on(GameEvents.DEBATE_LINE, (payload) => {
    const { speakerId, text } = payload as { speakerId: string; text: string };
    lineReceived({ speakerId, text });
  });
  gameBus.on(GameEvents.DEBATE_COMPLETE, () => {
    debateCompleted();
  });
  gameBus.on(GameEvents.OPTIONS, (payload) => {
    optionsReceived((payload as { options: OptionCard[] }).options);
  });
  gameBus.on(GameEvents.WAR_ROOM, (payload) => {
    warRoomReceived(payload as WarRoomPayload);
  });
  gameBus.on(GameEvents.BOARD_VOTE, (payload) => {
    boardVoteReceived(payload as BoardVotePayload);
  });

  subscribe(syncOutbound);
  syncOutbound();
}

function syncOutbound(): void {
  const s = getState();
  const active = s.debates.find((d) => d.key === s.activeKey);
  const line = active && active.cursor >= 0 ? active.lines[active.cursor] : undefined;
  if (line && active) {
    const sig = `${active.key}:${line.index}`;
    if (sig !== lastShownSig) {
      lastShownSig = sig;
      gameBus.emit(GameEvents.LINE_SHOWN, { speakerId: line.speakerId, text: line.text });
    }
  }

  if (
    active?.proceeded &&
    !s.pendingOptions &&
    !s.boardVote &&
    (s.serverPhase === 'EXPLORE' || s.serverPhase === 'GAME_END')
  ) {
    if (dismissedKey !== active.key) {
      dismissedKey = active.key;
      gameBus.emit(GameEvents.DEBATE_DISMISSED);
    }
  }
}
