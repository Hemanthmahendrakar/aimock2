"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { AuthShell } from "@/components/auth-shell";
import { Alert } from "@/components/ui/alert";
import { authApi, ApiRequestError } from "@/lib/api";

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [state, setState] = useState<"pending" | "success" | "error">("pending");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!token) {
      setState("error");
      setMessage("This verification link is missing its token.");
      return;
    }
    authApi
      .verifyEmail(token)
      .then(() => setState("success"))
      .catch((err) => {
        setState("error");
        setMessage(
          err instanceof ApiRequestError
            ? err.message
            : "Couldn't reach the server. Check your connection and try again."
        );
      });
  }, [token]);

  return (
    <AuthShell title="Email verification">
      {state === "pending" && <Alert variant="info">Verifying your email…</Alert>}
      {state === "success" && (
        <>
          <Alert variant="success">
            Your email is verified. Your institute account is now active.
          </Alert>
          <Link href="/institute/login" className="text-sm text-primary hover:underline">
            Log in
          </Link>
        </>
      )}
      {state === "error" && (
        <>
          <Alert variant="error">{message}</Alert>
          <Link href="/institute/login" className="text-sm text-primary hover:underline">
            Back to login
          </Link>
        </>
      )}
    </AuthShell>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={null}>
      <VerifyEmailContent />
    </Suspense>
  );
}
