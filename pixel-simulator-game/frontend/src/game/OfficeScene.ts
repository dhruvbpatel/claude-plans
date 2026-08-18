import Phaser from 'phaser';
import { GameEvents, gameBus } from './eventBus';
import {
  TILE,
  TILES,
  createCharacterTexture,
  createFurnitureTextures,
  createTilesetTexture,
} from './textures';
import {
  BOARD_SEATS,
  BOARD_VIEW,
  FURNITURE,
  MAP_H,
  MAP_W,
  PLAYER_GALLERY,
  PLAYER_PALETTE,
  PLAYER_SPAWN,
  ROOMS,
  ZONES,
  buildGrid,
  npcsForScenario,
  type NpcDef,
  type ZoneDef,
} from './officeMap';
import { exploreZoom, fitRectZoom, rectCenterPx } from './cameraMath';
import { scenarioIdFromUrl } from '../net/session';

const PLAYER_SPEED = 130;
const NPC_SPEED = 50;
const NPC_INTERACT_RADIUS = 42;
const MEETING_STUCK_MS = 1000;
const CAMERA_PAN_MS = 700;
const TOUR_MS = 600;
const NPC_TOUR_ZOOM = 3;

type Dir = 'down' | 'left' | 'right' | 'up';
const DIRS: Dir[] = ['down', 'left', 'right', 'up'];
const DIR_FRAME: Record<Dir, number> = { down: 0, left: 2, right: 4, up: 6 };

interface InteractTarget {
  targetId: string;
  label: string;
}

interface NpcActor {
  id: string;
  sprite: Phaser.Physics.Arcade.Sprite;
  tag: Phaser.GameObjects.Text;
  wander: { x0: number; y0: number; x1: number; y1: number };
  target: Phaser.Math.Vector2 | null;
  nextMoveAt: number;
  lastX: number;
  lastY: number;
  lastProgressAt: number;
  bubble: Phaser.GameObjects.Text | null;
  bubbleUntil: number;
}

export class OfficeScene extends Phaser.Scene {
  private player!: Phaser.Physics.Arcade.Sprite;
  private cursors!: Phaser.Types.Input.Keyboard.CursorKeys;
  private wasd!: Record<'W' | 'A' | 'S' | 'D', Phaser.Input.Keyboard.Key>;
  private keyE!: Phaser.Input.Keyboard.Key;
  private npcs: NpcActor[] = [];
  private facing: Dir = 'down';
  private phaseLocked = false;
  private uiLocked = false;
  private currentTarget: InteractTarget | null = null;
  private unsubscribes: (() => void)[] = [];
  private meeting = false;
  private seated = false;
  private pendingWalkOut = false;
  private walkingHome = false;
  private touring = false;
  private playerTarget: Phaser.Math.Vector2 | null = null;
  private npcDefs: NpcDef[] = [];
  private onResize = (): void => this.applyViewport();

  constructor() {
    super('OfficeScene');
  }

  create() {
    this.npcs = [];
    this.currentTarget = null;
    this.phaseLocked = false;
    this.uiLocked = false;
    this.meeting = false;
    this.seated = false;
    this.pendingWalkOut = false;
    this.walkingHome = false;
    this.touring = false;
    this.playerTarget = null;
    this.npcDefs = npcsForScenario(scenarioIdFromUrl());

    createTilesetTexture(this);
    createFurnitureTextures(this);
    createCharacterTexture(this, 'char-player', PLAYER_PALETTE);
    for (const npc of this.npcDefs) createCharacterTexture(this, `char-${npc.id}`, npc.palette);

    // --- Tilemap -----------------------------------------------------------
    const map = this.make.tilemap({ data: buildGrid(), tileWidth: TILE, tileHeight: TILE });
    const tileset = map.addTilesetImage('office-tiles')!;
    const layer = map.createLayer(0, tileset, 0, 0)!;
    layer.setDepth(0);
    map.setCollision(TILES.WALL);

    this.drawZonePads();
    this.drawRoomLabels();
    const solids = this.placeFurniture();

    // --- Player ------------------------------------------------------------
    this.player = this.physics.add.sprite(
      PLAYER_SPAWN.x * TILE + TILE / 2,
      PLAYER_SPAWN.y * TILE + TILE / 2,
      'char-player',
      0,
    );
    (this.player.body as Phaser.Physics.Arcade.Body).setSize(10, 8).setOffset(3, 8);
    this.player.setCollideWorldBounds(true);
    this.ensureCharAnims('char-player');

    // --- NPCs ---------------------------------------------------------------
    const npcGroup = this.physics.add.group();
    for (const def of this.npcDefs) {
      const key = `char-${def.id}`;
      this.ensureCharAnims(key);
      const sprite = this.physics.add.sprite(
        def.spawn.x * TILE + TILE / 2,
        def.spawn.y * TILE + TILE / 2,
        key,
        0,
      );
      (sprite.body as Phaser.Physics.Arcade.Body).setSize(10, 8).setOffset(3, 8);
      sprite.setCollideWorldBounds(true);
      sprite.setPushable(false);
      sprite.setInteractive({ useHandCursor: true });
      sprite.on('pointerdown', () => this.tryInteractWith(def.id, def.name, sprite));
      npcGroup.add(sprite);

      const tag = this.add
        .text(sprite.x, sprite.y - 12, def.name, {
          fontFamily: 'monospace',
          fontSize: '7px',
          color: '#eef2f8',
          backgroundColor: 'rgba(13, 18, 25, 0.55)',
          padding: { x: 2, y: 1 },
          resolution: 4,
        })
        .setOrigin(0.5, 1);

      this.npcs.push({
        id: def.id,
        sprite,
        tag,
        wander: def.wander,
        target: null,
        nextMoveAt: this.time.now + Phaser.Math.Between(500, 2500),
        lastX: sprite.x,
        lastY: sprite.y,
        lastProgressAt: this.time.now,
        bubble: null,
        bubbleUntil: 0,
      });
    }

    // --- Physics colliders ---------------------------------------------------
    this.physics.world.setBounds(0, 0, MAP_W * TILE, MAP_H * TILE);
    this.physics.add.collider(this.player, layer);
    this.physics.add.collider(npcGroup, layer);
    this.physics.add.collider(this.player, solids);
    this.physics.add.collider(npcGroup, solids);
    this.physics.add.collider(this.player, npcGroup);

    // --- Camera --------------------------------------------------------------
    const cam = this.cameras.main;
    cam.setBounds(0, 0, MAP_W * TILE, MAP_H * TILE);
    cam.setZoom(exploreZoom(cam.width, cam.height));
    cam.startFollow(this.player, true, 0.12, 0.12);
    cam.fadeIn(300);
    this.scale.on(Phaser.Scale.Events.RESIZE, this.onResize);

    // --- Input ---------------------------------------------------------------
    const kb = this.input.keyboard!;
    this.cursors = kb.createCursorKeys();
    this.wasd = kb.addKeys('W,A,S,D') as OfficeScene['wasd'];
    this.keyE = kb.addKey(Phaser.Input.Keyboard.KeyCodes.E);
    this.input.on('pointerdown', () => {
      this.tryInteract();
    });

    // --- Bus: input soft-lock + debate speech bubbles (SPEC §6) --------------
    this.unsubscribes.push(
      gameBus.on(GameEvents.PHASE, (payload) => {
        const { phase } = payload as { phase: string };
        if (phase === 'EXPLORE' || phase === 'GAME_END') {
          if (this.meeting) this.pendingWalkOut = true;
          else this.phaseLocked = false;
        } else {
          this.phaseLocked = true;
        }
      }),
      gameBus.on(GameEvents.INPUT_LOCK, (payload) => {
        this.uiLocked = Boolean((payload as { locked: boolean }).locked);
      }),
      gameBus.on(GameEvents.LINE_SHOWN, (payload) => {
        const { speakerId, text } = payload as { speakerId: string; text: string };
        this.showLineFor(speakerId, text);
      }),
      gameBus.on(GameEvents.DEBATE_DISMISSED, () => {
        if (this.pendingWalkOut || this.meeting) this.startWalkOut();
        else this.clearBubbles();
        this.phaseLocked = false;
        this.pendingWalkOut = false;
      }),
      gameBus.on(GameEvents.CONVENE, () => {
        this.startConvene();
      }),
      gameBus.on(GameEvents.TOUR_FOCUS, (payload) => {
        this.focusTour(payload as { kind: 'room' | 'npc'; id: string });
      }),
      gameBus.on(GameEvents.TOUR_END, () => {
        this.endTour();
      }),
    );
    const unsubAll = () => {
      this.unsubscribes.forEach((unsub) => unsub());
      this.unsubscribes = [];
      this.scale.off(Phaser.Scale.Events.RESIZE, this.onResize);
    };
    // DESTROY as well: game.destroy() (React StrictMode remount) skips SHUTDOWN.
    this.events.once(Phaser.Scenes.Events.SHUTDOWN, unsubAll);
    this.events.once(Phaser.Scenes.Events.DESTROY, unsubAll);
  }

  update(time: number) {
    this.updatePlayer();
    this.updateNpcs(time);
    this.updatePrompt();

    if (Phaser.Input.Keyboard.JustDown(this.keyE) && !(this.meeting && this.seated)) {
      this.tryInteract();
    }
  }

  private get locked(): boolean {
    return this.phaseLocked || this.uiLocked || this.meeting;
  }

  // --- Player movement -------------------------------------------------------

  private updatePlayer() {
    const body = this.player.body as Phaser.Physics.Arcade.Body;
    let vx = 0;
    let vy = 0;

    if (this.meeting && this.playerTarget && !this.seated) {
      const dist = Phaser.Math.Distance.Between(
        this.player.x, this.player.y, this.playerTarget.x, this.playerTarget.y,
      );
      if (dist < 4) {
        this.player.setPosition(this.playerTarget.x, this.playerTarget.y);
        this.playerTarget = null;
        this.facing = PLAYER_GALLERY.face;
        body.setVelocity(0, 0);
        this.player.anims.stop();
        this.player.setFrame(DIR_FRAME[this.facing]);
      } else {
        this.physics.moveTo(this.player, this.playerTarget.x, this.playerTarget.y, PLAYER_SPEED);
        this.facing = this.dirFromVelocity(body.velocity.x, body.velocity.y);
        this.player.anims.play(`char-player-walk-${this.facing}`, true);
      }
      this.player.setDepth(this.player.y + 8);
      return;
    }

    if (!this.locked) {
      if (this.cursors.left.isDown || this.wasd.A.isDown) vx -= 1;
      if (this.cursors.right.isDown || this.wasd.D.isDown) vx += 1;
      if (this.cursors.up.isDown || this.wasd.W.isDown) vy -= 1;
      if (this.cursors.down.isDown || this.wasd.S.isDown) vy += 1;
    }

    const vec = new Phaser.Math.Vector2(vx, vy);
    if (vec.lengthSq() > 0) vec.normalize().scale(PLAYER_SPEED);
    body.setVelocity(vec.x, vec.y);

    if (vec.lengthSq() > 0) {
      this.facing = this.dirFromVelocity(vec.x, vec.y);
      this.player.anims.play(`char-player-walk-${this.facing}`, true);
    } else {
      this.player.anims.stop();
      this.player.setFrame(DIR_FRAME[this.facing]);
    }
    this.player.setDepth(this.player.y + 8);
  }

  private dirFromVelocity(vx: number, vy: number): Dir {
    if (Math.abs(vx) >= Math.abs(vy)) return vx < 0 ? 'left' : 'right';
    return vy < 0 ? 'up' : 'down';
  }

  // --- NPC wander -------------------------------------------------------------

  private updateNpcs(time: number) {
    for (const npc of this.npcs) {
      const body = npc.sprite.body as Phaser.Physics.Arcade.Body;

      if (this.meeting) {
        npc.target = null;
        body.setVelocity(0, 0);
        npc.sprite.anims.stop();
        const face = BOARD_SEATS[npc.id]?.face ?? 'down';
        npc.sprite.setFrame(DIR_FRAME[face]);
      } else if (this.phaseLocked && !this.meeting && !this.walkingHome) {
        // Freeze wandering during non-boardroom debates so bubbles are easy to follow.
        npc.target = null;
        body.setVelocity(0, 0);
        npc.sprite.anims.stop();
        npc.sprite.setFrame(DIR_FRAME.down);
        npc.nextMoveAt = time + 1000;
      } else if (npc.target) {
        const dist = Phaser.Math.Distance.Between(
          npc.sprite.x, npc.sprite.y, npc.target.x, npc.target.y,
        );
        const moved = Phaser.Math.Distance.Between(
          npc.sprite.x, npc.sprite.y, npc.lastX, npc.lastY,
        );
        if (moved > 1) {
          npc.lastX = npc.sprite.x;
          npc.lastY = npc.sprite.y;
          npc.lastProgressAt = time;
        }
        const stuckMs = this.meeting || this.walkingHome ? MEETING_STUCK_MS : 900;
        const stuck = time - npc.lastProgressAt > stuckMs;

        if (dist < 4 || stuck) {
          if ((this.meeting || this.walkingHome) && npc.target) {
            npc.sprite.setPosition(npc.target.x, npc.target.y);
          }
          npc.target = null;
          body.setVelocity(0, 0);
          npc.nextMoveAt = time + Phaser.Math.Between(1200, 4200);
          npc.sprite.anims.stop();
          const face = this.meeting
            ? (BOARD_SEATS[npc.id]?.face ?? 'down')
            : 'down';
          npc.sprite.setFrame(DIR_FRAME[face]);
        } else {
          this.physics.moveTo(npc.sprite, npc.target.x, npc.target.y, NPC_SPEED);
          const dir = this.dirFromVelocity(body.velocity.x, body.velocity.y);
          npc.sprite.anims.play(`char-${npc.id}-walk-${dir}`, true);
        }
      } else if (time > npc.nextMoveAt) {
        const tx = Phaser.Math.Between(npc.wander.x0, npc.wander.x1) * TILE + TILE / 2;
        const ty = Phaser.Math.Between(npc.wander.y0, npc.wander.y1) * TILE + TILE / 2;
        npc.target = new Phaser.Math.Vector2(tx, ty);
        npc.lastProgressAt = time;
        npc.lastX = npc.sprite.x;
        npc.lastY = npc.sprite.y;
      } else {
        body.setVelocity(0, 0);
      }

      npc.sprite.setDepth(npc.sprite.y + 8);
      npc.tag.setPosition(npc.sprite.x, npc.sprite.y - 11);
      npc.tag.setDepth(npc.sprite.y + 9);

      if (npc.bubble) {
        if (Number.isFinite(npc.bubbleUntil) && time > npc.bubbleUntil) {
          npc.bubble.destroy();
          npc.bubble = null;
        } else {
          this.layoutBubble(npc.bubble, npc.sprite);
          npc.bubble.setDepth(10_000 + npc.sprite.y);
        }
      }
    }

    if (this.meeting && !this.seated) this.maybeMarkSeated();
    if (this.walkingHome && this.npcs.every((n) => !n.target)) this.walkingHome = false;
  }

  // --- Debate speech bubbles ---------------------------------------------------

  private showLineFor(speakerId: string, text: string) {
    if (!this.cameras?.main) return; // scene torn down
    const npc = this.npcs.find((n) => n.id === speakerId);
    if (!npc) return;

    for (const other of this.npcs) {
      other.bubble?.destroy();
      other.bubble = null;
    }
    npc.bubble = this.add
      .text(npc.sprite.x, npc.sprite.y - 14, text, {
        fontFamily: 'monospace',
        fontSize: '8px',
        color: '#0d1219',
        backgroundColor: '#f4f7fb',
        padding: { x: 4, y: 3 },
        wordWrap: { width: 140 },
        align: 'left',
        resolution: 4,
      })
      .setDepth(10_000 + npc.sprite.y);
    this.layoutBubble(npc.bubble, npc.sprite);
    npc.bubbleUntil = Number.POSITIVE_INFINITY;

    if (!this.meeting) {
      const cam = this.cameras.main;
      cam.stopFollow();
      cam.pan(npc.sprite.x, npc.sprite.y + 16, 280, 'Sine.easeInOut');
    }
  }

  /** Keep a speech bubble inside the current camera view; flip below if the top clips. */
  private layoutBubble(
    bubble: Phaser.GameObjects.Text,
    sprite: Phaser.GameObjects.Sprite,
  ) {
    const cam = this.cameras.main;
    const view = cam.worldView;
    const pad = 8;
    const bw = bubble.width;
    const bh = bubble.height;
    const aboveY = sprite.y - 12;
    const belowY = sprite.y + 10;
    if (aboveY - bh >= view.y + pad) {
      bubble.setOrigin(0.5, 1);
      bubble.setPosition(sprite.x, aboveY);
    } else {
      bubble.setOrigin(0.5, 0);
      bubble.setPosition(sprite.x, belowY);
    }
    const half = bw / 2;
    bubble.x = Phaser.Math.Clamp(
      bubble.x,
      view.x + pad + half,
      view.right - pad - half,
    );
    const bounds = bubble.getBounds();
    if (bounds.top < view.y + pad) bubble.y += view.y + pad - bounds.top;
    if (bounds.bottom > view.bottom - pad) {
      bubble.y -= bounds.bottom - (view.bottom - pad);
    }
  }

  private tileCenter(x: number, y: number): Phaser.Math.Vector2 {
    return new Phaser.Math.Vector2(x * TILE + TILE / 2, y * TILE + TILE / 2);
  }

  private startConvene() {
    this.meeting = true;
    this.pendingWalkOut = false;
    this.walkingHome = false;
    this.phaseLocked = true;
    this.playerTarget = null;

    // Snap onto seats. Walking them in collides with the solid table and
    // each other, so `seated` never flipped true and the player stayed locked.
    for (const npc of this.npcs) {
      const seat = BOARD_SEATS[npc.id];
      if (!seat) continue;
      npc.target = null;
      const body = npc.sprite.body as Phaser.Physics.Arcade.Body;
      body.enable = false;
      body.setVelocity(0, 0);
      const pos = this.tileCenter(seat.x, seat.y);
      npc.sprite.setPosition(pos.x, pos.y);
      npc.sprite.anims.stop();
      npc.sprite.setFrame(DIR_FRAME[seat.face]);
    }

    const gallery = this.tileCenter(PLAYER_GALLERY.x, PLAYER_GALLERY.y);
    const pbody = this.player.body as Phaser.Physics.Arcade.Body;
    pbody.setVelocity(0, 0);
    this.player.setPosition(gallery.x, gallery.y);
    this.facing = PLAYER_GALLERY.face;
    this.player.anims.stop();
    this.player.setFrame(DIR_FRAME[this.facing]);

    this.seated = true;

    const cam = this.cameras.main;
    cam.stopFollow();
    const focus = rectCenterPx(BOARD_VIEW);
    cam.pan(focus.x, focus.y, CAMERA_PAN_MS, 'Sine.easeInOut');
    cam.zoomTo(this.meetingZoom(), CAMERA_PAN_MS, 'Sine.easeInOut');
  }

  private maybeMarkSeated() {
    const playerReady = !this.playerTarget;
    const npcsReady = this.npcs.every((n) => !n.target || !BOARD_SEATS[n.id]);
    if (!playerReady || !npcsReady) return;
    this.seated = true;
    this.facing = PLAYER_GALLERY.face;
    this.player.setFrame(DIR_FRAME[this.facing]);
  }

  private startWalkOut() {
    if (!this.meeting && !this.pendingWalkOut) return;
    this.pendingWalkOut = false;
    this.meeting = false;
    this.seated = false;
    this.walkingHome = false;
    this.playerTarget = null;
    this.cameras.main.zoomTo(this.currentExploreZoom(), CAMERA_PAN_MS, 'Sine.easeInOut');
    this.clearBubbles();

    for (const npc of this.npcs) {
      const def = this.npcDefs.find((n) => n.id === npc.id);
      if (!def) continue;
      npc.target = null;
      const body = npc.sprite.body as Phaser.Physics.Arcade.Body;
      body.enable = true;
      body.setVelocity(0, 0);
      const pos = this.tileCenter(def.spawn.x, def.spawn.y);
      npc.sprite.setPosition(pos.x, pos.y);
      npc.sprite.anims.stop();
      npc.sprite.setFrame(DIR_FRAME.down);
      npc.nextMoveAt = this.time.now + Phaser.Math.Between(800, 2200);
    }
  }

  private applyViewport() {
    if (this.touring) return;
    const cam = this.cameras.main;
    if (this.meeting) {
      const focus = rectCenterPx(BOARD_VIEW);
      cam.setZoom(this.meetingZoom());
      cam.centerOn(focus.x, focus.y);
    } else {
      cam.setZoom(this.currentExploreZoom());
    }
  }

  private currentExploreZoom(): number {
    const cam = this.cameras.main;
    return exploreZoom(cam.width, cam.height);
  }

  private meetingZoom(): number {
    const cam = this.cameras.main;
    return fitRectZoom(BOARD_VIEW, { w: cam.width, h: cam.height });
  }

  private focusTour(step: { kind: 'room' | 'npc'; id: string }) {
    this.touring = true;
    const cam = this.cameras.main;
    cam.stopFollow();
    if (step.kind === 'room') {
      const room = ROOMS.find((r) => r.id === step.id);
      if (!room) return;
      const rect = { x0: room.x0, y0: room.y0, x1: room.x1, y1: room.y1 };
      const focus = rectCenterPx(rect);
      cam.pan(focus.x, focus.y, TOUR_MS, 'Sine.easeInOut');
      cam.zoomTo(fitRectZoom(rect, { w: cam.width, h: cam.height }), TOUR_MS, 'Sine.easeInOut');
      return;
    }
    const npc = this.npcs.find((n) => n.id === step.id);
    if (!npc) return;
    cam.pan(npc.sprite.x, npc.sprite.y, TOUR_MS, 'Sine.easeInOut');
    cam.zoomTo(NPC_TOUR_ZOOM, TOUR_MS, 'Sine.easeInOut');
  }

  private endTour() {
    this.touring = false;
    const cam = this.cameras.main;
    cam.startFollow(this.player, true, 0.12, 0.12);
    cam.zoomTo(this.currentExploreZoom(), TOUR_MS, 'Sine.easeInOut');
  }

  private clearBubbles() {
    if (!this.cameras?.main) return; // scene torn down
    for (const npc of this.npcs) {
      npc.bubble?.destroy();
      npc.bubble = null;
    }
    this.cameras.main.startFollow(this.player, true, 0.12, 0.12);
  }

  // --- Interact prompt + emit ---------------------------------------------------

  private findTarget(): InteractTarget | null {
    if (this.locked) return null;

    let best: { npc: NpcActor; dist: number } | null = null;
    for (const npc of this.npcs) {
      const dist = Phaser.Math.Distance.Between(
        this.player.x, this.player.y, npc.sprite.x, npc.sprite.y,
      );
      if (dist <= NPC_INTERACT_RADIUS && (!best || dist < best.dist)) {
        best = { npc, dist };
      }
    }
    if (best) {
      const def = this.npcDefs.find((n) => n.id === best!.npc.id)!;
      return { targetId: `npc:${best.npc.id}`, label: `Talk to ${def.name}` };
    }

    const zone = this.zoneAtPlayer();
    if (zone) return { targetId: `zone:${zone.id}`, label: zone.label };
    return null;
  }

  private zoneAtPlayer(): ZoneDef | null {
    const px = this.player.x;
    const py = this.player.y + 4; // bias toward feet
    for (const zone of ZONES) {
      const x0 = zone.x * TILE - 6;
      const y0 = zone.y * TILE - 6;
      const x1 = (zone.x + zone.w) * TILE + 6;
      const y1 = (zone.y + zone.h) * TILE + 6;
      if (px >= x0 && px <= x1 && py >= y0 && py <= y1) return zone;
    }
    return null;
  }

  private updatePrompt() {
    const target = this.findTarget();
    if (target?.targetId !== this.currentTarget?.targetId) {
      this.currentTarget = target;
      gameBus.emit(GameEvents.PROMPT, target);
    }
  }

  private tryInteract() {
    if (this.locked || !this.currentTarget) return;
    gameBus.emit(GameEvents.INTERACT, { targetId: this.currentTarget.targetId });
  }

  private tryInteractWith(id: string, _name: string, sprite: Phaser.GameObjects.Sprite) {
    if (this.locked) return;
    const dist = Phaser.Math.Distance.Between(this.player.x, this.player.y, sprite.x, sprite.y);
    if (dist <= NPC_INTERACT_RADIUS) {
      gameBus.emit(GameEvents.INTERACT, { targetId: `npc:${id}` });
    }
  }

  // --- World dressing -------------------------------------------------------------

  private drawZonePads() {
    const g = this.add.graphics().setDepth(1);
    for (const zone of ZONES) {
      const x = zone.x * TILE;
      const y = zone.y * TILE;
      const w = zone.w * TILE;
      const h = zone.h * TILE;
      g.fillStyle(0xffe08a, 0.16).fillRect(x, y, w, h);
      g.lineStyle(1, 0xffe08a, 0.55).strokeRect(x + 0.5, y + 0.5, w - 1, h - 1);
    }
  }

  private drawRoomLabels() {
    for (const room of ROOMS) {
      this.add
        .text((room.x0 + 1) * TILE + 2, (room.y0 + 1) * TILE + 2, room.label.toUpperCase(), {
          fontFamily: 'monospace',
          fontSize: '7px',
          color: '#0d1219',
          resolution: 4,
        })
        .setAlpha(0.55)
        .setDepth(2);
    }
  }

  private placeFurniture(): Phaser.Physics.Arcade.StaticGroup {
    const solids = this.physics.add.staticGroup();
    for (const item of FURNITURE) {
      const x = item.x * TILE;
      const y = item.y * TILE;
      if (item.solid) {
        const img = solids.create(x, y, item.texture) as Phaser.Physics.Arcade.Sprite;
        img.setOrigin(0, 0);
        img.refreshBody();
        img.setDepth(y + img.displayHeight);
      } else {
        const img = this.add.image(x, y, item.texture).setOrigin(0, 0);
        img.setDepth(y + img.displayHeight);
      }
    }
    return solids;
  }

  private ensureCharAnims(key: string) {
    DIRS.forEach((dir, i) => {
      const animKey = `${key}-walk-${dir}`;
      if (this.anims.exists(animKey)) return;
      this.anims.create({
        key: animKey,
        frames: [
          { key, frame: i * 2 },
          { key, frame: i * 2 + 1 },
        ],
        frameRate: 6,
        repeat: -1,
      });
    });
  }
}
