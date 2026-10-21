"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { AppHeader } from "@/components/app-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert } from "@/components/ui/alert";
import { StatusBadge } from "@/components/ui/badge";
import {
  campaignsApi,
  studentsApi,
  instituteInterviewsApi,
  ApiRequestError,
  Campaign,
  Student,
  InterviewSummary,
} from "@/lib/api";

const INTERVIEW_STATUS_LABEL: Record<string, string> = {
  created: "Invited",
  ready: "Opened link",
  in_progress: "In progress",
  completed: "Completed",
  evaluating: "Evaluating",
  report_generating: "Generating report",
  report_ready: "Report ready",
  failed: "Failed",
  cancelled: "Cancelled",
};

const NEXT_STATUS_ACTION: Record<string, { label: string; action: "activate" | "complete" | "archive" } | null> = {
  draft: { label: "Activate campaign", action: "activate" },
  active: { label: "Mark completed", action: "complete" },
  completed: { label: "Archive", action: "archive" },
  archived: null,
};

export default function CampaignDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const campaignId = params.id;

  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [roster, setRoster] = useState<Student[]>([]);
  const [rosterTotal, setRosterTotal] = useState(0);
  const [interviews, setInterviews] = useState<InterviewSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [transitioning, setTransitioning] = useState(false);

  const [search, setSearch] = useState("");
  const [searchResults, setSearchResults] = useState<Student[]>([]);
  const [assigning, setAssigning] = useState(false);
  const [assignMessage, setAssignMessage] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [c, rosterResult, interviewsResult] = await Promise.all([
        campaignsApi.get(campaignId),
        campaignsApi.listStudents(campaignId, { per_page: 100 }),
        instituteInterviewsApi.listForCampaign(campaignId, { per_page: 100 }),
      ]);
      setCampaign(c);
      setRoster(rosterResult.items);
      setRosterTotal(rosterResult.pagination.total);
      setInterviews(interviewsResult.items);
    } catch (err) {
      if (err instanceof ApiRequestError && err.status === 401) {
        router.push("/institute/login");
        return;
      }
      if (err instanceof ApiRequestError && err.status === 404) {
        setError("Campaign not found.");
        return;
      }
      setError("Couldn't load this campaign.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [campaignId]);

  async function handleTransition(action: "activate" | "complete" | "archive") {
    setTransitioning(true);
    setError(null);
    try {
      const updated =
        action === "activate"
          ? await campaignsApi.activate(campaignId)
          : action === "complete"
          ? await campaignsApi.complete(campaignId)
          : await campaignsApi.archive(campaignId);
      setCampaign(updated);
    } catch (err) {
      setError(
        err instanceof ApiRequestError ? err.message : "Couldn't update campaign status."
      );
    } finally {
      setTransitioning(false);
    }
  }

  async function handleStudentSearch(e: FormEvent) {
    e.preventDefault();
    if (!search.trim()) return;
    try {
      const result = await studentsApi.list({ search, per_page: 10 });
      setSearchResults(result.items);
    } catch {
      setSearchResults([]);
    }
  }

  async function handleAssign(studentId: string) {
    setAssigning(true);
    setAssignMessage(null);
    try {
      const result = await campaignsApi.assignStudents(campaignId, [studentId]);
      if (result.assigned > 0) {
        setAssignMessage("Student assigned.");
      } else if (result.already_assigned > 0) {
        setAssignMessage("Student is already assigned.");
      }
      const rosterResult = await campaignsApi.listStudents(campaignId, { per_page: 100 });
      setRoster(rosterResult.items);
      setRosterTotal(rosterResult.pagination.total);
    } catch (err) {
      setAssignMessage(
        err instanceof ApiRequestError ? err.message : "Couldn't assign student."
      );
    } finally {
      setAssigning(false);
    }
  }

  async function handleUnassign(studentId: string) {
    try {
      await campaignsApi.unassignStudent(campaignId, studentId);
      setRoster((r) => r.filter((s) => s.id !== studentId));
      setRosterTotal((t) => t - 1);
    } catch {
      setError("Couldn't remove student from campaign.");
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-muted-foreground">Loading…</p>
      </div>
    );
  }

  if (error && !campaign) {
    return (
      <div className="min-h-screen">
        <AppHeader />
        <div className="mx-auto max-w-3xl px-6 py-12">
          <Alert variant="error">{error}</Alert>
        </div>
      </div>
    );
  }

  if (!campaign) return null;

  const nextAction = NEXT_STATUS_ACTION[campaign.status];
  const rosterIds = new Set(roster.map((s) => s.id));

  return (
    <div className="min-h-screen">
      <AppHeader />
      <div className="mx-auto max-w-3xl space-y-8 px-6 py-12">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="font-display text-3xl">{campaign.name}</h1>
            <p className="mt-1 text-muted-foreground">{campaign.role}</p>
          </div>
          <StatusBadge status={campaign.status} />
        </div>

        {error && <Alert variant="error">{error}</Alert>}

        <div className="grid grid-cols-2 gap-4 rounded-md border border-border bg-white p-6 text-sm">
          <div>
            <p className="text-muted-foreground">Difficulty</p>
            <p className="mt-1 capitalize">{campaign.difficulty}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Experience level</p>
            <p className="mt-1">{campaign.experience_level ?? "—"}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Round durations</p>
            <p className="mt-1">
              Technical {campaign.technical_duration_minutes}m · Managerial{" "}
              {campaign.managerial_duration_minutes}m · HR {campaign.hr_duration_minutes}m
            </p>
          </div>
          <div>
            <p className="text-muted-foreground">Total duration</p>
            <p className="mt-1">{campaign.total_duration_minutes} minutes</p>
          </div>
        </div>

        {nextAction && (
          <Button
            type="button"
            variant="ghost"
            className="w-auto px-4"
            loading={transitioning}
            onClick={() => handleTransition(nextAction.action)}
          >
            {nextAction.label}
          </Button>
        )}

        <div className="space-y-4">
          <h2 className="font-display text-xl">Roster ({rosterTotal})</h2>

          <form onSubmit={handleStudentSearch} className="flex gap-2">
            <Input
              placeholder="Search students by name, email, or roll number"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <Button type="submit" className="w-auto px-4">
              Search
            </Button>
          </form>

          {assignMessage && <Alert variant="info">{assignMessage}</Alert>}

          {searchResults.length > 0 && (
            <div className="rounded-md border border-border bg-white">
              {searchResults.map((s) => (
                <div
                  key={s.id}
                  className="flex items-center justify-between border-b border-border px-4 py-3 text-sm last:border-0"
                >
                  <div>
                    <p>{s.name}</p>
                    <p className="text-muted-foreground">{s.email}</p>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    className="w-auto px-3"
                    disabled={assigning || rosterIds.has(s.id)}
                    onClick={() => handleAssign(s.id)}
                  >
                    {rosterIds.has(s.id) ? "Assigned" : "Assign"}
                  </Button>
                </div>
              ))}
            </div>
          )}

          <div className="overflow-hidden rounded-md border border-border bg-white">
            <table className="w-full text-sm">
              <thead className="border-b border-border bg-muted text-left text-muted-foreground">
                <tr>
                  <th className="px-4 py-3 font-medium">Name</th>
                  <th className="px-4 py-3 font-medium">Email</th>
                  <th className="px-4 py-3 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {roster.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="px-4 py-8 text-center text-muted-foreground">
                      No students assigned yet.
                    </td>
                  </tr>
                ) : (
                  roster.map((s) => (
                    <tr key={s.id} className="border-b border-border last:border-0">
                      <td className="px-4 py-3">{s.name}</td>
                      <td className="px-4 py-3 text-muted-foreground">{s.email}</td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => handleUnassign(s.id)}
                          className="text-sm text-destructive hover:underline"
                        >
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {interviews.length > 0 && (
          <div className="space-y-3">
            <h2 className="font-display text-xl">Interviews ({interviews.length})</h2>
            <div className="overflow-hidden rounded-md border border-border bg-white">
              <table className="w-full text-sm">
                <thead className="border-b border-border bg-muted text-left text-muted-foreground">
                  <tr>
                    <th className="px-4 py-3 font-medium">Student</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-4 py-3 font-medium">Current round</th>
                  </tr>
                </thead>
                <tbody>
                  {interviews.map((iv) => {
                    const student = roster.find((s) => s.id === iv.student_id);
                    return (
                      <tr key={iv.id} className="border-b border-border last:border-0">
                        <td className="px-4 py-3">
                          <Link
                            href={`/institute/interviews/${iv.id}`}
                            className="hover:text-primary hover:underline"
                          >
                            {student?.name ?? iv.student_id}
                          </Link>
                        </td>
                        <td className="px-4 py-3 text-muted-foreground">
                          {INTERVIEW_STATUS_LABEL[iv.status] ?? iv.status}
                        </td>
                        <td className="px-4 py-3 capitalize text-muted-foreground">
                          {iv.current_round ?? "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>

  );
}
