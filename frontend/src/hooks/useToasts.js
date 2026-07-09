import { useCallback, useRef, useState } from "react";

// Lightweight ephemeral notification queue. Not a global/context-based
// system -- each screen that wants toasts calls this hook locally and
// renders <ToastStack toasts={toasts} onDismiss={dismissToast} />,
// same per-feature-hook approach as useSale/useHeldSales/etc. rather
// than a new app-wide provider for what's currently a single screen's
// need.
let nextId = 0;

export function useToasts(duration = 4000) {
  const [toasts, setToasts] = useState([]);
  const timers = useRef(new Map());

  const dismissToast = useCallback((id) => {
    setToasts((current) => current.filter((t) => t.id !== id));
    const timer = timers.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timers.current.delete(id);
    }
  }, []);

  const showToast = useCallback(
    (type, message) => {
      const id = nextId++;
      setToasts((current) => [...current, { id, type, message }]);
      const timer = setTimeout(() => dismissToast(id), duration);
      timers.current.set(id, timer);
    },
    [dismissToast, duration],
  );

  return { toasts, showToast, dismissToast };
}
