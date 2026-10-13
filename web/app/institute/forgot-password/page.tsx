"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { AuthShell } from "@/components/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/ui/field";
import { Alert } from "@/components/ui/alert";
import { authApi } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await authApi.forgotPassword(email);
    } finally {
      // Always show the same confirmation, whether or not the email
      // exists — the API deliberately doesn't reveal that either.
      setSent(true);
      setLoading(false);
    }
  }

  if (sent) {
    return (
      <AuthShell title="Check your email">
        <Alert variant="success">
          If <strong>{email}</strong> is registered, we&rsquo;ve sent a link to
          reset the password.
        </Alert>
        <Link href="/institute/login" className="text-sm text-primary hover:underline">
          Back to login
        </Link>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="Reset your password"
      subtitle="We'll email you a link to set a new one."
    >
      <form onSubmit={handleSubmit} className="space-y-5" noValidate>
        <Field label="Work email" htmlFor="email">
          <Input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </Field>

        <Button type="submit" loading={loading}>
          Send reset link
        </Button>
      </form>

      <Link href="/institute/login" className="text-sm text-primary hover:underline">
        Back to login
      </Link>
    </AuthShell>
  );
}
