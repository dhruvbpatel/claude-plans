import { TILES, type CharPalette } from './textures';

/**
 * NovaTech HQ layout, in tile coordinates (16px tiles).
 * World: 60 x 40 tiles = 960 x 640 px.
 * Meridian ids remain so `?scenario=meridian-activist-01` still maps.
 */

export const MAP_W = 60;
export const MAP_H = 40;

export interface RoomDef {
  id: string;
  label: string;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  floor: number;
  doors: { x: number; y: number }[];
}

export const ROOMS: RoomDef[] = [
  {
    id: 'war_room', label: 'Strategy Room',
    x0: 0, y0: 0, x1: 14, y1: 11, floor: TILES.WAR,
    doors: [{ x: 8, y: 11 }, { x: 9, y: 11 }],
  },
  {
    id: 'boardroom', label: 'War Room',
    x0: 14, y0: 0, x1: 45, y1: 11, floor: TILES.BOARD,
    doors: [{ x: 29, y: 11 }, { x: 30, y: 11 }],
  },
  {
    id: 'ceo_office', label: 'Research',
    x0: 45, y0: 0, x1: 59, y1: 11, floor: TILES.CEO,
    doors: [{ x: 50, y: 11 }, { x: 51, y: 11 }],
  },
  {
    id: 'trading_floor', label: 'Trading Floor',
    x0: 0, y0: 14, x1: 24, y1: 27, floor: TILES.TRADING,
    doors: [{ x: 11, y: 14 }, { x: 12, y: 14 }, { x: 24, y: 20 }, { x: 24, y: 21 }],
  },
  {
    id: 'cfo_office', label: 'Capital Markets',
    x0: 41, y0: 14, x1: 59, y1: 21, floor: TILES.CFO,
    doors: [{ x: 41, y: 17 }, { x: 41, y: 18 }],
  },
  {
    id: 'gc_office', label: 'Counsel',
    x0: 41, y0: 21, x1: 59, y1: 28, floor: TILES.GC,
    doors: [{ x: 41, y: 24 }, { x: 41, y: 25 }],
  },
  {
    id: 'press_bay', label: 'Press Bay',
    x0: 0, y0: 28, x1: 24, y1: 39, floor: TILES.PRESS,
    doors: [{ x: 24, y: 32 }, { x: 24, y: 33 }],
  },
  {
    id: 'lobby', label: 'Lobby',
    x0: 24, y0: 28, x1: 41, y1: 39, floor: TILES.LOBBY,
    doors: [
      { x: 30, y: 28 }, { x: 31, y: 28 }, { x: 32, y: 28 }, { x: 33, y: 28 },
      { x: 41, y: 33 }, { x: 41, y: 34 },
    ],
  },
];

export function buildGrid(): number[][] {
  const grid: number[][] = Array.from({ length: MAP_H }, () =>
    Array<number>(MAP_W).fill(TILES.HALL),
  );
  for (const room of ROOMS) {
    for (let y = room.y0; y <= room.y1; y++) {
      for (let x = room.x0; x <= room.x1; x++) {
        const edge = x === room.x0 || x === room.x1 || y === room.y0 || y === room.y1;
        grid[y][x] = edge ? TILES.WALL : room.floor;
      }
    }
  }
  // Doors punched after all perimeters so shared walls stay open.
  for (const room of ROOMS) {
    for (const door of room.doors) grid[door.y][door.x] = room.floor;
  }
  for (let x = 0; x < MAP_W; x++) {
    grid[0][x] = TILES.WALL;
    grid[MAP_H - 1][x] = TILES.WALL;
  }
  for (let y = 0; y < MAP_H; y++) {
    grid[y][0] = TILES.WALL;
    grid[y][MAP_W - 1] = TILES.WALL;
  }
  return grid;
}

// --- Zone interact pads (tile rects), IDs per SPEC §7 -----------------------

export interface ZoneDef {
  id: string;
  label: string;
  x: number;
  y: number;
  w: number;
  h: number;
}

export const ZONES: ZoneDef[] = [
  { id: 'lobby', label: 'Lobby', x: 31, y: 33, w: 2, h: 2 },
  { id: 'trading_floor', label: 'Trading Floor', x: 7, y: 19, w: 2, h: 2 },
  { id: 'war_room', label: 'War Room', x: 3, y: 6, w: 2, h: 2 },
  { id: 'ceo_office', label: 'CEO Office', x: 46, y: 6, w: 2, h: 2 },
  { id: 'cfo_office', label: 'CFO Office', x: 45, y: 17, w: 2, h: 2 },
  { id: 'gc_office', label: 'GC Office', x: 45, y: 25, w: 2, h: 2 },
  { id: 'boardroom', label: 'Boardroom', x: 28, y: 9, w: 2, h: 2 },
  { id: 'press_bay', label: 'Press Bay', x: 17, y: 31, w: 2, h: 2 },
];

// --- NPCs, IDs per SPEC §7 ---------------------------------------------------

export interface NpcDef {
  id: string;
  name: string;
  spawn: { x: number; y: number };
  wander: { x0: number; y0: number; x1: number; y1: number };
  palette: CharPalette;
}

export const PLAYER_PALETTE: CharPalette = {
  skin: '#e8b98a', hair: '#2e2a26', shirt: '#2f6db5', pants: '#26314a',
};

export const PLAYER_SPAWN = { x: 32, y: 36 };

const CEO: NpcDef = {
  id: 'ceo', name: 'CEO', spawn: { x: 50, y: 6 },
  wander: { x0: 46, y0: 3, x1: 57, y1: 9 },
  palette: { skin: '#f0c8a0', hair: '#9aa0a8', shirt: '#3a3f4a', pants: '#2b2f38' },
};
const CFO: NpcDef = {
  id: 'cfo', name: 'CFO', spawn: { x: 50, y: 18 },
  wander: { x0: 43, y0: 16, x1: 57, y1: 19 },
  palette: { skin: '#c98a5e', hair: '#4a3324', shirt: '#274768', pants: '#1e2c40' },
};
const GC: NpcDef = {
  id: 'gc', name: 'General Counsel', spawn: { x: 51, y: 26 },
  wander: { x0: 43, y0: 23, x1: 57, y1: 26 },
  palette: { skin: '#e8b98a', hair: '#1f1b18', shirt: '#6b2f3a', pants: '#33222a' },
};
const CHAIR: NpcDef = {
  id: 'chair', name: 'Chair', spawn: { x: 30, y: 9 },
  wander: { x0: 19, y0: 7, x1: 40, y1: 10 },
  palette: { skin: '#f0c8a0', hair: '#e8e4dc', shirt: '#4a5d3a', pants: '#3a3328' },
};
const ANALYST: NpcDef = {
  id: 'analyst', name: 'Analyst', spawn: { x: 13, y: 20 },
  wander: { x0: 2, y0: 16, x1: 21, y1: 25 },
  palette: { skin: '#b97a50', hair: '#2a241f', shirt: '#2f8f7a', pants: '#3d4450' },
};
const PARTNER: NpcDef = {
  id: 'partner', name: 'Activist Partner', spawn: { x: 7, y: 8 },
  wander: { x0: 2, y0: 3, x1: 13, y1: 9 },
  palette: { skin: '#e8b98a', hair: '#5a3a28', shirt: '#5d3a78', pants: '#2e2440' },
};
const OPERATOR: NpcDef = {
  id: 'operator', name: 'Operating Partner', spawn: { x: 9, y: 6 },
  wander: { x0: 2, y0: 3, x1: 13, y1: 9 },
  palette: { skin: '#e8b98a', hair: '#5a3a28', shirt: '#5d3a78', pants: '#2e2440' },
};
const CTO: NpcDef = {
  id: 'cto', name: 'Research / CTO', spawn: { x: 15, y: 18 },
  wander: { x0: 2, y0: 16, x1: 21, y1: 25 },
  palette: { skin: '#b97a50', hair: '#2a241f', shirt: '#2f8f7a', pants: '#3d4450' },
};
const HR: NpcDef = {
  id: 'hr', name: 'Talent / HR', spawn: { x: 52, y: 8 },
  wander: { x0: 46, y0: 3, x1: 57, y1: 9 },
  palette: { skin: '#f0c8a0', hair: '#9aa0a8', shirt: '#3a3f4a', pants: '#2b2f38' },
};
const COMMS: NpcDef = {
  id: 'comms', name: 'Communications', spawn: { x: 10, y: 32 },
  wander: { x0: 2, y0: 30, x1: 20, y1: 37 },
  palette: { skin: '#e8b98a', hair: '#3a2a20', shirt: '#8a5a28', pants: '#2a2420' },
};

/** NovaTech war-room debate seats (scenario npcs + chair). */
export const NOVATECH_NPCS: NpcDef[] = [CFO, GC, CHAIR, OPERATOR, CTO, HR, COMMS];
/** Meridian boardroom + office cast. */
export const MERIDIAN_NPCS: NpcDef[] = [CEO, CFO, GC, CHAIR, ANALYST, PARTNER];

export function npcsForScenario(scenarioId: string): NpcDef[] {
  return scenarioId.includes('meridian') ? MERIDIAN_NPCS : NOVATECH_NPCS;
}

/** Default = NovaTech debate cast. OfficeScene may swap via npcsForScenario. */
export const NPCS: NpcDef[] = NOVATECH_NPCS;

// --- Furniture (tile coords of top-left corner) ------------------------------

export interface FurnitureDef {
  texture: string;
  x: number;
  y: number;
  solid: boolean;
}

export const FURNITURE: FurnitureDef[] = [
  // Boardroom — table sits mid-room so north-row bubbles have headroom
  { texture: 'board_table', x: 22, y: 6, solid: true },
  { texture: 'chair', x: 24, y: 4, solid: false },
  { texture: 'chair', x: 29, y: 4, solid: false },
  { texture: 'chair', x: 34, y: 4, solid: false },
  { texture: 'chair', x: 24, y: 8, solid: false },
  { texture: 'chair', x: 29, y: 8, solid: false },
  { texture: 'chair', x: 34, y: 8, solid: false },
  { texture: 'chair', x: 36, y: 6, solid: false },
  { texture: 'chair', x: 36, y: 8, solid: false },
  { texture: 'plant', x: 18, y: 1, solid: false },
  { texture: 'plant', x: 41, y: 9, solid: false },
  // CEO office
  { texture: 'desk', x: 48, y: 4, solid: true },
  { texture: 'chair', x: 49, y: 3, solid: false },
  { texture: 'shelf', x: 54, y: 1, solid: true },
  { texture: 'sofa', x: 46, y: 8, solid: true },
  { texture: 'plant', x: 57, y: 1, solid: false },
  // CFO office
  { texture: 'desk', x: 48, y: 16, solid: true },
  { texture: 'chair', x: 49, y: 15, solid: false },
  { texture: 'cabinet', x: 56, y: 15, solid: true },
  { texture: 'plant', x: 43, y: 19, solid: false },
  // GC office
  { texture: 'desk', x: 48, y: 24, solid: true },
  { texture: 'chair', x: 49, y: 23, solid: false },
  { texture: 'shelf', x: 43, y: 22, solid: true },
  { texture: 'plant', x: 57, y: 26, solid: false },
  // Trading floor
  { texture: 'desk', x: 4, y: 17, solid: true },
  { texture: 'desk', x: 10, y: 17, solid: true },
  { texture: 'desk', x: 16, y: 17, solid: true },
  { texture: 'desk', x: 4, y: 21, solid: true },
  { texture: 'desk', x: 10, y: 21, solid: true },
  { texture: 'desk', x: 16, y: 21, solid: true },
  { texture: 'cooler', x: 22, y: 15, solid: true },
  { texture: 'plant', x: 1, y: 15, solid: false },
  // War room
  { texture: 'screen', x: 5, y: 1, solid: true },
  { texture: 'table', x: 6, y: 5, solid: true },
  { texture: 'chair', x: 6, y: 4, solid: false },
  { texture: 'chair', x: 8, y: 4, solid: false },
  { texture: 'chair', x: 6, y: 7, solid: false },
  { texture: 'chair', x: 8, y: 7, solid: false },
  { texture: 'plant', x: 12, y: 1, solid: false },
  // Press bay
  { texture: 'podium', x: 12, y: 30, solid: true },
  { texture: 'chair', x: 5, y: 33, solid: false },
  { texture: 'chair', x: 8, y: 33, solid: false },
  { texture: 'chair', x: 11, y: 33, solid: false },
  { texture: 'chair', x: 14, y: 33, solid: false },
  { texture: 'chair', x: 5, y: 36, solid: false },
  { texture: 'chair', x: 8, y: 36, solid: false },
  { texture: 'chair', x: 11, y: 36, solid: false },
  { texture: 'chair', x: 14, y: 36, solid: false },
  { texture: 'plant', x: 1, y: 29, solid: false },
  { texture: 'plant', x: 22, y: 29, solid: false },
  // Lobby
  { texture: 'reception', x: 34, y: 30, solid: true },
  { texture: 'sofa', x: 26, y: 35, solid: true },
  { texture: 'plant', x: 25, y: 29, solid: false },
  { texture: 'plant', x: 39, y: 36, solid: false },
  // Lounge (unnamed bottom-right area)
  { texture: 'sofa', x: 46, y: 31, solid: true },
  { texture: 'cooler', x: 43, y: 29, solid: true },
  { texture: 'plant', x: 57, y: 29, solid: false },
];

export type Face = 'down' | 'left' | 'right' | 'up';

export interface SeatDef {
  x: number;
  y: number;
  face: Face;
}

/** Unique stand/sit tiles around the board table. */
export const BOARD_SEATS: Record<string, SeatDef> = {
  chair: { x: 36, y: 6, face: 'left' },
  ceo: { x: 24, y: 4, face: 'down' },
  cfo: { x: 29, y: 4, face: 'down' },
  gc: { x: 34, y: 4, face: 'down' },
  analyst: { x: 24, y: 8, face: 'up' },
  partner: { x: 29, y: 8, face: 'up' },
  hr: { x: 24, y: 8, face: 'up' },
  operator: { x: 29, y: 8, face: 'up' },
  cto: { x: 24, y: 4, face: 'down' },
  comms: { x: 36, y: 8, face: 'left' },
};

export const PLAYER_GALLERY: SeatDef = { x: 34, y: 8, face: 'up' };

/** Table-center tile the camera holds on during a meeting. */
export const BOARD_CAMERA = { x: 29, y: 6 };
