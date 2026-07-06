"use client";

import { ReactNode, createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { CheckCircle2, Info, AlertTriangle, X } from "lucide-react";

type ToastVariant = "info" | "success" | "warning";

interface ToastItem {
  id: number;
  message: string;
  variant: ToastVariant;
}

interface ToastContextValue {
  showToast: (message: string, variant?: ToastVariant) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

/** Read the nearest ToastProvider's showToast(). Must be called from a client component. */
export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within a <ToastProvider>");
  return ctx;
}

const icons: Record<ToastVariant, ReactNode> = {
  info: <Info className="h-5 w-5 text-accent" aria-hidden="true" />,
  success: <CheckCircle2 className="h-5 w-5 text-success" aria-hidden="true" />,
  warning: <AlertTriangle className="h-5 w-5 text-warning" aria-hidden="true" />,
};

/**
 * Wrap the app in this once, in the root layout. Used across ShiftIQ to
 * surface insight_engine.py output as friendly callouts (the Truebill
 * "Helen just saved $7.95/month" pattern) rather than a plain data table.
 */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  // Server and the client's first render must produce identical output, but
  // `document` only exists on the client — checking it inline during render
  // makes the client's first pass diverge from the server-rendered HTML
  // (a hydration mismatch). Delaying the portal until after mount, via this
  // effect, keeps the first client render identical to the server's.
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const showToast = useCallback((message: string, variant: ToastVariant = "info") => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, message, variant }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 3000);
  }, []);

  // showToast is already a stable reference (useCallback with no deps), but
  // wrapping it in a fresh object literal on every render still changes the
  // context value's identity — which would re-render every page that calls
  // useToast() each time the toast list itself changes (i.e. every time any
  // toast anywhere appears or auto-dismisses). Memoizing keeps the value
  // reference stable for the lifetime of the provider.
  const value = useMemo<ToastContextValue>(() => ({ showToast }), [showToast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      {mounted &&
        createPortal(
          // Doc 12: desktop bottom-right, phone top. Toasts never block interaction.
          <div className="fixed left-1/2 top-4 z-[100] flex w-full max-w-sm -translate-x-1/2 flex-col gap-2 px-4 sm:left-auto sm:right-6 sm:top-auto sm:bottom-6 sm:translate-x-0">
            {toasts.map((t) => (
              <div
                key={t.id}
                className="animate-fade-up flex items-start gap-3 rounded-md border border-border bg-surface p-4 shadow-1"
              >
                {icons[t.variant]}
                <p className="flex-1 text-sm text-text">{t.message}</p>
                <button
                  onClick={() => setToasts((prev) => prev.filter((x) => x.id !== t.id))}
                  className="text-muted hover:text-text"
                  aria-label="Dismiss"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>,
          document.body
        )}
    </ToastContext.Provider>
  );
}
