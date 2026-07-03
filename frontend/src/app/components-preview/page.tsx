"use client";

import { useState } from "react";
import { Wallet, TrendingUp, PiggyBank, Receipt, Target } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { Skeleton } from "@/components/ui/Skeleton";
import { IconCard } from "@/components/ui/IconCard";
import { StatCard } from "@/components/ui/StatCard";
import { useToast } from "@/components/ui/Toast";

export default function ComponentsPreview() {
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedGoal, setSelectedGoal] = useState<string | null>(null);
  const { showToast } = useToast();

  return (
    <main className="mx-auto max-w-4xl space-y-10 p-6 sm:p-10">
      <div>
        <h1 className="text-2xl font-bold text-text">ShiftIQ Component Preview</h1>
        <p className="mt-1 text-sm text-muted">
          Days 1&ndash;3 output &mdash; design tokens and base components, before any real page is built.
        </p>
      </div>

      <section>
        <h2 className="mb-3 text-lg font-bold text-text">Buttons</h2>
        <div className="flex flex-wrap gap-3">
          <Button variant="primary">Primary</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="outline">Outline</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="danger">Danger</Button>
          <Button variant="primary" isLoading>
            Loading
          </Button>
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-lg font-bold text-text">Stat cards (Dashboard preview)</h2>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <StatCard label="Balance" value="$1,240.50" icon={Wallet} trend="up" trendLabel="+$85 this week" />
          <StatCard label="Weekly income" value="$412.00" icon={TrendingUp} trend="up" trendLabel="On track" />
          <StatCard label="Weekly expenses" value="$268.00" icon={Receipt} trend="down" trendLabel="-12% vs last week" />
          <StatCard label="Savings rate" value="35%" icon={PiggyBank} trend="up" trendLabel="Strong" />
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-lg font-bold text-text">Goal picker (icon cards)</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <IconCard
            icon={Target}
            label="Weeks to Goal"
            selected={selectedGoal === "weeks"}
            onClick={() => setSelectedGoal("weeks")}
          />
          <IconCard
            icon={TrendingUp}
            label="Goal Progress"
            selected={selectedGoal === "progress"}
            onClick={() => setSelectedGoal("progress")}
          />
          <IconCard
            icon={PiggyBank}
            label="Emergency Fund"
            selected={selectedGoal === "emergency"}
            onClick={() => setSelectedGoal("emergency")}
          />
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-lg font-bold text-text">Card + form</h2>
        <Card className="max-w-sm">
          <CardHeader>
            <CardTitle>Add a job</CardTitle>
            <CardDescription>Matches the /api/jobs schema.</CardDescription>
          </CardHeader>
          <div className="space-y-3">
            <Input label="Job name" placeholder="Coffee shop" />
            <Input label="Amount" placeholder="15.50" hint="Per the selected frequency" />
            <Button className="w-full" onClick={() => showToast("Job added — see how insights appear.", "success")}>
              Save job
            </Button>
          </div>
        </Card>
      </section>

      <section>
        <h2 className="mb-3 text-lg font-bold text-text">Skeleton (loading state)</h2>
        <div className="space-y-2">
          <Skeleton className="h-5 w-2/3" />
          <Skeleton className="h-5 w-1/2" />
          <Skeleton className="h-24 w-full" />
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-lg font-bold text-text">Modal + Toast</h2>
        <div className="flex gap-3">
          <Button onClick={() => setModalOpen(true)}>Open modal</Button>
          <Button
            variant="outline"
            onClick={() => showToast("You just saved $12/mo by trimming a subscription.", "info")}
          >
            Trigger insight toast
          </Button>
        </div>
        <Modal open={modalOpen} onClose={() => setModalOpen(false)} title="Delete this shift?">
          <p className="mb-4 text-sm text-muted">This can&apos;t be undone.</p>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="danger" onClick={() => setModalOpen(false)}>
              Delete
            </Button>
          </div>
        </Modal>
      </section>
    </main>
  );
}
