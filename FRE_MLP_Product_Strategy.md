# Financial Reality Engine — Minimum Lovable Product (MLP) Strategy

**Constraint honored throughout: zero backend changes.** Every recommendation below routes through engines that already exist — `financial_state.py`, `schedule_analytics.shift_impact()`, `optimizer.py`, `simulation.run_monte_carlo()`. This is a UI and information-architecture redesign, not a rebuild.

---

## 1. MLP Product Definition

FRE today is a financial *tracking* system wearing seven tabs of analytics. The MLP reframes it as a financial *decision* tool with one job: tell you, instantly, what any change to your schedule does to your money. The product is no longer "manage your finances" — it's "before you take or drop a shift, know the real cost." Everything else FRE can already compute (risk score, Monte Carlo, goals, trends) becomes supporting detail a user can dig into later, not the thing they see first. The backend's actual differentiator — `shift_impact()` running in ~3 microseconds against a single source of truth — gets a UI that matches its speed: tap a shift, see the consequence, no navigation required.

---

## 2. What to Remove From the Current UI

Nothing below is a backend cut — these engines stay callable, just not surfaced as primary navigation.

- **The 5-tab Analytics page** (Savings / Health / Income / Expenses / Trends) — this is the single biggest source of "what do I even do here" paralysis. Collapse to zero default-visible tabs; reachable from a single "Details" link, not main nav.
- **Goals page** — remove from the main nav bar entirely. It's a feature for engaged week-3 users, not something a first-time opener needs to see.
- **Settings as a nav-level destination** — move behind a profile icon, not a sidebar item competing for attention with the actual product.
- **Schedule's 5 sub-tabs** (Week View / Add Event / My Events / Free Time / Import) — a first-time user should never have to choose among five tabs to add their own schedule. Collapse Add/My Events/Import into one "+" action sheet; Free Time becomes a detail view, not a tab.
- **Forecasting's 3-tab structure** (Projection / Scenarios / Simulation) — Monte Carlo with manual "weeks" and "runs" number inputs is a power-user surface, not a first-screen one. It becomes a single button result, not a configuration form.
- **The multi-bullet "Quick Insights" card** on the dashboard — currently shows 3 separate insight strings. Cut to one headline insight; the rest become available on tap, not shown by default.
- **Raw Job/Expense CRUD as a top-level "Data" nav item** — income should visibly come from the schedule (it already does, architecturally); a standalone "Data Management" tab undercuts that story and makes FRE look like a budgeting app again.

Net result: 7 nav items → 3.

---

## 3. What the Home Screen Must Show — Exact Components

Single screen, no scrolling required to see the core value. Top to bottom:

1. **Headline number** (one line, large type): *"You're on track to net **$262** this week."* — pulled directly from `state.net_weekly_flow()`, framed as an outcome, not a balance sheet line item.
2. **One-word stability badge**, not a numeric score: *Stable* / *Tight* / *At Risk*, color-coded — `risk_score()` mapped through `insight_engine.risk_label()` (already exists) instead of showing "60/100."
3. **This week's shifts as a compact horizontal strip** — one row, one block per scheduled Work shift, day + hours visible, nothing else. Pulled from `db.get_events()` filtered to the current week, not the full weekly-calendar view.
4. **Each shift block is tappable.** That tap *is* the product — see Section 4.
5. **One secondary action below the strip:** *"What if I picked up an extra shift?"* — a single entry point into the optimizer, framed as a question, not a configuration screen.

Nothing else. No charts, no risk-factor breakdowns, no savings rate percentage, no trend lines on the first screen.

---

## 4. The "Aha Moment" User Flow

1. User opens the app. Within one render, they see: *"You're on track to net $262 this week."* — value visible before any interaction. **(< 2 seconds)**
2. They notice Thursday's shift in the strip below.
3. They tap it.
4. Instantly, inline — no new screen, no loading state — a card expands beneath that shift:
   *"Skip this shift? You'd lose $48 (-12% this week). You'd still net $52 net — manageable, but tight."*
   This is `shift_impact()` rendered verbatim; the recommendation string it already returns is the copy.
5. The user realizes, without being told: *this app knows what my schedule is worth, shift by shift, in real time.*
6. That's the aha moment — total elapsed time under 10 seconds, zero forms filled out, zero tabs visited.

Everything FRE can do beyond this (Monte Carlo, optimizer, trends, goals) is now something the user *seeks out* because they've already trusted the core number — not something they had to wade through to find it.

---

## 5. The Single Killer Feature

**Tap-a-shift, see-the-consequence** — i.e., `shift_impact()` exposed with zero setup and zero navigation.

Not Monte Carlo (too abstract for a daily-use moment — it's a "once a month" feature). Not the knapsack optimizer (genuinely powerful, but it's a *second* session feature, for someone who already trusts the app and now wants it to plan for them). Shift-impact decisioning wins because it is: instant (~3 microseconds backing it), concrete (a dollar figure, not a probability distribution), and tied to a decision the user is *already making* — whether to take or drop a real shift this week. This is the feature that earns a daily open; the rest earns a weekly or monthly one.

---

## 6. Suggested Onboarding — First 60 Seconds

- **0–10s:** One screen, one input: *"Paste or import this week's schedule."* Uses the existing natural-language import parser (`date_parser.py` already handles "Thursday, June 18" headers, AM/PM, inline rates) — no separate "add job," "add expense," or "set a goal" steps. Income is schedule-derived; nothing else is needed to start.
- **10–25s:** The moment import finishes, the home screen renders immediately with the real headline number and the week strip — no setup wizard, no empty states, no "let's add your first expense" prompts.
- **25–45s:** A single one-time coachmark over the first shift block: *"Tap any shift to see what it's worth."* No tutorial carousel, no multi-step walkthrough — one nudge, one action.
- **45–60s:** User taps, sees the shift-impact card, and has now experienced the entire core loop — without ever opening Analytics, Goals, Settings, or Forecasting. Those become discoverable later, not gatekeeping steps before value.

---

## Why This Works Without Touching the Backend

Every component above is a thinner view over something that already exists and is already tested:

| UI Surface | Existing Engine Call |
|---|---|
| Headline number | `state.net_weekly_flow()` |
| Stability badge | `insight_engine.risk_label(state.risk_score())` |
| Week strip | `db.get_events()`, filtered to current week |
| Tap-a-shift card | `schedule_analytics.shift_impact(event, state)` |
| "Extra shift?" action | `optimizer.optimize_shift_selection()` |
| Import onboarding | `date_parser.py` (already built) |

The 166-test backend doesn't change. What changes is which 10% of it is on-screen by default, and which 90% is one tap away instead of a competing nav item.
