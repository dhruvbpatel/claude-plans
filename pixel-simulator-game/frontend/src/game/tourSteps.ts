import { npcsForScenario, ROOMS } from './officeMap';

export interface TourStep {
  kind: 'room' | 'npc';
  id: string;
  title: string;
  caption: string;
}

const ROOM_CAPTIONS: Record<string, string> = {
  lobby: 'You spawn here. Yellow pads are interact zones — walk on one and press E.',
  press_bay: 'The press bay. Headlines hit the ticker after you commit to a move.',
  trading_floor: 'Trading floor. Market color and free-roam beats often start here.',
  war_room: 'Strategy room. Your team huddles here before a vote.',
  boardroom: 'The war-room table. Debates snap everyone to seats around this board.',
  ceo_office: 'Research. Product and tech live on this wing.',
  cfo_office: 'Capital markets. Cash, debt, and the tape.',
  gc_office: 'Counsel. Legal and governance pressure shows up here.',
};

const NPC_CAPTIONS: Record<string, string> = {
  chair: 'The Chair. Runs the table and breaks ties.',
  cfo: 'CFO. Watches cash, debt, and whether the street will buy the story.',
  gc: 'General Counsel. Flags legal and governance risk.',
  operator: 'Operating Partner. Pushes the activist operating plan.',
  cto: 'Research / CTO. Owns product and the innovation metric.',
  hr: 'Talent / HR. Morale and people risk.',
  comms: 'Communications. Shapes the public narrative.',
  ceo: 'The CEO. Entrenched management — your opposite number.',
  analyst: 'The analyst. Sizes the stake and reads the tape.',
  partner: 'Your activist partner. Wants speed and a loud catalyst.',
};

const ROOM_ORDER = [
  'lobby',
  'press_bay',
  'trading_floor',
  'war_room',
  'boardroom',
  'ceo_office',
  'cfo_office',
  'gc_office',
];

export function tourStepsFor(scenarioId: string): TourStep[] {
  const rooms: TourStep[] = ROOM_ORDER.filter((id) => ROOMS.some((r) => r.id === id)).map(
    (id) => {
      const room = ROOMS.find((r) => r.id === id)!;
      return {
        kind: 'room',
        id,
        title: room.label,
        caption: ROOM_CAPTIONS[id] ?? room.label,
      };
    },
  );
  const npcs: TourStep[] = npcsForScenario(scenarioId).map((npc) => ({
    kind: 'npc' as const,
    id: npc.id,
    title: npc.name,
    caption: NPC_CAPTIONS[npc.id] ?? npc.name,
  }));
  return [...rooms, ...npcs];
}
