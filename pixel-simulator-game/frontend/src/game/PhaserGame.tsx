import { useEffect, useRef } from 'react';
import Phaser from 'phaser';
import { GameEvents, gameBus } from './eventBus';
import { OfficeScene } from './OfficeScene';

const config: Phaser.Types.Core.GameConfig = {
  type: Phaser.AUTO,
  parent: undefined,
  width: 800,
  height: 480,
  backgroundColor: '#1a2332',
  pixelArt: true,
  roundPixels: true,
  scene: [OfficeScene],
  physics: {
    default: 'arcade',
    arcade: { debug: false },
  },
  scale: {
    mode: Phaser.Scale.FIT,
    autoCenter: Phaser.Scale.CENTER_BOTH,
  },
};

export function PhaserGame() {
  const hostRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!hostRef.current) return;
    const game = new Phaser.Game({ ...config, parent: hostRef.current });
    const focusCanvas = () => {
      const canvas = game.canvas as HTMLCanvasElement | undefined;
      if (!canvas) return;
      canvas.tabIndex = 0;
      canvas.focus({ preventScroll: true });
    };
    // Option cards are HTML buttons; clicking one steals keys from Phaser.
    const unsub = gameBus.on(GameEvents.PHASE, (payload) => {
      const { phase } = payload as { phase: string };
      if (phase === 'EXPLORE' || phase === 'GAME_END') focusCanvas();
    });
    game.events.once(Phaser.Core.Events.READY, focusCanvas);
    return () => {
      unsub();
      game.destroy(true);
    };
  }, []);

  return <div ref={hostRef} className="phaser-host" aria-label="Office canvas" />;
}
