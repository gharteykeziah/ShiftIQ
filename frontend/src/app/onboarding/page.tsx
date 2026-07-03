import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { HeroIllustration } from "@/components/illustrations/HeroIllustration";

export default function OnboardingPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-accent-light/40 px-6 py-12">
      <div className="w-full max-w-sm text-center">
        <HeroIllustration className="mx-auto mb-8 h-56 w-56" />
        <h1 className="text-3xl font-bold leading-tight text-text">
          Take control of your shifts and your money
        </h1>
        <p className="mt-3 text-sm text-muted">
          ShiftIQ turns your schedule into a real financial picture — income, expenses, goals, and
          what-if simulations, all in one place.
        </p>

        <div className="mt-8 space-y-3">
          <Link href="/register" className="block">
            <Button size="lg" className="w-full">
              Get Started
            </Button>
          </Link>
          <Link href="/login" className="block">
            <Button variant="ghost" size="lg" className="w-full">
              I already have an account
            </Button>
          </Link>
        </div>
      </div>
    </main>
  );
}
