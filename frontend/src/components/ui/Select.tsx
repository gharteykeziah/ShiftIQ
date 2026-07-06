"use client";

import { SelectHTMLAttributes, forwardRef, useId } from "react";
import { cn } from "@/lib/utils";

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
  hint?: string;
}

/**
 * Same label/hint/error API as <Input>, for the styled <select> markup that
 * was copy-pasted identically across the Jobs (frequency), Expenses
 * (frequency), Shifts (category, day), and Import Schedule (category) forms.
 */
export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, label, error, hint, id, children, ...props }, ref) => {
    const autoId = useId();
    const selectId = id ?? autoId;
    return (
      <div className="w-full">
        {label && (
          <label htmlFor={selectId} className="mb-1.5 block text-sm font-medium text-text">
            {label}
          </label>
        )}
        <select
          ref={ref}
          id={selectId}
          className={cn(
            "w-full rounded-2xl border border-border bg-white px-4 py-3 text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/40",
            error && "ring-2 ring-danger/50",
            className
          )}
          {...props}
        >
          {children}
        </select>
        {error ? (
          <p className="mt-1.5 text-xs text-danger">{error}</p>
        ) : hint ? (
          <p className="mt-1.5 text-xs text-muted">{hint}</p>
        ) : null}
      </div>
    );
  }
);
Select.displayName = "Select";
