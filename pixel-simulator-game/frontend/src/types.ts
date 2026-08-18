import { MERIDIAN_NPCS, NOVATECH_NPCS } from './game/officeMap';

export type ServerPhase =
  | 'EXPLORE'
  | 'BEAT_INTRO'
  | 'CONVENE'
  | 'DEBATE'
  | 'AWAIT_DECISION'
  | 'BOARD_VOTE'
  | 'APPLY'
  | 'GAME_END';

export type UiMode = 'INTRO' | 'TOUR' | 'PLAYING';

export type DebateKind = 'war_room' | 'free_roam' | 'board_motion';

export interface DebateLine {
  speakerId: string;
  text: string;
  index: number;
}

export interface DebateBlock {
  key: string; // `${beatId}#${ordinal}` — a beat can debate twice (options + motion)
  beatId: string;
  quarter: number;
  title: string;
  kind: DebateKind;
  lines: DebateLine[];
  complete: boolean;
  cursor: number;
  maxSeen: number;
  proceeded: boolean;
}

export interface VisibleLine extends DebateLine {
  blockKey: string;
}

export interface BeatInfo {
  beatId: string;
  n: number;
  title: string;
  situation: string;
  zoneId?: string;
  npcId?: string | null;
}

export interface NextBeatHint {
  beatId: string;
  n: number;
  title: string;
  zoneId: string;
  npcId?: string | null;
}

export interface OptionCard {
  id: string;
  label: string;
  pros: string[];
  cons: string[];
}

export interface Dissent {
  seatId: string;
  name: string;
  preferredLabel: string;
  concern: string;
}

export interface WarRoomPayload {
  quarter: number;
  recommendedCardId: string;
  recommendedLabel: string;
  tally: Record<string, number>;
  confidence: string;
  dissents: Dissent[];
}

export interface VoteRow {
  speakerId: string;
  name: string;
  optionId: string;
  label: string;
}

export interface BoardVotePayload {
  motionId: string;
  motionLabel: string;
  votes: VoteRow[];
  winningOptionId: string;
  winningLabel: string;
  tieBrokenBy?: string;
}

export interface SessionInfo {
  sessionId: string;
  seed: number;
}

export const SPEAKER_NAMES: Record<string, string> = {
  ceo: 'CEO',
  cfo: 'CFO',
  gc: 'Counsel',
  chair: 'Chair',
  analyst: 'Analyst',
  partner: 'Partner',
  operator: 'Operating Partner',
  cto: 'CTO',
  hr: 'Talent / HR',
  comms: 'Comms',
};

export const SPEAKER_COLORS: Record<string, string> = Object.fromEntries(
  [...NOVATECH_NPCS, ...MERIDIAN_NPCS].map((npc) => [npc.id, npc.palette.shirt]),
);
