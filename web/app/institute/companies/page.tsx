"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AppHeader } from "@/components/app-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert } from "@/components/ui/alert";
import { ApiRequestError, Company, companiesApi } from "@/lib/api";

export default function CompaniesPage() {
  const router = useRouter();
  const [items, setItems] = useState<Company[]>([]);
  const [name, setName] = useState("");
  const [website, setWebsite] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  async function load() {
    setError("");
    try {
      setItems(await companiesApi.list());
    } catch (e) {
      if (e instanceof ApiRequestError && e.status === 401) router.push("/institute/login");
      else setError(e instanceof Error ? e.message : "Unable to load companies.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);

  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError("");
    try {
      await companiesApi.create({ name: name.trim(), website: website.trim() || undefined, description: description.trim() || undefined });
      setName(""); setWebsite(""); setDescription(""); await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to create company.");
    } finally { setBusy(false); }
  }

  return <div className="min-h-screen"><AppHeader/><main className="mx-auto max-w-4xl space-y-8 px-6 py-10">
    <div className="flex flex-wrap items-end justify-between gap-3"><div><h1 className="font-display text-3xl">Company catalog</h1><p className="mt-2 text-sm text-muted-foreground">Create company profiles and use them in interview campaigns and company-specific questions.</p></div><Link className="text-sm underline" href="/institute/campaigns">Go to campaigns</Link></div>
    {error && <Alert variant="error">{error}</Alert>}
    <form onSubmit={submit} className="space-y-3 rounded-lg border border-border bg-white p-5">
      <h2 className="font-medium">Add a company</h2>
      <div className="grid gap-3 md:grid-cols-2"><Input value={name} onChange={e=>setName(e.target.value)} placeholder="Company name" required maxLength={180}/><Input value={website} onChange={e=>setWebsite(e.target.value)} placeholder="Website (optional)" type="url"/></div>
      <textarea value={description} onChange={e=>setDescription(e.target.value)} placeholder="Company or hiring context (optional)" maxLength={4000} className="min-h-24 w-full rounded-md border border-border p-3 text-sm"/>
      <Button type="submit" disabled={busy} className="md:max-w-48">{busy ? "Saving…" : "Add company"}</Button>
    </form>
    <section className="space-y-3"><h2 className="font-medium">Available companies</h2>{loading ? <p className="text-sm text-muted-foreground">Loading companies…</p> : items.length === 0 ? <p className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">No companies yet. Add one above, then select it when creating a campaign.</p> : items.map(c=><article key={c.id} className="rounded-lg border border-border bg-white p-4"><div className="font-medium">{c.name}</div>{c.website && <a className="text-sm underline" href={c.website} target="_blank" rel="noreferrer">{c.website}</a>}{c.description && <p className="mt-2 whitespace-pre-wrap text-sm text-muted-foreground">{c.description}</p>}</article>)}</section>
  </main></div>;
}
