import { ComingSoonCard } from "@/components/ComingSoonCard";

export default function DashboardPage() {
  return (
    <div className="mx-auto max-w-4xl p-6 sm:p-10">
      <ComingSoonCard
        title="Dashboard"
        description="Balance and weekly income/expense stat cards, insights as friendly callouts, and the balance projection chart land on Days 9-11."
      />
    </div>
  );
}
