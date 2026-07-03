import { redirect } from "next/navigation";

// Auth and the real pages don't exist yet (Days 4+) — send / to the
// component preview so there's something meaningful to look at for now.
export default function Home() {
  redirect("/components-preview");
}
