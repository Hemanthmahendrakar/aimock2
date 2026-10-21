"use client";

import { ChangeEvent, FormEvent, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AppHeader } from "@/components/app-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Field } from "@/components/ui/field";
import { Alert } from "@/components/ui/alert";
import { instituteApi, ApiRequestError, InstituteProfile } from "@/lib/api";

export default function InstituteProfilePage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [profile, setProfile] = useState<InstituteProfile | null>(null);
  const [form, setForm] = useState({ name: "", phone: "", address: "", website: "" });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    instituteApi
      .getProfile()
      .then((p) => {
        setProfile(p);
        setForm({
          name: p.name,
          phone: p.phone ?? "",
          address: p.address ?? "",
          website: p.website ?? "",
        });
      })
      .catch((err) => {
        if (err instanceof ApiRequestError && err.status === 401) {
          router.push("/institute/login");
          return;
        }
        setError("Couldn't load your institute's profile.");
      })
      .finally(() => setLoading(false));
  }, [router]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSaved(false);
    setSaving(true);
    try {
      const updated = await instituteApi.updateProfile(form);
      setProfile(updated);
      setSaved(true);
    } catch (err) {
      setError(
        err instanceof ApiRequestError ? err.message : "Couldn't save your changes."
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleLogoChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setUploadingLogo(true);
    try {
      const updated = await instituteApi.uploadLogo(file);
      setProfile(updated);
    } catch (err) {
      setError(
        err instanceof ApiRequestError ? err.message : "Couldn't upload the logo."
      );
    } finally {
      setUploadingLogo(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function handleLogoRemove() {
    setError(null);
    try {
      const updated = await instituteApi.deleteLogo();
      setProfile(updated);
    } catch (err) {
      setError(
        err instanceof ApiRequestError ? err.message : "Couldn't remove the logo."
      );
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
        <h1 className="font-display text-3xl">Institute profile</h1>

        {error && <Alert variant="error">{error}</Alert>}
        {saved && <Alert variant="success">Changes saved.</Alert>}

        <div className="rounded-md border border-border bg-white p-6">
          <p className="mb-3 text-sm font-medium">Logo</p>
          <div className="flex items-center gap-4">
            <div className="flex h-16 w-16 items-center justify-center overflow-hidden rounded-md border border-border bg-muted">
              {profile?.logo_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={profile.logo_url} alt="Institute logo" className="h-full w-full object-cover" />
              ) : (
                <span className="text-xs text-muted-foreground">No logo</span>
              )}
            </div>
            <div className="flex gap-2">
              <input
                ref={fileInputRef}
                type="file"
                accept="image/png,image/jpeg,image/webp,image/svg+xml"
                onChange={handleLogoChange}
                className="hidden"
                id="logo-upload"
              />
              <Button
                type="button"
                variant="ghost"
                className="w-auto px-4"
                disabled={uploadingLogo}
                onClick={() => fileInputRef.current?.click()}
              >
                {uploadingLogo ? "Uploading…" : "Upload logo"}
              </Button>
              {profile?.logo_url && (
                <Button
                  type="button"
                  variant="ghost"
                  className="w-auto px-4 text-destructive"
                  onClick={handleLogoRemove}
                >
                  Remove
                </Button>
              )}
            </div>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            PNG, JPEG, WEBP, or SVG. Up to 2MB.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <Field label="Institute name" htmlFor="name">
            <Input
              id="name"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              required
            />
          </Field>

          <Field label="Phone" htmlFor="phone">
            <Input
              id="phone"
              value={form.phone}
              onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
            />
          </Field>

          <Field label="Address" htmlFor="address">
            <Textarea
              id="address"
              value={form.address}
              onChange={(e) => setForm((f) => ({ ...f, address: e.target.value }))}
            />
          </Field>

          <Field label="Website" htmlFor="website">
            <Input
              id="website"
              placeholder="https://yourinstitute.edu"
              value={form.website}
              onChange={(e) => setForm((f) => ({ ...f, website: e.target.value }))}
            />
          </Field>

          <Button type="submit" loading={saving} className="w-auto px-6">
            Save changes
          </Button>
        </form>
      </div>
    </div>
  );
}
