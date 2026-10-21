"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppHeader } from "@/components/app-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Field } from "@/components/ui/field";
import { Alert } from "@/components/ui/alert";
import {
  interviewTemplatesApi,
  ApiRequestError,
  InterviewTemplate,
  RoundConfigInput,
  RoundType,
} from "@/lib/api";

const ROUND_TYPES: RoundType[] = ["technical", "managerial", "hr"];
const ROUND_LABELS: Record<RoundType, string> = {
  technical: "Technical",
  managerial: "Managerial",
  hr: "HR",
};
const ROUND_DEFAULT_MINUTES: Record<RoundType, number> = {
  technical: 15,
  managerial: 10,
  hr: 10,
};

type RoundFormState = {
  enabled: boolean;
  duration_minutes: number;
  question_categories: string;
  instructions: string;
};

function initialRounds(): Record<RoundType, RoundFormState> {
  return {
    technical: {
      enabled: true,
      duration_minutes: 15,
      question_categories: "",
      instructions: "",
    },
    managerial: { enabled: true, duration_minutes: 10, question_categories: "", instructions: "" },
    hr: { enabled: true, duration_minutes: 10, question_categories: "", instructions: "" },
  };
}

export default function InterviewTemplatesPage() {
  const router = useRouter();
  const [templates, setTemplates] = useState<InterviewTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [isDefault, setIsDefault] = useState(false);
  const [rounds, setRounds] = useState<Record<RoundType, RoundFormState>>(initialRounds());
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const result = await interviewTemplatesApi.list({ per_page: 50 });
      setTemplates(result.items);
    } catch (err) {
      if (err instanceof ApiRequestError && err.status === 401) {
        router.push("/institute/login");
        return;
      }
      setError("Couldn't load interview templates.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function updateRound(type: RoundType, patch: Partial<RoundFormState>) {
    setRounds((r) => ({ ...r, [type]: { ...r[type], ...patch } }));
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setCreateError(null);
    setCreating(true);
    try {
      const roundPayload: RoundConfigInput[] = ROUND_TYPES.filter(
        (t) => rounds[t].enabled
      ).map((t) => ({
        round_type: t,
        duration_minutes: rounds[t].duration_minutes,
        question_categories: rounds[t].question_categories
          ? rounds[t].question_categories.split(",").map((s) => s.trim()).filter(Boolean)
          : [],
        instructions: rounds[t].instructions || undefined,
      }));

      await interviewTemplatesApi.create({
        name,
        description: description || undefined,
        is_default: isDefault,
        rounds: roundPayload,
      });
      setName("");
      setDescription("");
      setIsDefault(false);
      setRounds(initialRounds());
      setShowForm(false);
      load();
    } catch (err) {
      setCreateError(
        err instanceof ApiRequestError ? err.message : "Couldn't create template."
      );
    } finally {
      setCreating(false);
    }
  }

  async function handleDelete(id: string) {
    try {
      await interviewTemplatesApi.remove(id);
      load();
    } catch {
      setError("Couldn't remove template.");
    }
  }

  return (
    <div className="min-h-screen">
      <AppHeader />
      <div className="mx-auto max-w-3xl space-y-6 px-6 py-12">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="font-display text-3xl">Interview templates</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Reusable round presets you can apply when creating a campaign.
            </p>
          </div>
          <Button type="button" className="w-auto px-4" onClick={() => setShowForm((v) => !v)}>
            {showForm ? "Cancel" : "New template"}
          </Button>
        </div>

        {error && <Alert variant="error">{error}</Alert>}

        {showForm && (
          <form
            onSubmit={handleCreate}
            className="space-y-5 rounded-md border border-border bg-white p-6"
          >
            {createError && <Alert variant="error">{createError}</Alert>}

            <div className="grid grid-cols-2 gap-4">
              <Field label="Template name" htmlFor="t-name">
                <Input
                  id="t-name"
                  required
                  placeholder="Standard SDE Interview"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </Field>
              <div className="flex items-end pb-2.5">
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={isDefault}
                    onChange={(e) => setIsDefault(e.target.checked)}
                  />
                  Set as default template
                </label>
              </div>
            </div>

            <Field label="Description" htmlFor="t-desc">
              <Textarea
                id="t-desc"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </Field>

            <div className="space-y-4">
              {ROUND_TYPES.map((type) => (
                <div key={type} className="rounded-md border border-border p-4">
                  <label className="flex items-center gap-2 text-sm font-medium">
                    <input
                      type="checkbox"
                      checked={rounds[type].enabled}
                      onChange={(e) => updateRound(type, { enabled: e.target.checked })}
                    />
                    {ROUND_LABELS[type]} round
                  </label>

                  {rounds[type].enabled && (
                    <div className="mt-3 space-y-3">
                      <Field label="Duration (minutes)" htmlFor={`${type}-duration`}>
                        <Input
                          id={`${type}-duration`}
                          type="number"
                          min={1}
                          max={180}
                          value={rounds[type].duration_minutes}
                          onChange={(e) =>
                            updateRound(type, {
                              duration_minutes:
                                Number(e.target.value) || ROUND_DEFAULT_MINUTES[type],
                            })
                          }
                        />
                      </Field>
                      <Field
                        label={type === "technical" ? "Question categories (comma-separated)" : "Focus areas (comma-separated)"}
                        htmlFor={`${type}-categories`}
                      >
                        <Input
                          id={`${type}-categories`}
                          placeholder={
                            type === "technical" ? "dsa, dbms, projects" : "ownership, leadership"
                          }
                          value={rounds[type].question_categories}
                          onChange={(e) =>
                            updateRound(type, { question_categories: e.target.value })
                          }
                        />
                      </Field>
                      <Field label="Instructions for the interviewer" htmlFor={`${type}-instr`}>
                        <Textarea
                          id={`${type}-instr`}
                          value={rounds[type].instructions}
                          onChange={(e) => updateRound(type, { instructions: e.target.value })}
                        />
                      </Field>
                    </div>
                  )}
                </div>
              ))}
            </div>

            <Button type="submit" loading={creating} className="w-auto px-6">
              Create template
            </Button>
          </form>
        )}

        <div className="overflow-hidden rounded-md border border-border bg-white">
          <table className="w-full text-sm">
            <thead className="border-b border-border bg-muted text-left text-muted-foreground">
              <tr>
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Rounds</th>
                <th className="px-4 py-3 font-medium">Default</th>
                <th className="px-4 py-3 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-muted-foreground">
                    Loading…
                  </td>
                </tr>
              ) : templates.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-muted-foreground">
                    No templates yet.
                  </td>
                </tr>
              ) : (
                templates.map((t) => (
                  <tr key={t.id} className="border-b border-border last:border-0">
                    <td className="px-4 py-3 font-medium">{t.name}</td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {t.rounds.map((r) => ROUND_LABELS[r.round_type]).join(", ") || "—"}
                    </td>
                    <td className="px-4 py-3">{t.is_default ? "Yes" : ""}</td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => handleDelete(t.id)}
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
    </div>
  );
}
