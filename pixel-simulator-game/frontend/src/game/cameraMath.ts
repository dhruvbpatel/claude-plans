/** Must match `officeMap` MAP_W/H and `textures` TILE. */
const TILE = 16;
const WORLD_W = 60 * TILE;
const WORLD_H = 40 * TILE;

export interface TileRect {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

export interface ViewSize {
  w: number;
  h: number;
}

/** Integer zoom ≥2 that never exposes past world bounds (kills fractional shimmer). */
export function exploreZoom(viewW: number, viewH: number): number {
  if (viewW <= 0 || viewH <= 0) return 2;
  const minZ = Math.max(viewW / WORLD_W, viewH / WORLD_H, 2);
  return Math.ceil(minZ - 1e-9);
}

/** Zoom to fit a tile rect in the view; clamped [1.25, 4] and snapped to 0.25. */
export function fitRectZoom(rect: TileRect, view: ViewSize, pad = 16): number {
  if (view.w <= 0 || view.h <= 0) return 1.25;
  const rw = (rect.x1 - rect.x0 + 1) * TILE + pad * 2;
  const rh = (rect.y1 - rect.y0 + 1) * TILE + pad * 2;
  if (rw <= 0 || rh <= 0) return 1.25;
  const z = Math.min(view.w / rw, view.h / rh);
  const clamped = Math.min(4, Math.max(1.25, z));
  return Math.round(clamped * 4) / 4;
}

export function rectCenterPx(rect: TileRect): { x: number; y: number } {
  return {
    x: ((rect.x0 + rect.x1 + 1) / 2) * TILE,
    y: ((rect.y0 + rect.y1 + 1) / 2) * TILE,
  };
}
