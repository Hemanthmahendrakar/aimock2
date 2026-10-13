"use client";

import { ChangeEvent, FormEvent, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AppHeader } from "@/components/app-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/ui/field";
import { Alert } from "@/components/ui/alert";
import {
  studentsApi,
  ApiRequestError,
  Student,
  ImportResult,
  Campus, campusApi,
} from "@/lib/api";

const PER_PAGE = 10;

const emptyForm = { name: "", email: "", roll_number: "", department: "", batch: "", phone: "", campus_id: "", course: "", graduation_year: "", experience_level: "" };

export default function StudentsPage() {
  const router = useRouter();

  const [students, setStudents] = useState<Student[]>([]);
  const [campuses, setCampuses] = useState<Campus[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showAddForm, setShowAddForm] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function loadStudents(targetPage = page, targetSearch = search) {
    setLoading(true);
    setError(null);
    try {
      const result = await studentsApi.list({
        page: targetPage,
        per_page: PER_PAGE,
        search: targetSearch,
      });
      setStudents(result.items);
      setTotal(result.pagination.total);
    } catch (err) {
      if (err instanceof ApiRequestError && err.status === 401) {
        router.push("/institute/login");
        return;
      }
      setError("Couldn't load students.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    campusApi.list().then(setCampuses).catch(() => undefined);
    loadStudents(1, "");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleSearchSubmit(e: FormEvent) {
    e.preventDefault();
    setPage(1);
    loadStudents(1, search);
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setCreateError(null);
    setCreating(true);
    try {
      await studentsApi.create({
        name: form.name,
        email: form.email,
        roll_number: form.roll_number || undefined,
        department: form.department || undefined,
        batch: form.batch || undefined,
        phone: form.phone || undefined,
        campus_id: form.campus_id || undefined,
        course: form.course || undefined,
        graduation_year: form.graduation_year ? Number(form.graduation_year) : undefined,
        experience_level: form.experience_level || undefined,
      });
      setForm(emptyForm);
      setShowAddForm(false);
      loadStudents(1, search);
      setPage(1);
    } catch (err) {
      setCreateError(
        err instanceof ApiRequestError ? err.message : "Couldn't add student."
      );
    } finally {
      setCreating(false);
    }
  }

  async function handleDelete(id: string) {
    try {
      await studentsApi.remove(id);
      loadStudents(page, search);
    } catch {
      setError("Couldn't remove student.");
    }
  }

  async function handleImport(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setImportError(null);
    setImportResult(null);
    setImporting(true);
    try {
      const result = await studentsApi.importCsv(file);
      setImportResult(result);
      loadStudents(1, search);
      setPage(1);
    } catch (err) {
      setImportError(
        err instanceof ApiRequestError ? err.message : "Import failed."
      );
    } finally {
      setImporting(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / PER_PAGE));

  return (
    <div className="min-h-screen">
      <AppHeader />
      <div className="mx-auto max-w-4xl space-y-6 px-6 py-12">
        <div className="flex items-center justify-between">
          <h1 className="font-display text-3xl">Students</h1>
          <div className="flex gap-2">
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              onChange={handleImport}
              className="hidden"
              id="csv-import"
            />
            <Button
              type="button"
              variant="ghost"
              className="w-auto px-4"
              disabled={importing}
              onClick={() => fileInputRef.current?.click()}
            >
              {importing ? "Importing…" : "Import CSV"}
            </Button>
            <Button
              type="button"
              className="w-auto px-4"
              onClick={() => setShowAddForm((v) => !v)}
            >
              {showAddForm ? "Cancel" : "Add student"}
            </Button>
          </div>
        </div>

        {error && <Alert variant="error">{error}</Alert>}
        {importError && <Alert variant="error">{importError}</Alert>}

        {importResult && (
          <Alert variant={importResult.skipped > 0 ? "info" : "success"}>
            Imported {importResult.created} of {importResult.total_rows} rows.
            {importResult.skipped > 0 && (
              <>
                {" "}
                {importResult.skipped} skipped:
                <ul className="mt-2 list-inside list-disc space-y-0.5">
                  {importResult.errors.slice(0, 10).map((e, i) => (
                    <li key={i}>
                      Row {e.row}: {e.message}
                    </li>
                  ))}
                </ul>
              </>
            )}
          </Alert>
        )}

        {showAddForm && (
          <form
            onSubmit={handleCreate}
            className="space-y-4 rounded-md border border-border bg-white p-6"
          >
            {createError && <Alert variant="error">{createError}</Alert>}
            <div className="grid grid-cols-2 gap-4">
              <Field label="Name" htmlFor="s-name">
                <Input
                  id="s-name"
                  required
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                />
              </Field>
              <Field label="Email" htmlFor="s-email">
                <Input
                  id="s-email"
                  type="email"
                  required
                  value={form.email}
                  onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                />
              </Field>
              <Field label="Roll number" htmlFor="s-roll">
                <Input
                  id="s-roll"
                  value={form.roll_number}
                  onChange={(e) => setForm((f) => ({ ...f, roll_number: e.target.value }))}
                />
              </Field>
              <Field label="Department" htmlFor="s-dept">
                <Input
                  id="s-dept"
                  value={form.department}
                  onChange={(e) => setForm((f) => ({ ...f, department: e.target.value }))}
                />
              </Field>
              <Field label="Batch" htmlFor="s-batch">
                <Input
                  id="s-batch"
                  value={form.batch}
                  onChange={(e) => setForm((f) => ({ ...f, batch: e.target.value }))}
                />
              </Field>
              <Field label="Phone" htmlFor="s-phone">
                <Input
                  id="s-phone"
                  value={form.phone}
                  onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
                />
              </Field>
              <Field label="Campus" htmlFor="s-campus">
                <select id="s-campus" className="h-10 w-full rounded-md border border-border bg-white px-3 text-sm" value={form.campus_id} onChange={(e) => setForm((f) => ({ ...f, campus_id: e.target.value }))}>
                  <option value="">Not assigned</option>{campuses.filter((c) => c.is_active).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </Field>
              <Field label="Course" htmlFor="s-course"><Input id="s-course" value={form.course} onChange={(e) => setForm((f) => ({ ...f, course: e.target.value }))} placeholder="B.Tech CSE" /></Field>
              <Field label="Graduation year" htmlFor="s-grad"><Input id="s-grad" type="number" min="1950" max="2200" value={form.graduation_year} onChange={(e) => setForm((f) => ({ ...f, graduation_year: e.target.value }))} /></Field>
              <Field label="Experience level" htmlFor="s-exp"><Input id="s-exp" value={form.experience_level} onChange={(e) => setForm((f) => ({ ...f, experience_level: e.target.value }))} placeholder="Fresher" /></Field>
            </div>
            <Button type="submit" loading={creating} className="w-auto px-6">
              Add student
            </Button>
          </form>
        )}

        <form onSubmit={handleSearchSubmit} className="flex gap-2">
          <Input
            placeholder="Search by name, email, or roll number"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <Button type="submit" className="w-auto px-4">
            Search
          </Button>
        </form>

        <div className="overflow-hidden rounded-md border border-border bg-white">
          <table className="w-full text-sm">
            <thead className="border-b border-border bg-muted text-left text-muted-foreground">
              <tr>
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Email</th>
                <th className="px-4 py-3 font-medium">Roll no.</th>
                <th className="px-4 py-3 font-medium">Department</th>
                <th className="px-4 py-3 font-medium">Batch</th>
                <th className="px-4 py-3 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                    Loading…
                  </td>
                </tr>
              ) : students.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                    No students yet. Add one, or import a CSV.
                  </td>
                </tr>
              ) : (
                students.map((s) => (
                  <tr key={s.id} className="border-b border-border last:border-0">
                    <td className="px-4 py-3">
                      <Link
                        href={`/institute/students/${s.id}`}
                        className="font-medium text-foreground hover:text-primary"
                      >
                        {s.name}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">{s.email}</td>
                    <td className="px-4 py-3">{s.roll_number ?? "—"}</td>
                    <td className="px-4 py-3">{s.department ?? "—"}</td>
                    <td className="px-4 py-3">{s.batch ?? "—"}</td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => handleDelete(s.id)}
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

        {totalPages > 1 && (
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>
              Page {page} of {totalPages} ({total} students)
            </span>
            <div className="flex gap-2">
              <Button
                type="button"
                variant="ghost"
                className="w-auto px-3"
                disabled={page <= 1}
                onClick={() => {
                  const next = page - 1;
                  setPage(next);
                  loadStudents(next, search);
                }}
              >
                Previous
              </Button>
              <Button
                type="button"
                variant="ghost"
                className="w-auto px-3"
                disabled={page >= totalPages}
                onClick={() => {
                  const next = page + 1;
                  setPage(next);
                  loadStudents(next, search);
                }}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
