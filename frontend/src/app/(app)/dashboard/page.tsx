"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Pencil } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { api, ApiError } from "@/lib/api";
import type { StateSummary, InsightsResponse, ShiftOut, ExpenseOut } from "@/lib/types";
import { hoursBetween } from "@/lib/utils";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { Input } from "@/components/ui/Input";
import { useToast } from "@/components/ui/Toast";

import { Hero } from "@/features/today/components/Hero";
import { DecisionBar } from "@/features/today/components/DecisionBar";
import { MoneyCard } from "@/features/today/components/MoneyCard";
import { GoalCard } from "@/features/today/components/GoalCard";
import { Timeline } from "@/features/today/components/Timeline";
import { OpportunityCard } from "@/features/today/components/OpportunityCard";
import { MoneyJourney } from "@/features/today/components/MoneyJourney";
import { InsightCard } from "@/features/today/components/InsightCard";
import { ActivityFeed, type ActivityItem } from "@/features/today/components/ActivityFeed";
import { MotivationalFooter } from "@/features/today/components/MotivationalFooter";
import {
  timeOfDay,
  greetingWord,
  formatTime12h,
  computeContextLine,
  displayName,
  money,
  moneyRounded,
  todayIso,
  formatDateLabel,
  isSameWeek,
} from "@/features/today/utils";
import { CalendarClock, Receipt } from "lucide-react";

interface DayPattern {
  day: string;
  avgHours: number;
  avgPay: number;
  deltaPct: number;
}

/** Best-earning weekday from the user's own shift history — powers the
 *  Opportunity and "Things Worth Noticing" cards without needing a fake
 *  shift marketplace. Requires a little history so it isn't noisy. */
function computeDayPattern(shifts: ShiftOut[]): DayPattern | null {
  if (shifts.length < 4) return null;
  const byDay: Record<string, { hours: number; pay: number; count: number }> = {};
  let totalPay = 0;
  let totalCount = 0;
  for (const s of shifts) {
    const hours = hoursBetween(s.start_time, s.end_time);
    const pay = hours * s.hourly_rate;
    const bucket = (byDay[s.day] ??= { hours: 0, pay: 0, count: 0 });
    bucket.hours += hours;
    bucket.pay += pay;
    bucket.count += 1;
    totalPay += pay;
    totalCount += 1;
  }
  const overallAvg = totalCount > 0 ? totalPay / totalCount : 0;
  let best: DayPattern | null = null;
  for (const [day, v] of Object.entries(byDay)) {
    if (v.count < 2 || overallAvg <= 0) continue;
    const avgPay = v.pay / v.count;
    const deltaPct = ((avgPay - overallAvg) / overallAvg) * 100;
    if (deltaPct > 10 && (!best || deltaPct > best.deltaPct)) {
      best = {
        day,
        avgHours: Math.round((v.hours / v.count) * 10) / 10,
        avgPay: Math.round(avgPay),
        deltaPct: Math.round(deltaPct),
      };
    }
  }
  return best;
}

function weeksToTarget(shortfall: number, weeklyFlow: number): number | null {
  if (shortfall <= 0) return 0;
  if (weeklyFlow <= 0) return null;
  return Math.ceil(shortfall / weeklyFlow);
}

export default function TodayPage() {
  const { user, token } = useAuth();
  const { showToast } = useToast();

  const [state, setState] = useState<StateSummary | null>(null);
  const [insights, setInsights] = useState<InsightsResponse | null>(null);
  const [shifts, setShifts] = useState<ShiftOut[]>([]);
  const [expenses, setExpenses] = useState<ExpenseOut[]>([]);

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [balanceModalOpen, setBalanceModalOpen] = useState(false);
  const [balanceInput, setBalanceInput] = useState("");
  const [isSavingBalance, setIsSavingBalance] = useState(false);
  const [balanceError, setBalanceError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    setIsLoading(true);
    setError(null);
    try {
      const [stateRes, insightsRes, shiftsRes, expensesRes] = await Promise.all([
        api.state.get(token),
        api.insights(token),
        api.shifts.list(token),
        api.expenses.list(token),
      ]);
      setState(stateRes);
      setInsights(insightsRes);
      setShifts(shiftsRes);
      setExpenses(expensesRes);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "We couldn't load today's plan.");
    } finally {
      setIsLoading(false);
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

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
      await load();
      setBalanceModalOpen(false);
      showToast(`Money available updated to ${money(amount)}.`, "success");
    } catch (err) {
      setBalanceError(err instanceof ApiError ? err.message : "Couldn't update that right now. Please try again.");
    } finally {
      setIsSavingBalance(false);
    }
  }

  const dayPattern = useMemo(() => computeDayPattern(shifts), [shifts]);

  const todayShifts = useMemo(() => shifts.filter((s) => s.shift_date === todayIso()), [shifts]);

  const weekHours = useMemo(
    () => shifts.filter((s) => isSameWeek(s.shift_date)).reduce((sum, s) => sum + hoursBetween(s.start_time, s.end_time), 0),
    [shifts]
  );

  const recentActivity: ActivityItem[] = useMemo(() => {
    interface Source {
      id: string;
      icon: ActivityItem["icon"];
      label: string;
      isoDate: string;
      amount: number;
      tone: ActivityItem["tone"];
    }
    const shiftItems: Source[] = shifts.map((s) => ({
      id: `shift-${s.id}`,
      icon: CalendarClock,
      label: `Added shift at ${s.title}`,
      isoDate: s.shift_date,
      amount: Math.round(hoursBetween(s.start_time, s.end_time) * s.hourly_rate * 100) / 100,
      tone: "positive",
    }));
    const expenseItems: Source[] = expenses.map((e) => ({
      id: `expense-${e.name}-${e.date}`,
      icon: Receipt,
      label: `${e.name}`,
      isoDate: e.date,
      amount: e.amount,
      tone: "negative",
    }));

    return [...shiftItems, ...expenseItems]
      .sort((a, b) => (b.isoDate > a.isoDate ? 1 : -1))
      .slice(0, 4)
      .map(({ isoDate, amount, tone, ...rest }) => ({
        ...rest,
        tone,
        dateLabel: formatDateLabel(isoDate),
        amount: `${tone === "positive" ? "+" : "-"}${money(Math.abs(amount))}`,
      }));
  }, [shifts, expenses]);

  if (isLoading) {
    return (
      <div className="mx-auto max-w-content space-y-8 px-5 py-8 md:px-12 md:py-10">
        <Skeleton className="h-6 w-64" />
        <Skeleton className="h-[220px] w-full rounded-hero md:h-[340px]" />
        <Skeleton className="h-[72px] w-full rounded-md" />
        <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-40 w-full rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  if (error || !state) {
    return (
      <div className="mx-auto max-w-empty px-5 py-16 text-center">
        <Card>
          <CardHeader>
            <CardTitle>We couldn&apos;t load today&apos;s plan.</CardTitle>
            <CardDescription>{error ?? "Your existing schedule is still safe."} Please try again.</CardDescription>
          </CardHeader>
          <Button onClick={load}>Try again</Button>
        </Card>
      </div>
    );
  }

  // Emergency Fund target mirrors the "3x monthly expenses" calculation
  // already used on the Goals page — balance stands in for "saved" until
  // real persisted goals ship.
  const monthlyExpenses = state.weekly_expenses * (52 / 12);
  const target = monthlyExpenses * 3;
  const shortfall = Math.max(0, target - state.balance);
  const weeksBase = weeksToTarget(shortfall, state.net_weekly_flow);
  const weeksLabel =
    weeksBase === 0
      ? "Your Emergency Fund is fully funded."
      : weeksBase === null
        ? "Not reachable at your current pace yet."
        : `${weeksBase} ${weeksBase === 1 ? "week" : "weeks"} to goal.`;

  let daysSooner = 0;
  if (dayPattern && weeksBase !== null && weeksBase > 0) {
    const weeksBoosted = weeksToTarget(Math.max(0, shortfall - dayPattern.avgPay), state.net_weekly_flow);
    if (weeksBoosted !== null) daysSooner = (weeksBase - weeksBoosted) * 7;
  }
  const goalRecommendation =
    dayPattern && daysSooner > 0
      ? `One extra ${dayPattern.day} shift gets you there about ${daysSooner} days sooner.`
      : weeksBase !== null && weeksBase > 0
        ? "Picking up an extra shift moves this date closer."
        : "You're in great shape — keep doing what you're doing.";

  const safeToSpend = Math.max(0, (state.balance - state.weekly_expenses) / 7);
  const safeSpendCaption =
    safeToSpend > 0
      ? "You can spend this today without affecting rent or goals."
      : "This week's expenses may outpace your balance — worth a look.";

  // Doc 05: one headline, one supporting sentence — no inline highlight
  // spans, no metrics inside the Hero itself.
  let headline: string;
  let description: string;
  if (dayPattern && daysSooner > 0) {
    headline = "One decision changes this week.";
    description = `Picking up ${dayPattern.day}'s shift gets your Emergency Fund finished about ${daysSooner} days sooner.`;
  } else if (state.net_weekly_flow < 0) {
    headline = "Let's find some room before it adds up.";
    description = "Your expenses are outpacing your income this week.";
  } else {
    headline = "You're closer than you think.";
    description = "You're on track this week — check today's plan to keep the momentum.";
  }

  const contextLine = computeContextLine(todayShifts);

  const decisionRecommendation = dayPattern && daysSooner > 0 ? `Take ${dayPattern.day}'s shift.` : "You're on track today.";
  const decisionOutcome = dayPattern && daysSooner > 0 ? `+${moneyRounded(dayPattern.avgPay)}` : undefined;
  const decisionImpact =
    dayPattern && daysSooner > 0 ? `Emergency Fund finishes about ${daysSooner} days sooner.` : "Nothing needs your attention right now.";

  const insightText = insights?.insights?.[0];
  const insightBody = dayPattern
    ? `You usually earn ${dayPattern.deltaPct}% more on ${dayPattern.day}s than your average shift.`
    : (insightText ?? "Log a few weeks of shifts and expenses and we'll start surfacing patterns here.");

  return (
    <div className="mx-auto max-w-content space-y-8 px-5 py-8 md:px-12 md:py-10">
      <div className="flex items-start justify-between gap-4">
        <div className="hidden md:block" />
        <Button variant="outline" size="sm" onClick={openBalanceModal} className="rounded-pill">
          <Pencil className="h-4 w-4" aria-hidden="true" />
          Update money available
        </Button>
      </div>

      <Hero
        greeting={`Good ${greetingWord()}, ${user ? displayName(user.email) : "there"}.`}
        headline={headline}
        description={description}
        contextLine={contextLine}
        primaryLabel="View recommendation"
        primaryHref="/shifts"
        secondaryLabel="See why"
        secondaryHref="/goals"
        timeOfDay={timeOfDay()}
      />

      <DecisionBar
        recommendation={decisionRecommendation}
        outcome={decisionOutcome}
        impact={decisionImpact}
        href={dayPattern && daysSooner > 0 ? "/shifts" : "/goals"}
      />

      <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
        <MoneyCard title="Money available" amount={moneyRounded(safeToSpend)} description={safeSpendCaption} />
        <MoneyCard
          title="Expected this week"
          amount={moneyRounded(state.weekly_income)}
          description={`${Math.round(weekHours * 10) / 10} hours scheduled.`}
        />
        <GoalCard
          name="Emergency Fund"
          current={moneyRounded(Math.min(state.balance, target))}
          target={moneyRounded(target)}
          percent={target > 0 ? (Math.min(state.balance, target) / target) * 100 : 0}
          recommendation={goalRecommendation}
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Timeline
          events={todayShifts.map((s) => ({
            time: formatTime12h(s.start_time),
            title: s.title,
            duration: `${hoursBetween(s.start_time, s.end_time)}h · +${moneyRounded(hoursBetween(s.start_time, s.end_time) * s.hourly_rate)}`,
          }))}
          emptyMessage="You're free today. Maybe today is for resting, or finding another opportunity."
        />
        <OpportunityCard
          suggestion={
            dayPattern
              ? {
                  day: dayPattern.day,
                  hours: dayPattern.avgHours,
                  pay: `+${moneyRounded(dayPattern.avgPay)}`,
                  impact: `Gets you to your Emergency Fund about ${Math.max(daysSooner, 1)} days sooner.`,
                }
              : null
          }
        />
      </div>

      <MoneyJourney
        steps={[
          { label: "Expected this week", amount: moneyRounded(state.weekly_income), note: "What you're on track to earn." },
          { label: "Money spent", amount: moneyRounded(state.weekly_expenses), note: "Bills and expenses this week." },
          {
            label: "Money available",
            amount: moneyRounded(state.net_weekly_flow),
            note: state.net_weekly_flow >= 0 ? "Left over after this week's bills." : "Short this week — worth a look.",
          },
        ]}
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <InsightCard body={insightBody} ctaLabel={dayPattern ? "Show me this shift" : undefined} ctaHref="/shifts" />
        <ActivityFeed items={recentActivity} />
      </div>

      <MotivationalFooter />

      <Modal open={balanceModalOpen} onClose={() => setBalanceModalOpen(false)} title="Update money available">
        <Input
          label="Money available ($)"
          type="number"
          min="0"
          step="0.01"
          value={balanceInput}
          onChange={(e) => setBalanceInput(e.target.value)}
          error={balanceError ?? undefined}
        />
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setBalanceModalOpen(false)}>
            Keep current plan
          </Button>
          <Button onClick={handleSaveBalance} isLoading={isSavingBalance}>
            Save
          </Button>
        </div>
      </Modal>
    </div>
  );
}
