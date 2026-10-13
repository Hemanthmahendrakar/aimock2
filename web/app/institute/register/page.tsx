"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { AuthShell } from "@/components/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/ui/field";
import { Alert } from "@/components/ui/alert";
import { authApi, ApiRequestError } from "@/lib/api";
import { passwordIssue } from "@/lib/validation";

type FormState = {
  instituteName: string;
  instituteEmail: string;
  adminFullName: string;
  adminEmail: string;
  password: string;
};

const initialState: FormState = {
  instituteName: "",
  instituteEmail: "",
  adminFullName: "",
  adminEmail: "",
  password: "",
};

export default function RegisterPage() {
  const [form, setForm] = useState<FormState>(initialState);
  const [loading, setLoading] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [passwordHint, setPasswordHint] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setFormError(null);

    const issue = passwordIssue(form.password);
    if (issue) {
      setPasswordHint(issue);
      return;
    }

    setLoading(true);
    try {
      await authApi.register({
        institute_name: form.instituteName,
        institute_email: form.instituteEmail,
        admin_full_name: form.adminFullName,
        admin_email: form.adminEmail,
        password: form.password,
      });
      setSubmitted(true);
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

  if (submitted) {
    return (
      <AuthShell title="Check your email">
        <Alert variant="success">
          We sent a verification link to <strong>{form.adminEmail}</strong>.
          Verify your email to activate {form.instituteName || "your institute"}
          &rsquo;s account.
        </Alert>
        <Link href="/institute/login" className="text-sm text-primary hover:underline">
          Back to login
        </Link>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="Register your institute"
      subtitle="Set up mock interviews for your students in minutes."
    >
      <form onSubmit={handleSubmit} className="space-y-5" noValidate>
        {formError && <Alert variant="error">{formError}</Alert>}

        <Field label="Institute name" htmlFor="instituteName">
          <Input
            id="instituteName"
            required
            value={form.instituteName}
            onChange={(e) => update("instituteName", e.target.value)}
          />
        </Field>

        <Field label="Institute email" htmlFor="instituteEmail">
          <Input
            id="instituteEmail"
            type="email"
            required
            placeholder="admissions@yourinstitute.edu"
            value={form.instituteEmail}
            onChange={(e) => update("instituteEmail", e.target.value)}
          />
        </Field>

        <Field label="Your full name" htmlFor="adminFullName">
          <Input
            id="adminFullName"
            required
            value={form.adminFullName}
            onChange={(e) => update("adminFullName", e.target.value)}
          />
        </Field>

        <Field label="Your email" htmlFor="adminEmail">
          <Input
            id="adminEmail"
            type="email"
            required
            value={form.adminEmail}
            onChange={(e) => update("adminEmail", e.target.value)}
          />
        </Field>

        <Field
          label="Password"
          htmlFor="password"
          error={passwordHint}
        >
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            required
            value={form.password}
            onChange={(e) => {
              update("password", e.target.value);
              setPasswordHint(null);
            }}
          />
          <p className="text-xs text-muted-foreground">
            At least 10 characters, with a letter and a digit.
          </p>
        </Field>

        <Button type="submit" loading={loading}>
          Create institute account
        </Button>
      </form>

      <p className="text-sm text-muted-foreground">
        Already registered?{" "}
        <Link href="/institute/login" className="text-primary hover:underline">
          Log in
        </Link>
      </p>
    </AuthShell>
  );
}
