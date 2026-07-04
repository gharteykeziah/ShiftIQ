"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";

export function FaqItem({ question, answer }: { question: string; answer: string }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="border-b border-border">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-4 py-5 text-left"
      >
        <span className="text-body-lg text-text">{question}</span>
        <ChevronDown
          size={20}
          strokeWidth={2}
          className={`shrink-0 text-muted transition-transform duration-200 ${open ? "rotate-180" : ""}`}
          aria-hidden="true"
        />
      </button>
      {open && <p className="animate-fade-up max-w-reading pb-6 text-sm text-muted">{answer}</p>}
    </div>
  );
}
