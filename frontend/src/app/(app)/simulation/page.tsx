"use client";

import { FormEvent, useState } from "react";
import { TrendingUp, TrendingDown, ShieldCheck, ShieldAlert } from "lucide-react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  LineChart,
  Line,
} from "recharts";
import { useAuth } from "@/context/AuthContext";
import { api, ApiError } from "@/lib/api";
import type { MonteCarloResult, WhatIfResult } from "@/lib/types";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { StatCard } from "@/components/ui/StatCard";
import { cn } from "@/lib/utils";

type Tab = "monte-carlo" | "whatif";

function money(n: number): string {
  return `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export default function SimulationPage() {
  const { token } = useAuth();
  const [tab, setTab] = useState<Tab>("monte-carlo");

  // Monte Carlo
  const [mcWeeks, setMcWeeks] = useState("12");
  const [mcResult, setMcResult] = useState<MonteCarloResult | null>(null);
  const [mcLoading, setMcLoading] = useState(false);
  const [mcError, setMcError] = useState<string | null>(null);

  // What-If
  const [wiDescription, setWiDescription] = useState("");
  const [wiDollarChange, setWiDollarChange] = useState("");
  const [wiWeeks, setWiWeeks] = useState("12");
  const [wiResult, setWiResult] = useState<WhatIfResult | null>(null);
  const [wiLoading, setWiLoading] = useState(false);
  const [wiError, setWiError] = useState<string | null>(null);

  async function runMonteCarlo(e: FormEvent) {
    e.preventDefault();
    if (!token) return;
    const weeks = Number(mcWeeks);
    if (Number.isNaN(weeks) || weeks <= 0) {
      setMcError("Enter a number of weeks greater than 0.");
      return;
    }
    setMcLoading(true);
    setMcError(null);
    try {
      const result = await api.simulate.monteCarlo(token, weeks);
      setMcResult(result);
    } catch (err) {
      setMcError(err instanceof ApiError ? err.message : "Couldn't run the simulation.");
    } finally {
      setMcLoading(false);
    }
  }

  async function runWhatIf(e: FormEvent) {
    e.preventDefault();
    if (!token) return;
    const description = wiDescription.trim();
    const dollarChange = Number(wiDollarChange);
    const weeks = Number(wiWeeks);
    if (!description) {
      setWiError("Describe what happened.");
      return;
    }
    if (Number.isNaN(dollarChange)) {
      setWiError("Enter a dollar amount (can be negative).");
      return;
    }
    if (Number.isNaN(weeks) || weeks <= 0) {
      setWiError("Enter a number of weeks greater than 0.");
      return;
    }
    setWiLoading(true);
    setWiError(null);
    try {
      const result = await api.simulate.whatIf(token, description, dollarChange, weeks);
      setWiResult(result);
    } catch (err) {
      setWiError(err instanceof ApiError ? err.message : "Couldn't run the simulation.");
    } finally {
      setWiLoading(false);
    }
  }

  const mcChartData = mcResult
    ? [
        { label: "Worst", value: mcResult.worst_case },
        { label: "25th %ile", value: mcResult.p25 },
        { label: "Median", value: mcResult.median },
        { label: "Average", value: mcResult.average },
        { label: "75th %ile", value: mcResult.p75 },
        { label: "Best", value: mcResult.best_case },
      ]
    : [];

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6 sm:p-10">
      <h1 className="text-2xl font-bold text-text">Simulation</h1>

      <div className="flex gap-2">
        <button
          onClick={() => setTab("monte-carlo")}
          className={cn(
            "rounded-full px-4 py-2 text-sm font-medium transition-colors duration-150",
            tab === "monte-carlo" ? "bg-text text-white" : "bg-surface text-muted hover:bg-surface-hover"
          )}
        >
          Monte Carlo
        </button>
        <button
          onClick={() => setTab("whatif")}
          className={cn(
            "rounded-full px-4 py-2 text-sm font-medium transition-colors duration-150",
            tab === "whatif" ? "bg-text text-white" : "bg-surface text-muted hover:bg-surface-hover"
          )}
        >
          What-If
        </button>
      </div>

      {tab === "monte-carlo" ? (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Run 500 possible futures</CardTitle>
              <CardDescription>
                Simulates random real-world events (extra shifts, surprise bills, etc.) to show a
                realistic range of outcomes, not just one guess.
              </CardDescription>
            </CardHeader>
            <form onSubmit={runMonteCarlo} className="flex flex-wrap items-end gap-3">
              <div className="w-32">
                <Input
                  label="Weeks"
                  type="number"
                  min="1"
                  max="520"
                  value={mcWeeks}
                  onChange={(e) => setMcWeeks(e.target.value)}
                />
              </div>
              <Button type="submit" isLoading={mcLoading}>
                Run simulation
              </Button>
            </form>
            {mcError && <p className="mt-3 text-sm text-danger">{mcError}</p>}
          </Card>

          {mcResult && (
            <>
              <Card>
                <p className="text-sm leading-relaxed text-text">{mcResult.plain_summary}</p>
              </Card>

              <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <StatCard label="Average outcome" value={money(mcResult.average)} icon={TrendingUp} />
                <StatCard label="Best case" value={money(mcResult.best_case)} icon={ShieldCheck} trend="up" />
                <StatCard label="Worst case" value={money(mcResult.worst_case)} icon={TrendingDown} trend="down" />
                <StatCard
                  label="Deficit risk"
                  value={`${mcResult.deficit_probability}%`}
                  icon={ShieldAlert}
                  trend={mcResult.deficit_probability > 25 ? "down" : "up"}
                  trendLabel={`${mcResult.safe_probability}% safe`}
                />
              </div>

              <div className="rounded-3xl bg-surface p-5 shadow-card">
                <h3 className="mb-3 text-sm font-semibold text-text">
                  Outcome range across {mcResult.n} simulated futures
                </h3>
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={mcChartData}>
                    <CartesianGrid stroke="#D8E4DC" strokeDasharray="4 4" vertical={false} />
                    <XAxis
                      dataKey="label"
                      tick={{ fontSize: 11, fill: "#7A9485" }}
                      tickLine={false}
                      axisLine={false}
                    />
                    <YAxis tick={{ fontSize: 12, fill: "#7A9485" }} tickLine={false} axisLine={false} width={64} />
                    <Tooltip
                      formatter={(value) => [money(Number(value)), "Balance"]}
                      contentStyle={{
                        borderRadius: 12,
                        border: "none",
                        boxShadow: "0 4px 20px -4px rgba(26,46,34,0.15)",
                      }}
                    />
                    <Bar dataKey="value" fill="#1B6B3A" radius={[8, 8, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </>
          )}
        </div>
      ) : (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>What if something happened?</CardTitle>
              <CardDescription>
                Describe an event and its dollar impact — we&apos;ll show how your balance plays out
                over the following weeks.
              </CardDescription>
            </CardHeader>
            <form onSubmit={runWhatIf} className="space-y-4">
              <Input
                label="What happened?"
                placeholder="e.g. Car repair, got sick, picked up an extra shift"
                value={wiDescription}
                onChange={(e) => setWiDescription(e.target.value)}
              />
              <div className="grid grid-cols-2 gap-3">
                <Input
                  label="Dollar impact"
                  type="number"
                  step="0.01"
                  placeholder="-200 or 150"
                  value={wiDollarChange}
                  onChange={(e) => setWiDollarChange(e.target.value)}
                  hint="Negative for a cost, positive for a gain."
                />
                <Input
                  label="Weeks to project"
                  type="number"
                  min="1"
                  max="520"
                  value={wiWeeks}
                  onChange={(e) => setWiWeeks(e.target.value)}
                />
              </div>
              {wiError && <p className="text-sm text-danger">{wiError}</p>}
              <Button type="submit" isLoading={wiLoading}>
                Run simulation
              </Button>
            </form>
          </Card>

          {wiResult && (
            <>
              <Card>
                <p className="text-sm leading-relaxed text-text">{wiResult.summary}</p>
              </Card>

              <div className="rounded-3xl bg-surface p-5 shadow-card">
                <h3 className="mb-3 text-sm font-semibold text-text">Balance over time</h3>
                <ResponsiveContainer width="100%" height={260}>
                  <LineChart data={wiResult.history}>
                    <CartesianGrid stroke="#D8E4DC" strokeDasharray="4 4" vertical={false} />
                    <XAxis
                      dataKey="week"
                      tick={{ fontSize: 12, fill: "#7A9485" }}
                      tickLine={false}
                      axisLine={false}
                    />
                    <YAxis tick={{ fontSize: 12, fill: "#7A9485" }} tickLine={false} axisLine={false} width={64} />
                    <Tooltip
                      formatter={(value) => [money(Number(value)), "Balance"]}
                      labelFormatter={(label) => `Week ${label}`}
                      contentStyle={{
                        borderRadius: 12,
                        border: "none",
                        boxShadow: "0 4px 20px -4px rgba(26,46,34,0.15)",
                      }}
                    />
                    <Line type="monotone" dataKey="balance" stroke="#2563EB" strokeWidth={2.5} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
