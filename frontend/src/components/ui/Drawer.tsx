"use client";

import { ReactNode, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";

interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: ReactNode;
}

/**
 * Document 12 §Drawers: desktop slides from the right, phone slides up as a
 * bottom sheet. Used today for the mobile bottom-nav "More" menu; reusable
 * anywhere else a drawer is needed.
 */
export function Drawer({ open, onClose, title, children }: DrawerProps) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  if (!mounted || !open) return null;

  return createPortal(
    <div className="fixed inset-0 z-[90]">
      <div
        className="absolute inset-0 animate-fade-in bg-text/20"
        onClick={onClose}
        aria-hidden="true"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="animate-slide-up absolute inset-x-0 bottom-0 max-h-[80vh] overflow-y-auto rounded-t-xl border-t border-border bg-surface p-6 shadow-3 md:animate-slide-in-right md:inset-y-0 md:left-auto md:right-0 md:h-full md:max-h-none md:w-[360px] md:rounded-l-xl md:rounded-t-none"
      >
        <div className="mb-4 flex items-center justify-between">
          {title && <p className="text-card-heading font-serif font-medium text-text">{title}</p>}
          <button
            onClick={onClose}
            aria-label="Close"
            className="ml-auto flex h-9 w-9 items-center justify-center rounded-full text-muted hover:bg-surface-hover hover:text-text"
          >
            <X size={18} aria-hidden="true" />
          </button>
        </div>
        {children}
      </div>
    </div>,
    document.body
  );
}
