import { useEffect, useRef } from 'react';
import Phaser from 'phaser';
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
    return () => {
      game.destroy(true);
    };
  }, []);

  return <div ref={hostRef} className="phaser-host" aria-label="Office canvas" />;
}
