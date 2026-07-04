// Reference/preview data only — NOT wired into the live Dashboard.
// The real dashboard (src/app/(app)/dashboard/page.tsx) pulls everything
// from the actual API (state, insights, shifts, expenses) so numbers stay
// truthful to each signed-in user. This file exists for design-review /
// storybook-style previews of the new bento layout with realistic shapes.
export const dashboardData = {
  user: {
    firstName: "Aba",
  },

  nextBestMove: {
    title: "Pick up one 4-hour shift this week",
    outcome: "You'll reach your Emergency Fund 8 days earlier.",
    detail: "Still leaves your evening free and keeps rent on track.",
  },

  safeToSpend: {
    amount: 45,
    note: "You can spend this today without affecting rent or goals.",
  },

  opportunity: {
    title: "Campus Library Shift",
    hours: 4,
    pay: 72,
    detail: "Still leaves your evening free.",
  },

  goal: {
    name: "Emergency Fund",
    current: 780,
    target: 1000,
    percent: 78,
    timeLeft: "3 weeks to goal",
    recommendation: "One extra shift gets you there 8 days sooner.",
  },

  todayPlan: [
    {
      time: "9:00 AM – 1:00 PM",
      place: "Campus Library",
      hours: "4h",
      pay: 72,
    },
    {
      time: "5:00 PM – 9:00 PM",
      place: "Walmart",
      hours: "4h",
      pay: 72,
    },
  ],

  moneyFlow: {
    earned: 412,
    used: 268,
    left: 144,
  },

  pattern: {
    title: "ShiftIQ noticed something",
    text: "You usually earn 18% more on Thursday evenings. Picking up tomorrow's shift could cover your phone bill.",
  },

  recentActivity: [
    {
      label: "Added shift at Walmart",
      amount: "+$72.00",
      tone: "positive",
      time: "Today, 10:24 AM",
    },
    {
      label: "Grocery expense",
      amount: "-$45.30",
      tone: "negative",
      time: "Today, 9:15 AM",
    },
    {
      label: "Future Check completed",
      amount: "View results",
      tone: "neutral",
      time: "Yesterday, 8:42 PM",
    },
  ],
};
