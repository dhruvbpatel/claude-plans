import { useEffect, useState } from 'react';
import { GameEvents, gameBus } from '../game/eventBus';

interface Toast {
  id: number;
  text: string;
}

let seq = 0;

/** News ticker toasts: consequences, curveball headlines, and interact hints. */
export function ToastLog() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  useEffect(
    () =>
      gameBus.on(GameEvents.NEWS, (payload) => {
        const { text } = payload as { text: string };
        const id = ++seq;
        setToasts((prev) => [...prev.slice(-2), { id, text }]);
        setTimeout(() => {
          setToasts((prev) => prev.filter((t) => t.id !== id));
        }, 6000);
      }),
    [],
  );

  if (toasts.length === 0) return null;
  return (
    <div className="toast-log" aria-live="polite">
      {toasts.map((toast) => (
        <div key={toast.id} className="toast">
          {toast.text}
        </div>
      ))}
    </div>
  );
}
