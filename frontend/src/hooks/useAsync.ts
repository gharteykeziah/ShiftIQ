"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";

interface UseAsyncResult<T> {
  data: T | null;
  isLoading: boolean;
  error: string | null;
  /** Re-run the fetcher — used for a "Try again" button and after a save/delete. */
  reload: () => Promise<void>;
}

/**
 * Runs `fetcher` once on mount and again whenever `deps` changes, tracking
 * loading/error state. This is the load/isLoading/error/useCallback/useEffect
 * block that was hand-written, identically, on the Dashboard, Jobs,
 * Expenses, Shifts, and Goals pages — the only thing that varied between
 * them was which endpoint(s) got called and what to say if it failed.
 *
 * `fetcher` should return `null` when its preconditions aren't ready yet
 * (e.g. no auth token on the very first render) instead of throwing — the
 * hook treats that as "not ready", not as an error, and simply waits for
 * `deps` to change.
 *
 * `deps` is forwarded to an internal useCallback exactly like a normal
 * dependency array would be at the call site, so the usual rules of hooks
 * apply: include every value `fetcher` closes over.
 */
export function useAsync<T>(
  fetcher: () => Promise<T> | null,
  deps: unknown[],
  errorMessage: string
): UseAsyncResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    const promise = fetcher();
    if (!promise) return Promise.resolve();
    setIsLoading(true);
    setError(null);
    return promise
      .then((result) => setData(result))
      .catch((err) => setError(err instanceof ApiError ? err.message : errorMessage))
      .finally(() => setIsLoading(false));
    // fetcher is intentionally omitted — callers pass an inline closure, so
    // `deps` (forwarded from the call site) is the real, exhaustive list.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    load();
  }, [load]);

  return { data, isLoading, error, reload: load };
}
