"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card } from "@/components/ui/Card";

export default function RegisterPage() {
  const { register } = useAuth();
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);

    // Read the actual submitted values from the DOM (via FormData) instead
    // of trusting React state alone. Chrome's autofill/password-manager
    // sometimes fills the visible input without firing a React-visible
    // change event, so `email`/`password` state can silently stay empty
    // even though the field looks filled — which made this form reject a
    // valid autofilled password as "too short" and then blank the fields
    // on re-render. FormData always reflects the real DOM value.
    const data = new FormData(e.currentTarget);
    const emailValue = (data.get("email") as string) ?? email;
    const passwordValue = (data.get("password") as string) ?? password;
    const confirmValue = (data.get("confirmPassword") as string) ?? confirmPassword;

    if (passwordValue.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (passwordValue !== confirmValue) {
      setError("Passwords don't match.");
      return;
    }

    setIsSubmitting(true);
    try {
      await register(emailValue, passwordValue);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg px-6 py-12">
      <div className="w-full max-w-sm">
        <h1 className="text-3xl font-bold text-text">Create your account</h1>
        <p className="mt-2 text-sm text-muted">Start tracking your shifts and finances in one place.</p>

        {/* Inputs use a light grey fill (bg-bg) designed to sit on a white
            card — placed directly on this page's own grey background they
            were invisible (grey-on-grey, no visible field outline). Wrapping
            the form in a Card restores the contrast, matching every other
            form in the app. */}
        <Card className="mt-8">
          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="Email address"
              name="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <Input
              label="Password"
              name="password"
              type="password"
              autoComplete="new-password"
              required
              hint="At least 8 characters"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <Input
              label="Confirm password"
              name="confirmPassword"
              type="password"
              autoComplete="new-password"
              required
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
            />

            {error && (
              <p role="alert" className="text-sm text-danger">
                {error}
              </p>
            )}

            <Button type="submit" size="lg" className="w-full" isLoading={isSubmitting}>
              Create account
            </Button>
          </form>
        </Card>

        <p className="mt-6 text-center text-sm text-muted">
          Already have an account?{" "}
          <Link href="/login" className="font-semibold text-accent hover:underline">
            Log in
          </Link>
        </p>
      </div>
    </main>
  );
}
