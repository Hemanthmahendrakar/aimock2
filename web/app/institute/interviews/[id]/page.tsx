"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { AppHeader } from "@/components/app-header";
import { Alert } from "@/components/ui/alert";
import { StatusBadge } from "@/components/ui/badge";
import {
  reportsApi,
  studentsApi,
  ApiRequestError,
  InterviewAdminDetail,
  Report,
  Student,
} from "@/lib/api";

const DIMENSION_LABELS: Record<string, string> = {
  technical: "Technical",
  managerial: "Managerial",
  hr: "HR",
  communication: "Communication",
};

function ListSection({ title, items }: { title: string; items: string[] }) {
  if (!items || items.length === 0) return null;
  return (
    <div>
      <p className="text-sm font-medium text-muted-foreground">{title}</p>
      <ul className="mt-1 list-inside list-disc space-y-0.5 text-sm">
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

export default function InterviewDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const interviewId = params.id;

  const [detail, setDetail] = useState<InterviewAdminDetail | null>(null);
  const [student, setStudent] = useState<Student | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const d = await reportsApi.getInterviewDetail(interviewId);
        setDetail(d);
        studentsApi.get(d.student_id).then(setStudent).catch(() => {});
        try {
          const r = await reportsApi.getForInterview(interviewId);
          setReport(r);
        } catch (err) {
          // Report may not be generated yet — not a page-level error.
          if (!(err instanceof ApiRequestError && err.status === 404)) throw err;
        }
      } catch (err) {
        if (err instanceof ApiRequestError && err.status === 401) {
          router.push("/institute/login");
          return;
        }
        setError("Couldn't load this interview.");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [interviewId, router]);

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
      <div className="mx-auto max-w-3xl space-y-8 px-6 py-12">
        {error && <Alert variant="error">{error}</Alert>}
        {detail && (
          <>
            <div className="flex items-center justify-between">
              <div>
                <h1 className="font-display text-3xl">{student?.name ?? "Interview"}</h1>
                {student?.email && (
                  <p className="mt-1 text-sm text-muted-foreground">{student.email}</p>
                )}
              </div>
              <StatusBadge status={detail.status} />
            </div>

            {report && (
              <div className="rounded-md border border-border bg-white p-6">
                <p className="mb-4 text-sm font-medium">Report (v{report.version_number})</p>
                <div className="grid grid-cols-3 gap-4 sm:grid-cols-6">
                  {[
                    ["Overall", report.overall_score],
                    ["Technical", report.technical_score],
                    ["Managerial", report.managerial_score],
                    ["HR", report.hr_score],
                    ["Comm.", report.communication_score],
                    ["Problem solving", report.problem_solving_score],
                  ].map(([label, score]) => (
                    <div key={label as string}>
                      <p className="text-xs text-muted-foreground">{label}</p>
                      <p className="font-display text-xl">{score}</p>
                    </div>
                  ))}
                </div>
                <div className="mt-6 space-y-4">
                  <ListSection title="Strengths" items={report.strengths} />
                  <ListSection title="Weaknesses" items={report.weaknesses} />
                  <ListSection title="Technical skill gaps" items={report.technical_skill_gaps} />
                  <ListSection
                    title="Communication improvements"
                    items={report.communication_improvements}
                  />
                  <ListSection title="Interview highlights" items={report.interview_highlights} />
                  <ListSection
                    title="Recommended preparation"
                    items={report.recommended_preparation}
                  />
                  <ListSection title="Improvement plan" items={report.improvement_plan} />
                </div>
                <p className="mt-4 text-xs text-muted-foreground">
                  Source: {report.report_source} · Model: {report.model_version ?? "n/a"} ·
                  Generated {new Date(report.generated_at).toLocaleString()}
                </p>
              </div>
            )}

            {!report && (
              <Alert variant="info">
                Report not generated yet. It's produced automatically once the interview
                completes and is evaluated.
              </Alert>
            )}

            {detail.evaluations.length > 0 && (
              <div className="space-y-4">
                <h2 className="font-display text-xl">Evaluations</h2>
                {detail.evaluations.map((e) => (
                  <div
                    key={e.dimension}
                    className="rounded-md border border-border bg-white p-4"
                  >
                    <div className="flex items-center justify-between">
                      <p className="font-medium">
                        {DIMENSION_LABELS[e.dimension] ?? e.dimension}
                      </p>
                      <p className="font-display text-lg">{e.score}</p>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
                      {Object.entries(e.criteria_scores).map(([k, v]) => (
                        <span key={k} className="rounded-full bg-muted px-2 py-0.5">
                          {k}: {v}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="space-y-4">
              <h2 className="font-display text-xl">Rounds</h2>
              {detail.rounds.map((round) => (
                <div
                  key={round.round_type}
                  className="rounded-md border border-border bg-white p-4"
                >
                  <p className="font-medium capitalize">{round.round_type}</p>
                  <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
                    {round.questions.map((q) => (
                      <li key={q.id}>
                        {q.question_text}
                        {q.topic && <span className="ml-2 text-xs opacity-60">({q.topic})</span>}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
