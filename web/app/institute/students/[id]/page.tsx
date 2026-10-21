"use client";

import { ChangeEvent, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { AppHeader } from "@/components/app-header";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";
import {
  studentsApi,
  resumeApi,
  ApiRequestError,
  Student,
  ResumeVersion,
  ResumeVersionListResult,
} from "@/lib/api";

const STATUS_LABEL: Record<string, string> = {
  pending: "Queued",
  processing: "Processing…",
  completed: "Ready",
  failed: "Failed",
};

function ProfileSection({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div>
      <p className="text-sm font-medium">{title}</p>
      <ul className="mt-1 list-inside list-disc space-y-0.5 text-sm text-muted-foreground">
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

export default function StudentDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const studentId = params.id;
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [student, setStudent] = useState<Student | null>(null);
  const [resume, setResume] = useState<ResumeVersion | null>(null);
  const [resumeMissing, setResumeMissing] = useState(false);
  const [versions, setVersions] = useState<ResumeVersionListResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  async function loadResume() {
    try {
      const current = await resumeApi.getCurrent(studentId);
      setResume(current);
      setResumeMissing(false);
    } catch (err) {
      if (err instanceof ApiRequestError && err.status === 404) {
        setResumeMissing(true);
        setResume(null);
      } else {
        throw err;
      }
    }
    const versionList = await resumeApi.listVersions(studentId, { per_page: 20 });
    setVersions(versionList);
  }

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const s = await studentsApi.get(studentId);
      setStudent(s);
      await loadResume();
    } catch (err) {
      if (err instanceof ApiRequestError && err.status === 401) {
        router.push("/institute/login");
        return;
      }
      if (err instanceof ApiRequestError && err.status === 404) {
        setError("Student not found.");
        return;
      }
      setError("Couldn't load this student.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [studentId]);

  async function handleUpload(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadError(null);
    setUploading(true);
    try {
      await resumeApi.upload(studentId, file);
      await loadResume();
    } catch (err) {
      setUploadError(
        err instanceof ApiRequestError ? err.message : "Couldn't upload resume."
      );
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-muted-foreground">Loading…</p>
      </div>
    );
  }

  if (error && !student) {
    return (
      <div className="min-h-screen">
        <AppHeader />
        <div className="mx-auto max-w-3xl px-6 py-12">
          <Alert variant="error">{error}</Alert>
        </div>
      </div>
    );
  }

  if (!student) return null;

  const profile = resume?.candidate_profile;

  return (
    <div className="min-h-screen">
      <AppHeader />
      <div className="mx-auto max-w-3xl space-y-8 px-6 py-12">
        <div>
          <h1 className="font-display text-3xl">{student.name}</h1>
          <p className="mt-1 text-muted-foreground">{student.email}</p>
          <p className="mt-1 text-sm text-muted-foreground">
            {student.roll_number ?? "No roll number"} · {student.department ?? "—"} ·{" "}
            {student.batch ?? "—"}
          </p>
        </div>

        {error && <Alert variant="error">{error}</Alert>}
        {uploadError && <Alert variant="error">{uploadError}</Alert>}

        <div className="space-y-4 rounded-md border border-border bg-white p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">Resume</p>
              {resume && (
                <p className="text-sm text-muted-foreground">
                  {resume.original_filename} · v{resume.version_number} ·{" "}
                  {STATUS_LABEL[resume.extraction_status]}
                </p>
              )}
              {resumeMissing && (
                <p className="text-sm text-muted-foreground">No resume uploaded yet.</p>
              )}
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx"
              onChange={handleUpload}
              className="hidden"
              id="resume-upload"
            />
            <Button
              type="button"
              variant="ghost"
              className="w-auto px-4"
              disabled={uploading}
              onClick={() => fileInputRef.current?.click()}
            >
              {uploading ? "Uploading…" : resume ? "Upload new version" : "Upload resume"}
            </Button>
          </div>

          {resume?.extraction_status === "failed" && (
            <Alert variant="error">
              Couldn&rsquo;t process this resume: {resume.extraction_error}
            </Alert>
          )}

          {profile && profile.analysis_status === "completed" && (
            <div className="space-y-4 border-t border-border pt-4">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">
                Extracted profile
              </p>
              <ProfileSection title="Education" items={profile.education} />
              <ProfileSection title="Skills" items={profile.skills} />
              <ProfileSection title="Programming languages" items={profile.programming_languages} />
              <ProfileSection title="Technologies" items={profile.technologies} />
              <ProfileSection title="Projects" items={profile.projects} />
              <ProfileSection title="Internships" items={profile.internships} />
              <ProfileSection title="Experience" items={profile.experience} />
              <ProfileSection title="Certifications" items={profile.certifications} />
              <ProfileSection title="Achievements" items={profile.achievements} />
            </div>
          )}
        </div>

        {versions && versions.items.length > 0 && (
          <div className="space-y-3">
            <h2 className="font-display text-xl">Resume history</h2>
            <div className="overflow-hidden rounded-md border border-border bg-white">
              <table className="w-full text-sm">
                <thead className="border-b border-border bg-muted text-left text-muted-foreground">
                  <tr>
                    <th className="px-4 py-3 font-medium">Version</th>
                    <th className="px-4 py-3 font-medium">Filename</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {versions.items.map((v) => (
                    <tr key={v.id} className="border-b border-border last:border-0">
                      <td className="px-4 py-3">v{v.version_number}</td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {v.original_filename}
                      </td>
                      <td className="px-4 py-3">{STATUS_LABEL[v.extraction_status]}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
