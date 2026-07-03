import { redirect } from "next/navigation";

// The real app shell lands in Days 7-8 — for now, / sends visitors to the
// onboarding flow. /components-preview is still reachable directly by URL.
export default function Home() {
  redirect("/onboarding");
}
