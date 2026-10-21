"use client";

import { FormEvent, Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { AuthShell } from "@/components/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/ui/field";
import { Alert } from "@/components/ui/alert";
import { authApi, ApiRequestError } from "@/lib/api";
import { passwordIssue } from "@/lib/validation";

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";

  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [passwordHint, setPasswordHint] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setFormError(null);

    const issue = passwordIssue(password);
    if (issue) {
      setPasswordHint(issue);
      return;
    }

    setLoading(true);
    try {
      await authApi.resetPassword({ token, new_password: password });
      router.push("/institute/login");
    } catch (err) {
      if (err instanceof ApiRequestError) {
        setFormError(err.message);
      } else {
        setFormError("Couldn't reach the server. Check your connection and try again.");
      }
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return (
      <AuthShell title="Invalid link">
        <Alert variant="error">
          This password reset link is missing its token. Request a new one.
        </Alert>
        <Link href="/institute/forgot-password" className="text-sm text-primary hover:underline">
          Request a new link
        </Link>
      </AuthShell>
    );
  }

  return (
    <AuthShell title="Set a new password">
      <form onSubmit={handleSubmit} className="space-y-5" noValidate>
        {formError && <Alert variant="error">{formError}</Alert>}

        <Field label="New password" htmlFor="password" error={passwordHint}>
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            required
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              setPasswordHint(null);
            }}
          />
          <p className="text-xs text-muted-foreground">
            At least 10 characters, with a letter and a digit.
          </p>
        </Field>

        <Button type="submit" loading={loading}>
          Reset password
        </Button>
      </form>
    </AuthShell>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={null}>
      <ResetPasswordForm />
    </Suspense>
  );
}
