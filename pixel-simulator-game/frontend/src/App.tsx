import { useEffect } from 'react';
import { PhaserGame } from './game/PhaserGame';
import { startSession } from './net/session';
import { InteractPrompt } from './ui/InteractPrompt';
import { NewsTicker } from './ui/NewsTicker';
import { BoardVoteOverlay } from './ui/BoardVoteOverlay';
import { OptionCards } from './ui/OptionCards';
import { Scorecard } from './ui/Scorecard';
import { SidePanel } from './ui/SidePanel';
import { ToastLog } from './ui/ToastLog';
import './App.css';

function App() {
  useEffect(() => {
    startSession();
  }, []);

  return (
    <div className="app">
      <header className="hud">
        <h1>Activist Pixel Sim</h1>
        <p className="hud-sub">
          Meridian Dynamics HQ — WASD / arrows to walk, <kbd>E</kbd> or click to interact
        </p>
      </header>
      <main className="stage">
        <div className="stage-wrap">
          <PhaserGame />
          <InteractPrompt />
          <ToastLog />
          <OptionCards />
          <BoardVoteOverlay />
          <Scorecard />
        </div>
      </main>
      <SidePanel />
      <NewsTicker />
    </div>
  );
}

export default App;
