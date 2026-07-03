"use client";

import { useCallback, useEffect, useState } from "react";
import { Wallet, TrendingUp, Receipt, PiggyBank, Sparkles, Pencil } from "lucide-react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import { useAuth } from "@/context/AuthContext";
import { api, ApiError } from "@/lib/api";
import type { StateSummary, InsightsResponse, ProjectionResponse } from "@/lib/types";
import { StatCard } from "@/components/ui/StatCard";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { Input } from "@/components/ui/Input";
import { useToast } from "@/components/ui/Toast";

// Matches PROJECTION_WEEKS in config.py.
const PROJECTION_WEEK_OPTIONS = [4, 8, 12, 26, 52];

function money(n: number): string {
  return `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export default function DashboardPage() {
  const { token } = useAuth();
  const { showToast } = useToast();

  const [state, setState] = useState<StateSummary | null>(null);
  const [insights, setInsights] = useState<InsightsResponse | null>(null);
  const [projection, setProjection] = useState<ProjectionResponse | null>(null);
  const [projectionWeeks, setProjectionWeeks] = useState(12);

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [balanceModalOpen, setBalanceModalOpen] = useState(false);
  const [balanceInput, setBalanceInput] = useState("");
  const [isSavingBalance, setIsSavingBalance] = useState(false);
  const [balanceError, setBalanceError] = useState<string | null>(null);

  const loadCore = useCallback(async () => {
    if (!token) return;
    setIsLoading(true);
    setError(null);
    try {
      const [stateRes, insightsRes] = await Promise.all([api.state.get(token), api.insights(token)]);
      setState(stateRes);
      setInsights(insightsRes);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong loading your dashboard.");
    } finally {
      setIsLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadCore();
  }, [loadCore]);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    api
      .projection(token, projectionWeeks)
      .then((res) => {
        if (!cancelled) setProjection(res);
      })
      .catch(() => {
        // Non-fatal — the rest of the dashboard still works without the chart.
      });
    return () => {
      cancelled = true;
    };
  }, [token, projectionWeeks]);

  function openBalanceModal() {
    setBalanceInput(state ? String(state.balance) : "");
    setBalanceError(null);
    setBalanceModalOpen(true);
  }

  async function handleSaveBalance() {
    if (!token) return;
    const amount = Number(balanceInput);
    if (Number.isNaN(amount) || amount < 0) {
      setBalanceError("Enter a valid amount of $0 or more.");
      return;
    }
    setIsSavingBalance(true);
    setBalanceError(null);
    try {
      await api.state.setBalance(token, amount);
      await loadCore();
      setBalanceModalOpen(false);
      showToast(`Balance updated to ${money(amount)}.`, "success");
    } catch (err) {
      setBalanceError(err instanceof ApiError ? err.message : "Couldn't update your balance.");
    } finally {
      setIsSavingBalance(false);
    }
  }

  if (isLoading) {
    return (
      <div className="mx-auto max-w-5xl space-y-6 p-6 sm:p-10">
        <Skeleton className="h-8 w-40" />
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))}
        </div>
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (error || !state) {
    return (
      <div className="mx-auto max-w-lg p-6 sm:p-10">
        <Card>
          <CardHeader>
            <CardTitle>Couldn&apos;t load your dashboard</CardTitle>
            <CardDescription>{error ?? "Something went wrong."}</CardDescription>
          </CardHeader>
          <Button onClick={loadCore}>Try again</Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-8 p-6 sm:p-10">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-text">Dashboard</h1>
        <Button variant="outline" size="sm" onClick={openBalanceModal}>
          <Pencil className="h-4 w-4" aria-hidden="true" />
          Update balance
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatCard label="Balance" value={money(state.balance)} icon={Wallet} />
        <StatCard
          label="Weekly income"
          value={money(state.weekly_income)}
          icon={TrendingUp}
          trend="up"
        />
        <StatCard
          label="Weekly expenses"
          value={money(state.weekly_expenses)}
          icon={Receipt}
          trend="down"
        />
        <StatCard
          label="Savings rate"
          value={`${(state.savings_rate * 100).toFixed(0)}%`}
          icon={PiggyBank}
          trend={state.net_weekly_flow >= 0 ? "up" : "down"}
          trendLabel={insights?.health_label}
        />
      </div>

      {insights && insights.insights.length > 0 && (
        <section>
          <h2 className="mb-3 text-lg font-bold text-text">Insights</h2>
          <div className="space-y-2">
            {insights.insights.map((text, i) => (
              <div key={i} className="flex items-start gap-3 rounded-2xl bg-surface p-4 shadow-card">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-accent-light">
                  <Sparkles className="h-4 w-4 text-accent" aria-hidden="true" />
                </span>
                <p className="text-sm text-text">{text}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-bold text-text">Balance projection</h2>
          <select
            value={projectionWeeks}
            onChange={(e) => setProjectionWeeks(Number(e.target.value))}
            className="rounded-xl border-0 bg-bg px-3 py-1.5 text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/40"
          >
            {PROJECTION_WEEK_OPTIONS.map((w) => (
              <option key={w} value={w}>
                {w} weeks
              </option>
            ))}
          </select>
        </div>
        <div className="rounded-3xl bg-surface p-5 shadow-card">
          {projection ? (
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={projection.timeline}>
                <CartesianGrid stroke="#D8E4DC" strokeDasharray="4 4" vertical={false} />
                <XAxis
                  dataKey="week"
                  tick={{ fontSize: 12, fill: "#7A9485" }}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  tick={{ fontSize: 12, fill: "#7A9485" }}
                  tickLine={false}
                  axisLine={false}
                  width={64}
                />
                <Tooltip
                  formatter={(value) => [money(Number(value)), "Balance"]}
                  labelFormatter={(label) => `Week ${label}`}
                  contentStyle={{ borderRadius: 12, border: "none", boxShadow: "0 4px 20px -4px rgba(26,46,34,0.15)" }}
                />
                <Line type="monotone" dataKey="balance" stroke="#1B6B3A" strokeWidth={2.5} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <Skeleton className="h-64 w-full" />
          )}
        </div>
      </section>

      <Modal open={balanceModalOpen} onClose={() => setBalanceModalOpen(false)} title="Update balance">
        <Input
          label="New balance ($)"
          type="number"
          min="0"
          step="0.01"
          value={balanceInput}
          onChange={(e) => setBalanceInput(e.target.value)}
          error={balanceError ?? undefined}
        />
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setBalanceModalOpen(false)}>
            Cancel
          </Button>
          <Button onClick={handleSaveBalance} isLoading={isSavingBalance}>
            Save
          </Button>
        </div>
      </Modal>
    </div>
  );
}
