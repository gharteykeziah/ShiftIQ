import { ComingSoonCard } from "@/components/ComingSoonCard";

export default function GoalsPage() {
  return (
    <div className="mx-auto max-w-4xl p-6 sm:p-10">
      <ComingSoonCard
        title="Goals"
        description="Weeks-to-goal, goal progress, and emergency fund as selectable icon cards — lands on Days 24-25."
      />
    </div>
  );
}
