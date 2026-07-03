import { redirect } from "next/navigation";

// Superseded by the (app) route group's real shell, added Days 7-8
// (/dashboard, /jobs, /shifts, /expenses, /simulation, /goals). Kept as a
// redirect rather than removed, since files in this project can't be
// deleted once written.
export default function LegacyAppRedirect() {
  redirect("/dashboard");
}
