import { ComingSoonCard } from "@/components/ComingSoonCard";

export default function ExpensesPage() {
  return (
    <div className="mx-auto max-w-4xl p-6 sm:p-10">
      <ComingSoonCard
        title="Expenses"
        description="Add, edit, and remove expenses by category — lands on Days 15-16."
      />
    </div>
  );
}
