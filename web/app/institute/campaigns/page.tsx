"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AppHeader } from "@/components/app-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Field } from "@/components/ui/field";
import { Alert } from "@/components/ui/alert";
import { StatusBadge } from "@/components/ui/badge";
import {
  campaignsApi,
  interviewTemplatesApi,
  companiesApi, campusApi,
  Company, Campus,
  ApiRequestError,
  Campaign,
  InterviewTemplate,
} from "@/lib/api";

const emptyForm = {
  name: "",
  role: "",
  experience_level: "",
  department: "",
  batch: "",
  difficulty: "medium",
  interview_template_id: "",
  question_source: "ai",
  company_id: "",
  campus_id: "",
  job_description: "",
};

export default function CampaignsPage() {
  const router = useRouter();
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [templates, setTemplates] = useState<InterviewTemplate[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [campuses, setCampuses] = useState<Campus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const [campaignsResult, templatesResult, companyResult, campusResult] = await Promise.all([
        campaignsApi.list({ per_page: 50 }),
        interviewTemplatesApi.list({ per_page: 50 }),
        companiesApi.list(), campusApi.list(),
      ]);
      setCampaigns(campaignsResult.items);
      setTemplates(templatesResult.items);
      setCompanies(companyResult); setCampuses(campusResult);
    } catch (err) {
      if (err instanceof ApiRequestError && err.status === 401) {
        router.push("/institute/login");
        return;
      }
      setError("Couldn't load campaigns.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setCreateError(null);
    setCreating(true);
    try {
      const campaign = await campaignsApi.create({
        name: form.name,
        role: form.role,
        experience_level: form.experience_level || undefined,
        department: form.department || undefined,
        batch: form.batch || undefined,
        difficulty: form.difficulty,
        interview_template_id: form.interview_template_id || undefined,
        question_source: form.question_source,
        company_id: form.company_id || undefined,
        campus_id: form.campus_id || undefined,
        job_description: form.job_description || undefined,
      });
      router.push(`/institute/campaigns/${campaign.id}`);
    } catch (err) {
      setCreateError(
        err instanceof ApiRequestError ? err.message : "Couldn't create campaign."
      );
      setCreating(false);
    }
  }

  return (
    <div className="min-h-screen">
      <AppHeader />
      <div className="mx-auto max-w-3xl space-y-6 px-6 py-12">
        <div className="flex items-center justify-between">
          <h1 className="font-display text-3xl">Campaigns</h1>
          <Button
            type="button"
            className="w-auto px-4"
            onClick={() => setShowForm((v) => !v)}
          >
            {showForm ? "Cancel" : "New campaign"}
          </Button>
        </div>

        {error && <Alert variant="error">{error}</Alert>}

        {showForm && (
          <form
            onSubmit={handleCreate}
            className="space-y-4 rounded-md border border-border bg-white p-6"
          >
            {createError && <Alert variant="error">{createError}</Alert>}
            {templates.length > 0 && (
              <Field label="Start from a template (optional)" htmlFor="c-template">
                <Select
                  id="c-template"
                  value={form.interview_template_id}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, interview_template_id: e.target.value }))
                  }
                >
                  <option value="">No template — use defaults</option>
                  {templates.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name}
                      {t.is_default ? " (default)" : ""}
                    </option>
                  ))}
                </Select>
              </Field>
            )}
            <div className="grid grid-cols-2 gap-4">
              <Field label="Campaign name" htmlFor="c-name">
                <Input
                  id="c-name"
                  required
                  placeholder="Software Developer Mock Interview - 2027"
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                />
              </Field>
              <Field label="Target role" htmlFor="c-role">
                <Input
                  id="c-role"
                  required
                  placeholder="Software Developer"
                  value={form.role}
                  onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}
                />
              </Field>
              <Field label="Experience level" htmlFor="c-exp">
                <Input
                  id="c-exp"
                  placeholder="Fresher"
                  value={form.experience_level}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, experience_level: e.target.value }))
                  }
                />
              </Field>
              <Field label="Difficulty" htmlFor="c-diff">
                <Select
                  id="c-diff"
                  value={form.difficulty}
                  onChange={(e) => setForm((f) => ({ ...f, difficulty: e.target.value }))}
                >
                  <option value="easy">Easy</option>
                  <option value="medium">Medium</option>
                  <option value="hard">Hard</option>
                </Select>
              </Field>
              <Field label="Department" htmlFor="c-dept">
                <Input
                  id="c-dept"
                  value={form.department}
                  onChange={(e) => setForm((f) => ({ ...f, department: e.target.value }))}
                />
              </Field>
              <Field label="Batch" htmlFor="c-batch">
                <Input
                  id="c-batch"
                  value={form.batch}
                  onChange={(e) => setForm((f) => ({ ...f, batch: e.target.value }))}
                />
              </Field>
              <Field label="Question source" htmlFor="c-source">
                <Select id="c-source" value={form.question_source} onChange={(e) => setForm((f) => ({ ...f, question_source: e.target.value }))}>
                  <option value="ai">AI generated</option><option value="custom">Institute question bank</option><option value="mixed">Mix custom + AI</option>
                </Select>
              </Field>
              <Field label="Company (optional)" htmlFor="c-company">
                <Select id="c-company" value={form.company_id} onChange={(e) => setForm((f) => ({ ...f, company_id: e.target.value }))}>
                  <option value="">No company selected</option>{companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </Select>
              </Field>
              <Field label="Campus (optional)" htmlFor="c-campus">
                <Select id="c-campus" value={form.campus_id} onChange={(e) => setForm((f) => ({ ...f, campus_id: e.target.value }))}>
                  <option value="">All campuses / not specified</option>{campuses.filter((c) => c.is_active).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </Select>
              </Field>
            </div>
            <Field label="Job description (optional)" htmlFor="c-job-description">
              <textarea id="c-job-description" className="min-h-24 w-full rounded-md border border-border p-3 text-sm" value={form.job_description} onChange={(e) => setForm((f) => ({ ...f, job_description: e.target.value }))} placeholder="Paste the role requirements to guide AI-generated questions." />
            </Field>
            <Button type="submit" loading={creating} className="w-auto px-6">
              Create campaign
            </Button>
          </form>
        )}

        <div className="overflow-hidden rounded-md border border-border bg-white">
          <table className="w-full text-sm">
            <thead className="border-b border-border bg-muted text-left text-muted-foreground">
              <tr>
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Role</th>
                <th className="px-4 py-3 font-medium">Difficulty</th>
                <th className="px-4 py-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-muted-foreground">
                    Loading…
                  </td>
                </tr>
              ) : campaigns.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-muted-foreground">
                    No campaigns yet.
                  </td>
                </tr>
              ) : (
                campaigns.map((c) => (
                  <tr key={c.id} className="border-b border-border last:border-0">
                    <td className="px-4 py-3">
                      <Link
                        href={`/institute/campaigns/${c.id}`}
                        className="font-medium text-foreground hover:text-primary"
                      >
                        {c.name}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">{c.role}</td>
                    <td className="px-4 py-3 capitalize text-muted-foreground">
                      {c.difficulty}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={c.status} />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
