import { ComingSoonCard } from "@/components/ComingSoonCard";

export default function JobsPage() {
  return (
    <div className="mx-auto max-w-4xl p-6 sm:p-10">
      <ComingSoonCard
        title="Jobs"
        description="Add, edit, and remove jobs, with weekly income calculated per job — lands on Days 12-14."
      />
    </div>
  );
}
