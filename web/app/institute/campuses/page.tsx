"use client";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppHeader } from "@/components/app-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert } from "@/components/ui/alert";
import { ApiRequestError, Campus, campusApi } from "@/lib/api";

export default function CampusesPage() {
  const router = useRouter();
  const [items, setItems] = useState<Campus[]>([]); const [name, setName] = useState(""); const [code, setCode] = useState(""); const [location, setLocation] = useState(""); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  async function load() { try { setItems(await campusApi.list()); } catch (e) { if (e instanceof ApiRequestError && e.status === 401) router.push("/institute/login"); else setError(e instanceof Error ? e.message : "Unable to load campuses."); } }
  useEffect(() => { load(); }, []);
  async function submit(e: FormEvent) { e.preventDefault(); setBusy(true); setError(""); try { await campusApi.create({ name, code: code || undefined, location: location || undefined }); setName(""); setCode(""); setLocation(""); await load(); } catch (e) { setError(e instanceof Error ? e.message : "Unable to create campus."); } finally { setBusy(false); } }
  async function remove(id: string) { if (!confirm("Deactivate this campus?")) return; try { await campusApi.remove(id); await load(); } catch (e) { setError(e instanceof Error ? e.message : "Unable to deactivate campus."); } }
  return <div className="min-h-screen"><AppHeader/><main className="mx-auto max-w-4xl space-y-8 px-6 py-10"><div><h1 className="font-display text-3xl">Campus management</h1><p className="mt-2 text-sm text-muted-foreground">Organize students and campaigns by campus.</p></div>{error && <Alert variant="error">{error}</Alert>}<form onSubmit={submit} className="grid gap-3 rounded-lg border border-border bg-white p-5 md:grid-cols-4"><Input value={name} onChange={e=>setName(e.target.value)} placeholder="Campus name" required/><Input value={code} onChange={e=>setCode(e.target.value)} placeholder="Campus code"/><Input value={location} onChange={e=>setLocation(e.target.value)} placeholder="Location"/><Button type="submit" disabled={busy}>{busy?"Saving…":"Add campus"}</Button></form><section className="space-y-3">{items.length===0?<p className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">No campuses yet. Add your first campus above.</p>:items.map(c=><div key={c.id} className="flex items-center justify-between rounded-lg border border-border bg-white p-4"><div><p className="font-medium">{c.name}</p><p className="text-sm text-muted-foreground">{[c.code,c.location].filter(Boolean).join(" · ") || "No code or location"}</p></div><Button type="button" variant="outline" onClick={()=>remove(c.id)}>Deactivate</Button></div>)}</section></main></div>;
}
