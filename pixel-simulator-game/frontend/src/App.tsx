import { useEffect } from 'react';
import { PhaserGame } from './game/PhaserGame';
import { GameEvents, gameBus } from './game/eventBus';
import { startSession } from './net/session';
import {
  getState,
  readingActive,
  setTourActive,
  setTranscriptOpen,
  useGame,
} from './state/store';
import { wireStore } from './state/wireBus';
import { BottomDock } from './ui/BottomDock';
import { GuidedTour } from './ui/GuidedTour';
import { InteractPrompt } from './ui/InteractPrompt';
import { IntroBanner } from './ui/IntroBanner';
import { NewsTicker } from './ui/NewsTicker';
import { Scorecard } from './ui/Scorecard';
import { SidePanel } from './ui/SidePanel';
import { ToastLog } from './ui/ToastLog';
import { TranscriptDrawer } from './ui/TranscriptDrawer';
import './App.css';

function App() {
  const uiMode = useGame((s) => s.uiMode);
  const tourActive = useGame((s) => s.tourActive);
  const canHelp = useGame(
    (s) => s.serverPhase === 'EXPLORE' && !readingActive(s) && s.uiMode === 'PLAYING',
  );
  const touring = uiMode === 'TOUR' || tourActive;

  useEffect(() => {
    wireStore();
  }, []);

  useEffect(() => {
    if (uiMode === 'PLAYING') startSession();
  }, [uiMode]);

  useEffect(() => {
    const locked = uiMode !== 'PLAYING' || tourActive;
    gameBus.emit(GameEvents.INPUT_LOCK, { locked });
  }, [uiMode, tourActive]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 't' || e.key === 'T') {
        if (e.repeat) return;
        if (uiMode !== 'PLAYING') return;
        e.preventDefault();
        setTranscriptOpen(!getState().transcriptOpen);
      } else if (e.key === 'Escape') {
        setTranscriptOpen(false);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [uiMode]);

  return (
    <div className="app">
      <header className="hud">
        <div>
          <h1>Activist Pixel Sim</h1>
          <p className="hud-sub">
            NovaTech HQ — WASD / arrows to walk, <kbd>E</kbd> to interact
          </p>
        </div>
        <div className="hud-actions">
          <button
            type="button"
            className="hud-btn"
            disabled={!canHelp}
            onClick={() => setTourActive(true)}
            title="Replay office tour"
          >
            ?
          </button>
          <button
            type="button"
            className="hud-btn"
            onClick={() => setTranscriptOpen(true)}
            title="Open transcript"
          >
            T
          </button>
        </div>
      </header>
      <main className="stage">
        <PhaserGame />
        <InteractPrompt />
        <ToastLog />
        {touring && <GuidedTour />}
      </main>
      <BottomDock />
      <SidePanel />
      <NewsTicker />
      <TranscriptDrawer />
      {uiMode === 'INTRO' && <IntroBanner />}
      <Scorecard />
    </div>
  );
}

export default App;
