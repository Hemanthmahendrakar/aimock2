"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppHeader } from "@/components/app-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/ui/field";
import { Alert } from "@/components/ui/alert";
import { instituteApi, ApiRequestError } from "@/lib/api";

const HEX_RE = /^#(?:[0-9a-fA-F]{3}){1,2}$/;

export default function BrandingSettingsPage() {
  const router = useRouter();
  const [primaryColor, setPrimaryColor] = useState("#1F6F5C");
  const [secondaryColor, setSecondaryColor] = useState("#E2A73B");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    instituteApi
      .getProfile()
      .then((p) => {
        if (p.branding.primary_color) setPrimaryColor(p.branding.primary_color);
        if (p.branding.secondary_color) setSecondaryColor(p.branding.secondary_color);
      })
      .catch((err) => {
        if (err instanceof ApiRequestError && err.status === 401) {
          router.push("/institute/login");
        }
      })
      .finally(() => setLoading(false));
  }, [router]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSaved(false);

    if (!HEX_RE.test(primaryColor) || !HEX_RE.test(secondaryColor)) {
      setError("Colors must be valid hex codes, like #1F6F5C.");
      return;
    }

    setSaving(true);
    try {
      await instituteApi.updateBranding({
        primary_color: primaryColor,
        secondary_color: secondaryColor,
      });
      setSaved(true);
    } catch (err) {
      setError(
        err instanceof ApiRequestError ? err.message : "Couldn't save branding."
      );
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-muted-foreground">Loading…</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <AppHeader />
      <div className="mx-auto max-w-2xl space-y-8 px-6 py-12">
        <div>
          <h1 className="font-display text-3xl">Branding</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            These colors will apply to the student interview experience in a
            later phase.
          </p>
        </div>

        {error && <Alert variant="error">{error}</Alert>}
        {saved && <Alert variant="success">Branding saved.</Alert>}

        <form onSubmit={handleSubmit} className="space-y-5">
          <Field label="Primary color" htmlFor="primary_color">
            <div className="flex items-center gap-3">
              <input
                type="color"
                value={primaryColor}
                onChange={(e) => setPrimaryColor(e.target.value)}
                className="h-11 w-14 cursor-pointer rounded-md border border-border bg-white"
                aria-label="Primary color picker"
              />
              <Input
                id="primary_color"
                value={primaryColor}
                onChange={(e) => setPrimaryColor(e.target.value)}
              />
            </div>
          </Field>

          <Field label="Secondary color" htmlFor="secondary_color">
            <div className="flex items-center gap-3">
              <input
                type="color"
                value={secondaryColor}
                onChange={(e) => setSecondaryColor(e.target.value)}
                className="h-11 w-14 cursor-pointer rounded-md border border-border bg-white"
                aria-label="Secondary color picker"
              />
              <Input
                id="secondary_color"
                value={secondaryColor}
                onChange={(e) => setSecondaryColor(e.target.value)}
              />
            </div>
          </Field>

          <Button type="submit" loading={saving} className="w-auto px-6">
            Save branding
          </Button>
        </form>
      </div>
    </div>
  );
}
