"use client";

import { InputHTMLAttributes, forwardRef, useId } from "react";
import { cn } from "@/lib/utils";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, hint, id, ...props }, ref) => {
    const autoId = useId();
    const inputId = id ?? autoId;
    return (
      <div className="w-full">
        {label && (
          <label htmlFor={inputId} className="mb-1.5 block text-sm font-medium text-text">
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          className={cn(
            "w-full rounded-2xl border-0 bg-bg px-4 py-3 text-sm text-text placeholder:text-muted",
            "focus:outline-none focus:ring-2 focus:ring-accent/40",
            error && "ring-2 ring-danger/50",
            className
          )}
          {...props}
        />
        {error ? (
          <p className="mt-1.5 text-xs text-danger">{error}</p>
        ) : hint ? (
          <p className="mt-1.5 text-xs text-muted">{hint}</p>
        ) : null}
      </div>
    );
  }
);
Input.displayName = "Input";
