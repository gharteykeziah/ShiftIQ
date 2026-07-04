"use client";

import Link from "next/link";
import { ArrowRight, Wallet, Sparkles, Clock, Target } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { AppWindow } from "@/components/marketing/AppWindow";
import { FaqItem } from "@/components/marketing/FaqItem";

// Public landing page — structural rhythm inspired by studying Granola's
// marketing site (editorial serif headlines, generous whitespace, sunken
// cream section breaks, alternating feature rows, pill buttons, FAQ
// accordion, bold closing CTA). Every word of copy and every visual below
// is ShiftIQ's own — no borrowed logos, quotes, stats, or brand assets.
const JOB_TYPES = ["Baristas", "Retail", "Warehouse", "Rideshare & delivery", "Servers", "Nurses & CNAs"];

const FEATURES = [
  {
    eyebrow: "Today",
    heading: "Your next best move, every day",
    body: "ShiftIQ looks at your schedule, your bills, and your goals together, then tells you the one thing worth doing today — not a wall of numbers to interpret yourself.",
    preview: (
      <div className="space-y-3">
        <p className="text-metadata font-semibold uppercase tracking-wide text-accent">Next best move</p>
        <p className="text-body-lg font-medium text-text">Take Friday&apos;s shift.</p>
        <p className="text-sm text-muted">Emergency Fund finishes about 8 days sooner.</p>
      </div>
    ),
  },
  {
    eyebrow: "Money",
    heading: "See exactly where you stand",
    body: "No spreadsheets, no dashboards to decode. Just what you're expected to earn, what's already spoken for, and what's actually safe to spend today.",
    preview: (
      <div>
        <p className="text-sm font-medium text-muted">Money available</p>
        <p className="mt-1 font-serif text-4xl font-medium text-text">$48</p>
        <p className="mt-2 text-sm text-muted">Safe to spend today without affecting rent or goals.</p>
      </div>
    ),
  },
  {
    eyebrow: "Future Check",
    heading: "Look ahead before you decide",
    body: "Wondering if you can afford to skip a shift, or what one extra one gets you? Future Check shows the real outcome before you commit to anything.",
    preview: (
      <div className="space-y-2">
        <p className="text-sm text-muted">What if you worked one extra shift this week?</p>
        <p className="font-serif text-2xl font-medium text-text">Emergency Fund: 3 weeks → 2 weeks</p>
      </div>
    ),
  },
];

const PRINCIPLES = [
  { icon: Sparkles, title: "Recommendations, not reports", body: "One clear next move beats ten charts to interpret." },
  { icon: Clock, title: "Built from your real shifts", body: "Every insight comes from your own schedule and spending — never a fabricated average." },
  { icon: Target, title: "Calm by design", body: "No red alerts, no guilt trips. Just a clearer plan than you had this morning." },
];

const FAQS = [
  {
    q: "Who is ShiftIQ for?",
    a: "Anyone whose income depends on their schedule — hourly workers, gig drivers, servers, students working part-time, and anyone juggling variable shifts and fixed bills.",
  },
  {
    q: "Is my data private?",
    a: "Your shifts and expenses are only used to power your own recommendations. ShiftIQ doesn't sell your data.",
  },
  {
    q: "Do I need to connect a bank account?",
    a: "No. You tell ShiftIQ your balance, jobs, and expenses directly — nothing is pulled automatically unless you choose to add it.",
  },
  {
    q: "Is ShiftIQ free?",
    a: "Yes, for now. If that changes, existing plans and data will always come first — we'll never surprise you.",
  },
];

export default function OnboardingPage() {
  return (
    <main className="bg-bg">
      {/* Header */}
      <header className="mx-auto flex max-w-content items-center justify-between px-5 py-6 md:px-12">
        <p className="font-serif text-xl font-medium text-text">ShiftIQ</p>
        <div className="flex items-center gap-3">
          <Link href="/login" className="text-sm font-medium text-text hover:text-accent-dark">
            Log in
          </Link>
          <Link
            href="/register"
            className="inline-flex h-10 items-center justify-center rounded-pill bg-text px-5 text-sm font-medium text-white transition-colors duration-200 hover:bg-text/85"
          >
            Get started
          </Link>
        </div>
      </header>

      {/* Hero */}
      <section className="mx-auto grid max-w-content grid-cols-1 items-center gap-10 px-5 py-10 md:grid-cols-2 md:px-12 md:py-16">
        <div>
          <p className="text-sm font-medium text-muted">For people paid by the hour</p>
          <h1 className="mt-3 font-serif text-[40px] font-normal leading-[1.05] tracking-tight text-text md:text-hero">
            Know your next best move.
          </h1>
          <p className="mt-5 max-w-md text-body-lg text-muted">
            ShiftIQ turns your schedule into a clear financial plan — shifts, bills, and goals, one decision at a time.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href="/register"
              className="inline-flex h-12 items-center justify-center gap-2 rounded-pill bg-text px-6 text-sm font-medium text-white transition-colors duration-200 hover:bg-text/85"
            >
              Get started <ArrowRight size={16} aria-hidden="true" />
            </Link>
            <Link
              href="/login"
              className="inline-flex h-12 items-center justify-center rounded-pill border border-border px-6 text-sm font-medium text-text transition-colors duration-200 hover:bg-surface-hover"
            >
              I already have an account
            </Link>
          </div>
        </div>

        <AppWindow>
          <p className="text-metadata font-semibold uppercase tracking-wide text-accent">Your next best move</p>
          <p className="mt-2 font-serif text-2xl font-medium text-text">Take Friday&apos;s shift.</p>
          <p className="mt-1 text-sm font-medium text-accent-dark">+$82</p>
          <p className="mt-3 text-sm text-muted">Emergency Fund finishes about 8 days sooner.</p>
          <div className="mt-5 h-px bg-border" />
          <div className="mt-5 flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-muted">Money available</p>
              <p className="font-serif text-2xl font-medium text-text">$48</p>
            </div>
            <Wallet size={28} strokeWidth={2} className="text-accent" aria-hidden="true" />
          </div>
        </AppWindow>
      </section>

      {/* Built for */}
      <section className="bg-surface-hover py-12">
        <div className="mx-auto max-w-content px-5 text-center md:px-12">
          <p className="text-sm font-medium text-muted">Built for the way you actually work</p>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-x-8 gap-y-4">
            {JOB_TYPES.map((job) => (
              <span key={job} className="text-body-lg font-medium text-text/70">
                {job}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* Alternating feature rows */}
      <section className="mx-auto max-w-content space-y-20 px-5 py-20 md:px-12">
        {FEATURES.map((f, i) => (
          <div
            key={f.heading}
            className={`grid grid-cols-1 items-center gap-10 md:grid-cols-2 ${i % 2 === 1 ? "md:[&>*:first-child]:order-2" : ""}`}
          >
            <div>
              <p className="text-sm font-medium text-accent">{f.eyebrow}</p>
              <h2 className="mt-2 font-serif text-section font-medium leading-tight text-text">{f.heading}</h2>
              <p className="mt-4 max-w-md text-body-lg text-muted">{f.body}</p>
            </div>
            <AppWindow>{f.preview}</AppWindow>
          </div>
        ))}
      </section>

      {/* Principles */}
      <section className="bg-surface-hover py-20">
        <div className="mx-auto max-w-content px-5 md:px-12">
          <h2 className="max-w-xl font-serif text-section font-medium leading-tight text-text">
            Built to reduce uncertainty, not add to it.
          </h2>
          <div className="mt-10 grid grid-cols-1 gap-6 md:grid-cols-3">
            {PRINCIPLES.map((p) => {
              const Icon = p.icon;
              return (
                <div key={p.title} className="rounded-lg border border-border bg-surface p-8">
                  <Icon size={24} strokeWidth={2} className="text-accent" aria-hidden="true" />
                  <p className="mt-4 text-card-heading font-semibold text-text">{p.title}</p>
                  <p className="mt-2 text-sm text-muted">{p.body}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="mx-auto max-w-content px-5 py-20 md:px-12">
        <h2 className="text-center font-serif text-section font-medium text-text">Questions and answers</h2>
        <div className="mx-auto mt-10 max-w-reading">
          {FAQS.map((f) => (
            <FaqItem key={f.q} question={f.q} answer={f.a} />
          ))}
        </div>
      </section>

      {/* Closing CTA */}
      <section className="mx-auto max-w-content px-5 pb-20 md:px-12">
        <div className="rounded-hero bg-text px-8 py-16 text-center md:px-16">
          <h2 className="mx-auto max-w-2xl font-serif text-section font-medium leading-tight text-white md:text-page-title">
            Ready to know your next move?
          </h2>
          <p className="mx-auto mt-4 max-w-md text-body-lg text-white/70">
            Add your shifts and bills, and let ShiftIQ tell you what matters today.
          </p>
          <Link
            href="/register"
            className="mt-8 inline-flex h-12 items-center justify-center rounded-pill bg-white px-6 text-sm font-medium text-text transition-colors duration-200 hover:bg-white/90"
          >
            Get started
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="mx-auto max-w-content px-5 py-10 md:px-12">
        <div className="flex flex-col items-start justify-between gap-6 border-t border-border pt-8 sm:flex-row sm:items-center">
          <p className="font-serif text-lg font-medium text-text">ShiftIQ</p>
          <div className="flex flex-wrap gap-6 text-sm text-muted">
            <Link href="/login" className="hover:text-text">
              Log in
            </Link>
            <Link href="/register" className="hover:text-text">
              Get started
            </Link>
          </div>
          <p className="text-caption text-muted">© ShiftIQ, {new Date().getFullYear()}</p>
        </div>
      </footer>
    </main>
  );
}
