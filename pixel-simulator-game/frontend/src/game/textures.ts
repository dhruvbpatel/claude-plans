import Phaser from 'phaser';

/**
 * All art is generated at runtime on canvases (16px pixel-art tiles/sprites,
 * rendered at camera zoom 2). No downloaded assets — zero licensing concerns.
 */

export const TILE = 16;

export const TILES = {
  HALL: 0,
  WALL: 1,
  LOBBY: 2,
  TRADING: 3,
  WAR: 4,
  CEO: 5,
  CFO: 6,
  GC: 7,
  BOARD: 8,
  PRESS: 9,
} as const;

type Ctx = CanvasRenderingContext2D;

function rect(ctx: Ctx, x: number, y: number, w: number, h: number, color: string): void {
  ctx.fillStyle = color;
  ctx.fillRect(x, y, w, h);
}

interface FloorStyle {
  base: string;
  line: string;
  fleck: string;
}

const FLOORS: Record<number, FloorStyle> = {
  [TILES.HALL]: { base: '#9aa1af', line: '#8b92a1', fleck: '#a7aebb' },
  [TILES.LOBBY]: { base: '#c2a878', line: '#b39a6c', fleck: '#cfb689' },
  [TILES.TRADING]: { base: '#7f96b2', line: '#7289a5', fleck: '#8ca3bf' },
  [TILES.WAR]: { base: '#5d6b7e', line: '#536071', fleck: '#69788c' },
  [TILES.CEO]: { base: '#a0724d', line: '#916545', fleck: '#ad7f58' },
  [TILES.CFO]: { base: '#7ba190', line: '#6e9382', fleck: '#88ae9d' },
  [TILES.GC]: { base: '#a08298', line: '#92758a', fleck: '#ad8fa5' },
  [TILES.BOARD]: { base: '#9c5a5a', line: '#8d4f4f', fleck: '#a96666' },
  [TILES.PRESS]: { base: '#8a86ac', line: '#7c789d', fleck: '#9793b9' },
};

function drawFloorTile(ctx: Ctx, ox: number, style: FloorStyle): void {
  rect(ctx, ox, 0, TILE, TILE, style.base);
  rect(ctx, ox, TILE - 1, TILE, 1, style.line);
  rect(ctx, ox + TILE - 1, 0, 1, TILE, style.line);
  rect(ctx, ox + 3, 4, 1, 1, style.fleck);
  rect(ctx, ox + 10, 9, 1, 1, style.fleck);
  rect(ctx, ox + 6, 12, 1, 1, style.fleck);
}

function drawWallTile(ctx: Ctx, ox: number): void {
  rect(ctx, ox, 0, TILE, TILE, '#3d4763');
  rect(ctx, ox, 0, TILE, 2, '#55658a');
  rect(ctx, ox, 11, TILE, 5, '#262d40');
  rect(ctx, ox, 10, TILE, 1, '#1c2233');
}

export function createTilesetTexture(scene: Phaser.Scene): void {
  const key = 'office-tiles';
  if (scene.textures.exists(key)) return;
  const count = 10;
  const canvas = document.createElement('canvas');
  canvas.width = TILE * count;
  canvas.height = TILE;
  const ctx = canvas.getContext('2d')!;
  for (let i = 0; i < count; i++) {
    if (i === TILES.WALL) drawWallTile(ctx, i * TILE);
    else drawFloorTile(ctx, i * TILE, FLOORS[i]);
  }
  scene.textures.addCanvas(key, canvas);
}

// ---------------------------------------------------------------------------
// Characters: 8 frames of 16x16 (down0 down1 left0 left1 right0 right1 up0 up1)
// ---------------------------------------------------------------------------

export interface CharPalette {
  skin: string;
  hair: string;
  shirt: string;
  pants: string;
}

type Dir = 'down' | 'left' | 'right' | 'up';

function drawChar(ctx: Ctx, ox: number, dir: Dir, step: boolean, pal: CharPalette): void {
  const shoe = '#20242e';
  const eye = '#1b1f2a';

  if (!step) {
    rect(ctx, ox + 5, 12, 2, 3, pal.pants);
    rect(ctx, ox + 9, 12, 2, 3, pal.pants);
    rect(ctx, ox + 5, 15, 2, 1, shoe);
    rect(ctx, ox + 9, 15, 2, 1, shoe);
  } else {
    rect(ctx, ox + 4, 12, 2, 3, pal.pants);
    rect(ctx, ox + 10, 12, 2, 3, pal.pants);
    rect(ctx, ox + 4, 15, 2, 1, shoe);
    rect(ctx, ox + 10, 15, 2, 1, shoe);
  }

  rect(ctx, ox + 4, 7, 8, 5, pal.shirt);
  rect(ctx, ox + 3, 8, 1, 3, pal.shirt);
  rect(ctx, ox + 12, 8, 1, 3, pal.shirt);

  rect(ctx, ox + 5, 1, 6, 6, pal.skin);
  rect(ctx, ox + 5, 1, 6, 2, pal.hair);

  if (dir === 'up') {
    rect(ctx, ox + 5, 1, 6, 5, pal.hair);
  } else if (dir === 'down') {
    rect(ctx, ox + 6, 4, 1, 1, eye);
    rect(ctx, ox + 9, 4, 1, 1, eye);
  } else if (dir === 'left') {
    rect(ctx, ox + 9, 1, 2, 4, pal.hair);
    rect(ctx, ox + 6, 4, 1, 1, eye);
  } else {
    rect(ctx, ox + 5, 1, 2, 4, pal.hair);
    rect(ctx, ox + 9, 4, 1, 1, eye);
  }
}

export function createCharacterTexture(scene: Phaser.Scene, key: string, pal: CharPalette): void {
  if (scene.textures.exists(key)) return;
  const canvas = document.createElement('canvas');
  canvas.width = TILE * 8;
  canvas.height = TILE;
  const ctx = canvas.getContext('2d')!;
  const dirs: Dir[] = ['down', 'left', 'right', 'up'];
  dirs.forEach((dir, d) => {
    drawChar(ctx, (d * 2 + 0) * TILE, dir, false, pal);
    drawChar(ctx, (d * 2 + 1) * TILE, dir, true, pal);
  });
  const tex = scene.textures.addCanvas(key, canvas)!;
  for (let i = 0; i < 8; i++) tex.add(i, 0, i * TILE, 0, TILE, TILE);
}

// ---------------------------------------------------------------------------
// Furniture
// ---------------------------------------------------------------------------

function makeTexture(
  scene: Phaser.Scene,
  key: string,
  w: number,
  h: number,
  draw: (ctx: Ctx) => void,
): void {
  if (scene.textures.exists(key)) return;
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  draw(canvas.getContext('2d')!);
  scene.textures.addCanvas(key, canvas);
}

export function createFurnitureTextures(scene: Phaser.Scene): void {
  makeTexture(scene, 'desk', 32, 16, (ctx) => {
    rect(ctx, 0, 3, 32, 9, '#8a6642');
    rect(ctx, 0, 3, 32, 2, '#9d7850');
    rect(ctx, 0, 11, 32, 1, '#5e4229');
    rect(ctx, 1, 12, 2, 4, '#4a331f');
    rect(ctx, 29, 12, 2, 4, '#4a331f');
    rect(ctx, 11, 0, 10, 7, '#141b28');
    rect(ctx, 12, 1, 8, 5, '#173042');
    rect(ctx, 13, 4, 2, 1, '#41d98d');
    rect(ctx, 15, 3, 2, 1, '#41d98d');
    rect(ctx, 17, 2, 2, 1, '#41d98d');
  });

  makeTexture(scene, 'table', 64, 32, (ctx) => {
    rect(ctx, 2, 4, 60, 24, '#6d4c30');
    rect(ctx, 2, 4, 60, 4, '#7f5b3a');
    rect(ctx, 2, 26, 60, 2, '#503722');
    rect(ctx, 20, 12, 6, 4, '#e8e4dc');
    rect(ctx, 38, 14, 6, 4, '#e8e4dc');
  });

  makeTexture(scene, 'board_table', 224, 32, (ctx) => {
    rect(ctx, 4, 4, 216, 24, '#5d3f2a');
    rect(ctx, 4, 4, 216, 5, '#6f4c32');
    rect(ctx, 8, 14, 208, 4, '#4e3523');
    rect(ctx, 4, 26, 216, 2, '#412c1c');
    for (const px of [20, 56, 92, 128, 164, 200]) rect(ctx, px, 11, 5, 3, '#e8e4dc');
  });

  makeTexture(scene, 'chair', 16, 16, (ctx) => {
    rect(ctx, 3, 2, 10, 4, '#31405e');
    rect(ctx, 3, 6, 10, 7, '#3c4e72');
    rect(ctx, 4, 13, 2, 3, '#20242e');
    rect(ctx, 10, 13, 2, 3, '#20242e');
  });

  makeTexture(scene, 'plant', 16, 24, (ctx) => {
    rect(ctx, 4, 16, 8, 7, '#8a5a34');
    rect(ctx, 3, 15, 10, 2, '#9d6a40');
    rect(ctx, 4, 6, 8, 9, '#3f7d46');
    rect(ctx, 2, 8, 4, 5, '#356b3c');
    rect(ctx, 10, 8, 4, 5, '#356b3c');
    rect(ctx, 6, 2, 4, 6, '#4f975a');
    rect(ctx, 5, 5, 2, 2, '#4f975a');
    rect(ctx, 9, 5, 2, 2, '#4f975a');
  });

  makeTexture(scene, 'screen', 96, 16, (ctx) => {
    rect(ctx, 0, 0, 96, 16, '#10151f');
    rect(ctx, 2, 2, 92, 12, '#0a1420');
    rect(ctx, 4, 12, 88, 1, '#26557a');
    const ys = [10, 9, 10, 8, 7, 8, 6, 5, 6, 4, 5, 3];
    ys.forEach((y, i) => rect(ctx, 6 + i * 7, y, 7, 1, '#41d98d'));
  });

  makeTexture(scene, 'reception', 96, 24, (ctx) => {
    rect(ctx, 0, 8, 96, 14, '#7a5a3c');
    rect(ctx, 0, 4, 96, 6, '#95714c');
    rect(ctx, 0, 20, 96, 2, '#5d4229');
    rect(ctx, 40, 0, 12, 6, '#141b28');
    rect(ctx, 41, 1, 10, 4, '#2f8f7a');
  });

  makeTexture(scene, 'podium', 16, 24, (ctx) => {
    rect(ctx, 6, 10, 4, 12, '#6d4c30');
    rect(ctx, 2, 4, 12, 6, '#7f5b3a');
    rect(ctx, 2, 4, 12, 2, '#8f6845');
    rect(ctx, 7, 1, 2, 3, '#20242e');
  });

  makeTexture(scene, 'sofa', 48, 16, (ctx) => {
    rect(ctx, 2, 2, 44, 5, '#3a4c75');
    rect(ctx, 2, 6, 44, 9, '#455a8a');
    rect(ctx, 0, 4, 4, 11, '#324066');
    rect(ctx, 44, 4, 4, 11, '#324066');
    rect(ctx, 4, 14, 2, 2, '#20242e');
    rect(ctx, 42, 14, 2, 2, '#20242e');
  });

  makeTexture(scene, 'cabinet', 16, 24, (ctx) => {
    rect(ctx, 2, 2, 12, 21, '#7c8494');
    rect(ctx, 2, 8, 12, 1, '#5c6472');
    rect(ctx, 2, 15, 12, 1, '#5c6472');
    rect(ctx, 7, 5, 2, 1, '#3c4450');
    rect(ctx, 7, 11, 2, 1, '#3c4450');
    rect(ctx, 7, 18, 2, 1, '#3c4450');
  });

  makeTexture(scene, 'shelf', 32, 24, (ctx) => {
    rect(ctx, 0, 0, 32, 24, '#5d4229');
    rect(ctx, 2, 2, 28, 9, '#3f2d1c');
    rect(ctx, 2, 13, 28, 9, '#3f2d1c');
    const books = ['#9c5a5a', '#4f975a', '#31405e', '#c2a878', '#6b2f3a', '#2f8f7a'];
    books.forEach((c, i) => rect(ctx, 3 + i * 4, 4, 3, 7, c));
    books.forEach((c, i) => rect(ctx, 3 + i * 4, 15, 3, 7, books[books.length - 1 - i] ?? c));
  });

  makeTexture(scene, 'cooler', 16, 24, (ctx) => {
    rect(ctx, 4, 12, 8, 10, '#aab4c2');
    rect(ctx, 5, 3, 6, 9, '#7fc4e8');
    rect(ctx, 6, 4, 2, 6, '#a5daf2');
    rect(ctx, 4, 21, 8, 1, '#7c8494');
  });
}
