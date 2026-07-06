"use client";

import { FormEvent, useState } from "react";
import { Target, TrendingUp, PiggyBank } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import type { StateSummary } from "@/lib/types";
import { useAsync } from "@/hooks/useAsync";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { IconCard } from "@/components/ui/IconCard";
import { Skeleton } from "@/components/ui/Skeleton";
import { cn, money } from "@/lib/utils";

type GoalTab = "weeks" | "progress" | "emergency";

// Mirrors FinancialState.weeks_to_goal() in financial_state.py.
function weeksToGoal(goalAmount: number, balance: number, netWeeklyFlow: number): number | null {
  if (netWeeklyFlow <= 0) return null;
  const remaining = goalAmount - balance;
  if (remaining <= 0) return 0;
  const weeks = Math.ceil(remaining / netWeeklyFlow);
  return weeks <= 10_000 ? weeks : null;
}

// Mirrors FinancialState.goal_progress().
function goalProgressPct(goalAmount: number, balance: number): number | null {
  if (goalAmount === 0) return null;
  return (balance / goalAmount) * 100;
}

export default function GoalsPage() {
  const { token } = useAuth();

  const {
    data: state,
    isLoading,
    error,
    reload: load,
  } = useAsync<StateSummary>(() => (token ? api.state.get(token) : null), [token], "Something went wrong loading your data.");

  const [tab, setTab] = useState<GoalTab>("weeks");

  const [weeksGoalInput, setWeeksGoalInput] = useState("");
  const [weeksResult, setWeeksResult] = useState<number | null | undefined>(undefined);
  const [weeksError, setWeeksError] = useState<string | null>(null);

  const [progressGoalInput, setProgressGoalInput] = useState("");
  const [progressResult, setProgressResult] = useState<number | null | undefined>(undefined);
  const [progressError, setProgressError] = useState<string | null>(null);

  function handleWeeksSubmit(e: FormEvent) {
    e.preventDefault();
    if (!state) return;
    const goal = Number(weeksGoalInput);
    if (Number.isNaN(goal) || goal <= 0) {
      setWeeksError("Goal must be greater than zero.");
      setWeeksResult(undefined);
      return;
    }
    setWeeksError(null);
    setWeeksResult(weeksToGoal(goal, state.balance, state.net_weekly_flow));
  }

  function handleProgressSubmit(e: FormEvent) {
    e.preventDefault();
    if (!state) return;
    const goal = Number(progressGoalInput);
    if (Number.isNaN(goal) || goal <= 0) {
      setProgressError("Goal must be greater than zero.");
      setProgressResult(undefined);
      return;
    }
    setProgressError(null);
    setProgressResult(goalProgressPct(goal, state.balance));
  }

  if (isLoading) {
    return (
      <div className="mx-auto max-w-2xl space-y-4 p-6 sm:p-10">
        <Skeleton className="h-8 w-32" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }

  if (error || !state) {
    return (
      <div className="mx-auto max-w-lg p-6 sm:p-10">
        <Card>
          <CardHeader>
            <CardTitle>Couldn&apos;t load your goals data</CardTitle>
            <CardDescription>{error ?? "Something went wrong."}</CardDescription>
          </CardHeader>
          <Button onClick={load}>Try again</Button>
        </Card>
      </div>
    );
  }

  const monthlyExpenses = state.weekly_expenses * (52 / 12);
  const target3x = monthlyExpenses * 3;
  const target6x = monthlyExpenses * 6;

  function timeToReach(target: number): { label: string; tone: "good" | "muted" | "bad" } {
    const shortfall = target - state!.balance;
    if (shortfall <= 0) return { label: "Already funded", tone: "good" };
    if (state!.net_weekly_flow <= 0) return { label: "Not reachable at current flow", tone: "bad" };
    const weeks = shortfall / state!.net_weekly_flow;
    return { label: `${Math.ceil(weeks)} weeks (${(weeks / 4.33).toFixed(1)} months)`, tone: "muted" };
  }

  const time3x = timeToReach(target3x);
  const time6x = timeToReach(target6x);

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6 sm:p-10">
      <div>
        <h1 className="text-2xl font-bold text-text">Goals</h1>
        <p className="mt-1 text-sm text-muted">Calculators for savings targets, progress, and your emergency fund.</p>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <IconCard icon={Target} label="Weeks to Goal" selected={tab === "weeks"} onClick={() => setTab("weeks")} />
        <IconCard
          icon={TrendingUp}
          label="Goal Progress"
          selected={tab === "progress"}
          onClick={() => setTab("progress")}
        />
        <IconCard
          icon={PiggyBank}
          label="Emergency Fund"
          selected={tab === "emergency"}
          onClick={() => setTab("emergency")}
        />
      </div>

      {tab === "weeks" && (
        <Card>
          <CardHeader>
            <CardTitle>Weeks to Goal</CardTitle>
            <CardDescription>
              Enter a savings target. We&apos;ll tell you how many weeks it will take to reach it at
              your current net weekly flow.
            </CardDescription>
          </CardHeader>
          <form onSubmit={handleWeeksSubmit} className="flex flex-wrap items-end gap-3">
            <div className="w-40">
              <Input
                label="Savings goal ($)"
                type="number"
                min="0.01"
                step="0.01"
                value={weeksGoalInput}
                onChange={(e) => setWeeksGoalInput(e.target.value)}
              />
            </div>
            <Button type="submit">Calculate</Button>
          </form>
          {weeksError && (
            <p role="alert" className="mt-3 text-sm text-danger">
              {weeksError}
            </p>
          )}
          {weeksResult !== undefined && !weeksError && (
            <div className="mt-4 space-y-2 border-t border-border/60 pt-4 text-sm">
              {weeksResult === null ? (
                <p className="text-danger">
                  Your current net weekly flow is zero or negative. This goal cannot be reached
                  without more income or fewer expenses.
                </p>
              ) : (
                <>
                  <div className="flex justify-between">
                    <span className="text-muted">Net weekly flow</span>
                    <span className="font-semibold text-text">
                      {state.net_weekly_flow >= 0 ? "+" : ""}
                      {money(state.net_weekly_flow)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted">Weeks to goal</span>
                    <span className="font-semibold text-accent">{weeksResult}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted">That&apos;s roughly</span>
                    <span className="font-semibold text-accent">{(weeksResult / 4.33).toFixed(1)} months</span>
                  </div>
                </>
              )}
            </div>
          )}
        </Card>
      )}

      {tab === "progress" && (
        <Card>
          <CardHeader>
            <CardTitle>Goal Progress</CardTitle>
            <CardDescription>
              Enter a savings goal and see what percentage you&apos;ve already saved.
            </CardDescription>
          </CardHeader>
          <form onSubmit={handleProgressSubmit} className="flex flex-wrap items-end gap-3">
            <div className="w-40">
              <Input
                label="Savings goal ($)"
                type="number"
                min="0.01"
                step="0.01"
                value={progressGoalInput}
                onChange={(e) => setProgressGoalInput(e.target.value)}
              />
            </div>
            <Button type="submit">Show progress</Button>
          </form>
          {progressError && (
            <p role="alert" className="mt-3 text-sm text-danger">
              {progressError}
            </p>
          )}
          {progressResult != null && !progressError && (
            <div className="mt-4 space-y-3 border-t border-border/60 pt-4">
              {(() => {
                const pct = Math.min(progressResult, 100);
                const color = pct >= 50 ? "bg-accent" : pct >= 20 ? "bg-[#e67e22]" : "bg-danger";
                return (
                  <>
                    <div className="flex justify-between text-sm">
                      <span className="text-muted">Current balance</span>
                      <span className="font-semibold text-text">{money(state.balance)}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-muted">Progress</span>
                      <span className="font-semibold text-text">{pct.toFixed(1)}%</span>
                    </div>
                    <div className="h-6 w-full overflow-hidden rounded-full bg-border/60">
                      <div
                        className={cn("h-full rounded-full transition-all duration-300", color)}
                        style={{ width: `${Math.max(4, pct)}%` }}
                      />
                    </div>
                  </>
                );
              })()}
            </div>
          )}
        </Card>
      )}

      {tab === "emergency" && (
        <Card>
          <CardHeader>
            <CardTitle>Emergency Fund Calculator</CardTitle>
            <CardDescription>
              An emergency fund covers 3&ndash;6 months of expenses so a job loss, medical bill, or
              car repair doesn&apos;t send you into debt.
            </CardDescription>
          </CardHeader>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between">
              <span className="text-muted">Monthly expenses</span>
              <span className="font-semibold text-text">{money(monthlyExpenses)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted">Current balance</span>
              <span className="font-semibold text-text">{money(state.balance)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted">Net weekly flow</span>
              <span className="font-semibold text-text">
                {state.net_weekly_flow >= 0 ? "+" : ""}
                {money(state.net_weekly_flow)}
              </span>
            </div>
            <div className="border-t border-border/60 pt-3" />
            <div className="flex justify-between">
              <span className="text-muted">3-month target</span>
              <span className="font-semibold text-accent">{money(target3x)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted">Time to reach 3&times;</span>
              <span
                className={cn(
                  "font-semibold",
                  time3x.tone === "good" ? "text-accent" : time3x.tone === "bad" ? "text-danger" : "text-text"
                )}
              >
                {time3x.label}
              </span>
            </div>
            <div className="border-t border-border/60 pt-3" />
            <div className="flex justify-between">
              <span className="text-muted">6-month target</span>
              <span className="font-semibold text-accent">{money(target6x)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted">Time to reach 6&times;</span>
              <span
                className={cn(
                  "font-semibold",
                  time6x.tone === "good" ? "text-accent" : time6x.tone === "bad" ? "text-danger" : "text-text"
                )}
              >
                {time6x.label}
              </span>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
