/** Shared Phaser ↔ React event bus (Phase 3–4). Event names: see SPEC.md §6. */
type Handler = (payload: unknown) => void;

class GameEventBus {
  private target = new EventTarget();

  on(type: string, handler: Handler): () => void {
    const listener = ((e: Event) => {
      handler((e as CustomEvent).detail);
    }) as EventListener;
    this.target.addEventListener(type, listener);
    return () => this.target.removeEventListener(type, listener);
  }

  emit(type: string, detail?: unknown): void {
    this.target.dispatchEvent(new CustomEvent(type, { detail }));
  }
}

export const gameBus = new GameEventBus();

export const GameEvents = {
  SESSION: 'game:session',
  INTERACT: 'game:interact',
  PROMPT: 'game:prompt',
  PHASE: 'game:phase',
  SPEECH: 'game:speech',
  KPI: 'game:kpi',
  OPTIONS: 'game:options',
  NEWS: 'game:news',
  END: 'game:end',
  BEAT: 'game:beat',
  NEXT_BEAT: 'game:nextBeat',
  DECIDE: 'ui:decide',
  INPUT_LOCK: 'ui:inputLock',
} as const;
