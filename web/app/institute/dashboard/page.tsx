"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, BarChart3, BriefcaseBusiness, FileText, GraduationCap, Plus, Users } from "lucide-react";
import { AppHeader } from "@/components/app-header";
import { Alert } from "@/components/ui/alert";
import { authApi, dashboardApi, ApiRequestError, CurrentUser, InstituteDashboard } from "@/lib/api";

const statCards = [
  { key: "total_students", label: "Students", icon: Users, href: "/institute/students" },
  { key: "total_campaigns", label: "Campaigns", icon: BriefcaseBusiness, href: "/institute/campaigns" },
  { key: "assigned_interviews", label: "Assigned interviews", icon: GraduationCap, href: "/institute/campaigns" },
  { key: "reports_ready", label: "Reports ready", icon: FileText, href: "/institute/analytics" },
] as const;

function titleCase(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [dashboard, setDashboard] = useState<InstituteDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [me, summary] = await Promise.all([authApi.me(), dashboardApi.get()]);
        setUser(me);
        setDashboard(summary);
      } catch (err) {
        if (err instanceof ApiRequestError && err.status === 401) {
          router.push("/institute/login");
          return;
        }
        setError("Couldn't load your dashboard. Check the API and try again.");
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, [router]);

  if (loading) {
    return <div className="flex min-h-screen items-center justify-center"><p className="text-sm text-muted-foreground">Loading dashboard…</p></div>;
  }

  return (
    <div className="min-h-screen bg-muted/30">
      <AppHeader />
      <main className="mx-auto max-w-6xl space-y-8 px-5 py-8 md:px-8">
        {error && <Alert variant="error">{error}</Alert>}
        <section className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
          <div>
            <p className="text-sm font-medium text-primary">Institute workspace</p>
            <h1 className="mt-1 font-display text-3xl font-semibold">Welcome{user ? `, ${user.full_name}` : " back"}</h1>
            <p className="mt-2 text-sm text-muted-foreground">Track student practice, interview campaigns, and results from one place.</p>
          </div>
          <Link href="/institute/campaigns" className="inline-flex items-center justify-center gap-2 rounded-md bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground hover:opacity-90">
            <Plus size={16} /> Create campaign
          </Link>
        </section>

        {dashboard && <>
          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {statCards.map(({ key, label, icon: Icon, href }) => (
              <Link key={key} href={href} className="group rounded-xl border border-border bg-background p-5 transition hover:-translate-y-0.5 hover:shadow-sm">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">{label}</span>
                  <Icon size={18} className="text-muted-foreground" />
                </div>
                <p className="mt-4 text-3xl font-semibold tabular-nums">{dashboard.stats[key].toLocaleString()}</p>
                <span className="mt-3 inline-flex items-center gap-1 text-xs text-muted-foreground group-hover:text-foreground">View details <ArrowRight size={13} /></span>
              </Link>
            ))}
          </section>

          <section className="grid gap-5 lg:grid-cols-[1.5fr_1fr]">
            <div className="rounded-xl border border-border bg-background p-5">
              <div className="flex items-center justify-between gap-3">
                <div><h2 className="font-semibold">Recent campaigns</h2><p className="mt-1 text-sm text-muted-foreground">Your latest interview drives</p></div>
                <Link href="/institute/campaigns" className="text-sm font-medium text-primary hover:underline">View all</Link>
              </div>
              {dashboard.recent_campaigns.length === 0 ? (
                <div className="mt-6 rounded-lg border border-dashed border-border px-5 py-8 text-center">
                  <BriefcaseBusiness className="mx-auto text-muted-foreground" size={24} />
                  <p className="mt-3 font-medium">No campaigns yet</p>
                  <p className="mt-1 text-sm text-muted-foreground">Create your first campaign to invite students to practice.</p>
                  <Link href="/institute/campaigns" className="mt-4 inline-flex items-center gap-2 text-sm font-medium text-primary">Create campaign <ArrowRight size={14} /></Link>
                </div>
              ) : (
                <div className="mt-4 divide-y divide-border">
                  {dashboard.recent_campaigns.map((campaign) => (
                    <Link key={campaign.id} href={`/institute/campaigns/${campaign.id}`} className="flex items-center justify-between gap-4 py-4 first:pt-2 last:pb-0">
                      <div className="min-w-0"><p className="truncate text-sm font-medium">{campaign.name}</p><p className="mt-1 text-xs text-muted-foreground">{campaign.role}</p></div>
                      <span className="shrink-0 rounded-full bg-muted px-2.5 py-1 text-xs capitalize">{titleCase(campaign.status)}</span>
                    </Link>
                  ))}
                </div>
              )}
            </div>

            <div className="rounded-xl border border-border bg-background p-5">
              <div className="flex items-center gap-2"><BarChart3 size={18} /><h2 className="font-semibold">Interview progress</h2></div>
              <p className="mt-1 text-sm text-muted-foreground">Completion across assigned interviews</p>
              <div className="mt-6 flex items-end justify-between gap-3"><span className="text-4xl font-semibold tabular-nums">{dashboard.stats.completion_rate}%</span><span className="text-sm text-muted-foreground">{dashboard.stats.completed_interviews} of {dashboard.stats.assigned_interviews}</span></div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted"><div className="h-full rounded-full bg-primary transition-all" style={{ width: `${Math.min(100, Math.max(0, dashboard.stats.completion_rate))}%` }} /></div>
              <div className="mt-6 grid grid-cols-2 gap-3">
                <div className="rounded-lg bg-muted/60 p-3"><p className="text-xs text-muted-foreground">Active campaigns</p><p className="mt-1 text-xl font-semibold">{dashboard.stats.active_campaigns}</p></div>
                <div className="rounded-lg bg-muted/60 p-3"><p className="text-xs text-muted-foreground">Completed interviews</p><p className="mt-1 text-xl font-semibold">{dashboard.stats.completed_interviews}</p></div>
              </div>
              <Link href="/institute/analytics" className="mt-5 inline-flex items-center gap-2 text-sm font-medium text-primary">Open analytics <ArrowRight size={14} /></Link>
            </div>
          </section>
          <p className="text-xs text-muted-foreground">Signed in as {user?.email} · Institute ID {dashboard.institute_id}</p>
        </>}
      </main>
    </div>
  );
}
