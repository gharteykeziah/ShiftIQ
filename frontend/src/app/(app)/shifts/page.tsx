import { ComingSoonCard } from "@/components/ComingSoonCard";

export default function ShiftsPage() {
  return (
    <div className="mx-auto max-w-4xl p-6 sm:p-10">
      <ComingSoonCard
        title="Shifts"
        description="Shift CRUD with day filtering, plus the max-hours optimizer — the biggest page, lands on Days 17-20."
      />
    </div>
  );
}
