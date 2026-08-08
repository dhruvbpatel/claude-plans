import { useEffect, useState } from 'react';
import { GameEvents, gameBus } from '../game/eventBus';

interface Prompt {
  targetId: string;
  label: string;
}

/** Shows "E — Talk to CEO" etc. while an interact target is in range. */
export function InteractPrompt() {
  const [prompt, setPrompt] = useState<Prompt | null>(null);

  useEffect(() => gameBus.on(GameEvents.PROMPT, (p) => setPrompt(p as Prompt | null)), []);

  if (!prompt) return null;
  return (
    <div className="interact-prompt" role="status">
      <kbd>E</kbd>
      <span>{prompt.label}</span>
    </div>
  );
}
