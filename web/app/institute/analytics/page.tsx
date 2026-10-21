"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppHeader } from "@/components/app-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Field } from "@/components/ui/field";
import { Alert } from "@/components/ui/alert";
import { BarStat } from "@/components/ui/bar-stat";
import {
  analyticsApi,
  campaignsApi,
  ApiRequestError,
  AnalyticsDashboard,
  AnalyticsFilterOptions,
  Campaign,
  ReadinessBand,
} from "@/lib/api";

const READINESS_LABELS: Record<ReadinessBand, string> = {
  needs_improvement: "Needs improvement",
  developing: "Developing",
  ready: "Ready",
  excellent: "Excellent",
};

const READINESS_ORDER: ReadinessBand[] = ["needs_improvement", "developing", "ready", "excellent"];

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border border-border bg-white p-4 text-center">
      <p className="font-display text-2xl">{value}</p>
      <p className="mt-1 text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
    </div>
  );
}

export default function AnalyticsPage() {
  const router = useRouter();
  const [data, setData] = useState<AnalyticsDashboard | null>(null);
  const [filterOptions, setFilterOptions] = useState<AnalyticsFilterOptions | null>(null);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [filters, setFilters] = useState({
    campaign_id: "",
    department: "",
    batch: "",
    role: "",
    date_from: "",
    date_to: "",
  });

  async function load(params = filters) {
    setLoading(true);
    setError(null);
    try {
      const dashboard = await analyticsApi.getDashboard(params);
      setData(dashboard);
    } catch (err) {
      if (err instanceof ApiRequestError && err.status === 401) {
        router.push("/institute/login");
        return;
      }
      setError(
        err instanceof ApiRequestError ? err.message : "Couldn't load analytics."
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    Promise.all([
      analyticsApi.getFilterOptions(),
      campaignsApi.list({ per_page: 100 }),
    ]).then(([options, campaignsResult]) => {
      setFilterOptions(options);
      setCampaigns(campaignsResult.items);
    });
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleFilterSubmit(e: FormEvent) {
    e.preventDefault();
    load(filters);
  }

  function handleReset() {
    const cleared = {
      campaign_id: "", department: "", batch: "", role: "", date_from: "", date_to: "",
    };
    setFilters(cleared);
    load(cleared);
  }

  return (
    <div className="min-h-screen">
      <AppHeader />
      <div className="mx-auto max-w-4xl space-y-8 px-6 py-12">
        <h1 className="font-display text-3xl">Analytics</h1>

        {error && <Alert variant="error">{error}</Alert>}

        <form
          onSubmit={handleFilterSubmit}
          className="grid grid-cols-2 gap-4 rounded-md border border-border bg-white p-6 sm:grid-cols-3"
        >
          <Field label="Campaign" htmlFor="f-campaign">
            <Select
              id="f-campaign"
              value={filters.campaign_id}
              onChange={(e) => setFilters((f) => ({ ...f, campaign_id: e.target.value }))}
            >
              <option value="">All campaigns</option>
              {campaigns.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Department" htmlFor="f-dept">
            <Select
              id="f-dept"
              value={filters.department}
              onChange={(e) => setFilters((f) => ({ ...f, department: e.target.value }))}
            >
              <option value="">All departments</option>
              {filterOptions?.departments.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Batch" htmlFor="f-batch">
            <Select
              id="f-batch"
              value={filters.batch}
              onChange={(e) => setFilters((f) => ({ ...f, batch: e.target.value }))}
            >
              <option value="">All batches</option>
              {filterOptions?.batches.map((b) => (
                <option key={b} value={b}>
                  {b}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Role" htmlFor="f-role">
            <Input
              id="f-role"
              placeholder="e.g. Software Developer"
              value={filters.role}
              onChange={(e) => setFilters((f) => ({ ...f, role: e.target.value }))}
            />
          </Field>
          <Field label="From" htmlFor="f-from">
            <Input
              id="f-from"
              type="date"
              value={filters.date_from}
              onChange={(e) => setFilters((f) => ({ ...f, date_from: e.target.value }))}
            />
          </Field>
          <Field label="To" htmlFor="f-to">
            <Input
              id="f-to"
              type="date"
              value={filters.date_to}
              onChange={(e) => setFilters((f) => ({ ...f, date_to: e.target.value }))}
            />
          </Field>
          <div className="col-span-2 flex gap-2 sm:col-span-3">
            <Button type="submit" className="w-auto px-6">
              Apply filters
            </Button>
            <Button type="button" variant="ghost" className="w-auto px-6" onClick={handleReset}>
              Reset
            </Button>
          </div>
        </form>

        {loading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : data ? (
          <div className="space-y-8">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <StatCard label="Students" value={data.total_students} />
              <StatCard label="Assigned" value={data.assigned_interviews} />
              <StatCard label="Started" value={data.started_interviews} />
              <StatCard label="Completed" value={data.completed_interviews} />
              <StatCard label="Completion rate" value={`${data.completion_rate}%`} />
              <StatCard label="Average score" value={data.average_score ?? "—"} />
              <StatCard label="Highest score" value={data.highest_score ?? "—"} />
              <StatCard label="Lowest score" value={data.lowest_score ?? "—"} />
            </div>

            <div className="rounded-md border border-border bg-white p-6">
              <p className="mb-4 text-sm font-medium">Performance by round</p>
              <div className="space-y-3">
                <BarStat label="Technical" value={data.dimension_performance.technical} />
                <BarStat label="Managerial" value={data.dimension_performance.managerial} />
                <BarStat label="HR" value={data.dimension_performance.hr} />
                <BarStat
                  label="Communication"
                  value={data.dimension_performance.communication}
                />
              </div>
            </div>

            <div className="rounded-md border border-border bg-white p-6">
              <p className="mb-4 text-sm font-medium">Readiness distribution</p>
              <div className="space-y-3">
                {READINESS_ORDER.map((band) => (
                  <BarStat
                    key={band}
                    label={READINESS_LABELS[band]}
                    value={data.readiness_distribution[band] ?? 0}
                    max={Math.max(1, data.scored_interviews)}
                    suffix=""
                  />
                ))}
              </div>
              <p className="mt-3 text-xs text-muted-foreground">
                Based on {data.scored_interviews} scored interview
                {data.scored_interviews === 1 ? "" : "s"}.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="rounded-md border border-border bg-white p-6">
                <p className="mb-4 text-sm font-medium">By department</p>
                {data.department_performance.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No data yet.</p>
                ) : (
                  <div className="space-y-3">
                    {data.department_performance.map((d) => (
                      <BarStat key={d.name} label={`${d.name} (${d.count})`} value={d.average_score} />
                    ))}
                  </div>
                )}
              </div>
              <div className="rounded-md border border-border bg-white p-6">
                <p className="mb-4 text-sm font-medium">By batch</p>
                {data.batch_performance.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No data yet.</p>
                ) : (
                  <div className="space-y-3">
                    {data.batch_performance.map((b) => (
                      <BarStat key={b.name} label={`${b.name} (${b.count})`} value={b.average_score} />
                    ))}
                  </div>
                )}
              </div>
            </div>

            <div className="rounded-md border border-border bg-white p-6">
              <p className="mb-4 text-sm font-medium">Most common technical skill gaps</p>
              {data.skill_gaps.length === 0 ? (
                <p className="text-sm text-muted-foreground">No data yet.</p>
              ) : (
                <ul className="space-y-2 text-sm">
                  {data.skill_gaps.map((g) => (
                    <li key={g.gap} className="flex items-center justify-between">
                      <span>{g.gap}</span>
                      <span className="text-muted-foreground">{g.count}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
