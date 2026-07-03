// Mirrors the Pydantic schemas and response shapes in ../../../api.py and
// simulation.py. Keep in sync if those change.

export type Frequency = "Daily" | "Weekly" | "Biweekly" | "Monthly";
export type ShiftCategory = "Work" | "Class" | "Study" | "Meeting" | "Personal" | "Other";
export type Day =
  | "Monday"
  | "Tuesday"
  | "Wednesday"
  | "Thursday"
  | "Friday"
  | "Saturday"
  | "Sunday";

export interface User {
  id: number;
  email: string;
  created_at: string;
}

export interface JobOut {
  name: string;
  amount: number;
  frequency: Frequency;
  weekly_income: number;
}

export interface JobIn {
  name: string;
  amount: number;
  frequency: Frequency;
}

export interface ExpenseOut {
  name: string;
  amount: number;
  category: string;
  date: string;
  frequency: Frequency;
  weekly_amount: number;
}

export interface ExpenseIn {
  name: string;
  amount: number;
  category: string;
  date: string;
  frequency: Frequency;
}

export interface StateSummary {
  balance: number;
  weekly_income: number;
  weekly_expenses: number;
  net_weekly_flow: number;
  savings_rate: number;
  risk_score: number;
  health_score: number;
}

export interface ShiftOut {
  id: number;
  title: string;
  category: ShiftCategory;
  day: Day;
  start_time: string;
  end_time: string;
  hourly_rate: number;
  notes: string;
  shift_date: string;
}

export interface ShiftIn {
  title: string;
  category: ShiftCategory;
  day: Day;
  start_time: string;
  end_time: string;
  hourly_rate: number;
  notes?: string;
  shift_date?: string;
}

export interface InsightsResponse {
  health_score: number;
  risk_score: number;
  health_label: string;
  risk_label: string;
  insights: string[];
}

export interface ProjectionResponse {
  weeks: number;
  starting_balance: number;
  net_weekly_flow: number;
  timeline: { week: number; balance: number }[];
}

export interface HistoryResponse {
  count: number;
  snapshots: Record<string, unknown>[];
}

export interface IncomeByJob {
  [jobKey: string]: {
    name: string;
    rate: number;
    total_hours: number;
    total_income: number;
    avg_rate: number;
    shift_count: number;
  };
}

export interface EfficiencyReport {
  name: string;
  total_hours: number;
  total_income: number;
  income_per_hour: number;
  early_starts: number;
  late_ends: number;
  efficiency_note: string;
}

// run_monte_carlo() in simulation.py, minus `ending_balances` (api.py pops
// it before returning — it's a raw per-run array, too large for a plain
// JSON response).
export interface MonteCarloResult {
  average: number;
  best_case: number;
  worst_case: number;
  median: number;
  p25: number;
  p75: number;
  deficit_probability: number;
  safe_probability: number;
  plain_summary: string;
  n: number;
  weeks: number;
}

export interface WhatIfResult {
  history: { week: number; balance: number; note: string }[];
  summary: string;
}

export interface OptimizeResult {
  selected: { job_name: string; hours: number; hourly_rate: number; income: number }[];
  total_hours: number;
  total_income: number;
  hours_budget: number;
  hours_unused: number;
  effective_rate: number;
}
