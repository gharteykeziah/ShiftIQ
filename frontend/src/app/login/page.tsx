"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);

    // Read from FormData rather than trusting React state alone — Chrome's
    // autofill/password-manager can fill the visible field without firing
    // a React-visible change event, leaving state empty even though the
    // field looks filled. FormData always reflects the real DOM value.
    const data = new FormData(e.currentTarget);
    const emailValue = (data.get("email") as string) ?? email;
    const passwordValue = (data.get("password") as string) ?? password;

    setIsSubmitting(true);
    try {
      await login(emailValue, passwordValue);
      router.push("/dashboard");
    } catch (err) {
      // api.py deliberately returns the same message for a wrong email vs.
      // wrong password (prevents user enumeration) — shown to the user as-is.
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg px-6 py-12">
      <div className="w-full max-w-sm">
        <h1 className="text-3xl font-bold text-text">Log In</h1>
        <p className="mt-2 text-sm text-muted">Welcome back.</p>

        <form onSubmit={handleSubmit} className="mt-8 space-y-4">
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
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />

          {error && (
            <p role="alert" className="text-sm text-danger">
              {error}
            </p>
          )}

          <Button type="submit" size="lg" className="w-full" isLoading={isSubmitting}>
            Log in
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-muted">
          Don&apos;t have an account?{" "}
          <Link href="/register" className="font-semibold text-accent hover:underline">
            Create one
          </Link>
        </p>
      </div>
    </main>
  );
}
