"use client";

import { FormEvent, Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Alert } from "@/components/ui/alert";
import { interviewSessionApi, reportsApi, ApiRequestError, InterviewState, Report } from "@/lib/api";

const ROUND_LABELS: Record<string, string> = {
  technical: "Technical Round",
  managerial: "Managerial Round",
  hr: "HR Round",
};

function formatTime(seconds: number | null): string {
  if (seconds === null) return "--:--";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function InterviewSessionContent() {
  const params = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const interviewId = params.id;
  const token = searchParams.get("token");

  const [state, setState] = useState<InterviewState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [secondsLeft, setSecondsLeft] = useState<number | null>(null);

  const [answer, setAnswer] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  const [report, setReport] = useState<Report | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);

  // Voice + Avatar (Phase 13) — all optional, everything above still
  // works with none of this configured server-side.
  const [avatarSession, setAvatarSession] = useState<{
    provider: string;
    embed_url: string | null;
  } | null>(null);
  const [questionAudioUrl, setQuestionAudioUrl] = useState<string | null>(null);
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordedChunksRef = useRef<BlobPart[]>([]);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const applyState = useCallback((s: InterviewState) => {
    setState(s);
    setSecondsLeft(s.seconds_remaining);
    setAnswer("");
  }, []);

  useEffect(() => {
    async function init() {
      setLoading(true);
      setError(null);
      try {
        const s = token
          ? await interviewSessionApi.exchangeAccessToken(interviewId, token)
          : await interviewSessionApi.getState();
        applyState(s);
      } catch (err) {
        setError(
          err instanceof ApiRequestError
            ? err.message
            : "Couldn't reach the server. Check your connection and try again."
        );
      } finally {
        setLoading(false);
      }
    }
    init();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [interviewId, token]);

  // Local countdown for a smooth timer, resynced periodically from the server.
  useEffect(() => {
    if (state?.status !== "in_progress" || secondsLeft === null) return;
    const tick = setInterval(() => {
      setSecondsLeft((s) => (s !== null && s > 0 ? s - 1 : s));
    }, 1000);
    return () => clearInterval(tick);
  }, [state?.status, secondsLeft !== null]);

  // Resync with the server every 10s while in progress — a round can
  // advance server-side purely from time elapsing, with no client action.
  useEffect(() => {
    if (state?.status !== "in_progress") {
      if (pollRef.current) clearInterval(pollRef.current);
      return;
    }
    pollRef.current = setInterval(async () => {
      try {
        const s = await interviewSessionApi.getState();
        applyState(s);
      } catch {
        // Transient poll failures aren't worth surfacing to the user.
      }
    }, 10000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [state?.status, applyState]);

  // Evaluation + report generation run as background jobs after the
  // interview completes — poll until the report is actually ready,
  // rather than making the student refresh the page themselves.
  useEffect(() => {
    const pending = new Set(["completed", "evaluating", "report_generating"]);
    if (!state || !pending.has(state.status)) return;
    const poll = setInterval(async () => {
      try {
        const s = await interviewSessionApi.getState();
        applyState(s);
      } catch {
        // Transient poll failures aren't worth surfacing to the user.
      }
    }, 5000);
    return () => clearInterval(poll);
  }, [state?.status, applyState]);

  useEffect(() => {
    if (state?.status !== "report_ready" || report) return;
    reportsApi
      .getMyReport()
      .then(setReport)
      .catch((err) => {
        setReportError(
          err instanceof ApiRequestError ? err.message : "Couldn't load your report."
        );
      });
  }, [state?.status, report]);

  // Avatar session — fetched once the interview is under way. A
  // provider of "none" (the default when nothing's configured) is a
  // normal, expected response, not an error — see backend docstrings.
  useEffect(() => {
    if (state?.status !== "in_progress" || avatarSession) return;
    interviewSessionApi
      .getAvatarSession()
      .then(setAvatarSession)
      .catch(() => {
        // Avatar is a nice-to-have; a failure here should never block
        // the interview itself.
      });
  }, [state?.status, avatarSession]);

  // Text-to-speech for the current question: try server-side TTS
  // first, fall back to the browser's own speechSynthesis when no
  // provider is configured (getQuestionAudio resolves to null, not an
  // error, in that case — see lib/api.ts).
  useEffect(() => {
    const questionId = state?.current_question?.id;
    const questionText = state?.current_question?.question_text;
    if (!questionId || !questionText || state?.status !== "in_progress") return;

    let cancelled = false;
    let objectUrl: string | null = null;

    interviewSessionApi
      .getQuestionAudio()
      .then((blob) => {
        if (cancelled) return;
        if (blob) {
          objectUrl = URL.createObjectURL(blob);
          setQuestionAudioUrl(objectUrl);
        } else if (typeof window !== "undefined" && "speechSynthesis" in window) {
          window.speechSynthesis.cancel();
          window.speechSynthesis.speak(new SpeechSynthesisUtterance(questionText));
        }
      })
      .catch(() => {
        // Silent — the question text is already on screen either way.
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state?.current_question?.id]);

  async function handleToggleRecording() {
    setVoiceError(null);
    if (recording) {
      mediaRecorderRef.current?.stop();
      setRecording(false);
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      recordedChunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) recordedChunksRef.current.push(e.data);
      };
      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        const blob = new Blob(recordedChunksRef.current, { type: "audio/webm" });
        setTranscribing(true);
        try {
          const result = await interviewSessionApi.transcribeAnswer(blob);
          setAnswer((prev) => (prev.trim() ? `${prev.trim()} ${result.text}` : result.text));
        } catch (err) {
          setVoiceError(
            err instanceof ApiRequestError
              ? err.message
              : "Couldn't transcribe your recording — please type your answer instead."
          );
        } finally {
          setTranscribing(false);
        }
      };
      mediaRecorderRef.current = recorder;
      recorder.start();
      setRecording(true);
    } catch {
      setVoiceError(
        "Couldn't access your microphone. Check your browser permissions, or type your answer instead."
      );
    }
  }

  async function handleResumeCheck() {
    setActionLoading(true);
    setError(null);
    try {
      applyState(await interviewSessionApi.resumeCheck());
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "Something went wrong.");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleDeviceCheck() {
    setActionLoading(true);
    setError(null);
    try {
      applyState(await interviewSessionApi.deviceCheck());
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "Something went wrong.");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleStart() {
    setActionLoading(true);
    setError(null);
    try {
      applyState(await interviewSessionApi.start());
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "Something went wrong.");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleSubmitAnswer(e: FormEvent) {
    e.preventDefault();
    if (!state?.current_question || !answer.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      applyState(
        await interviewSessionApi.submitAnswer(state.current_question.id, answer.trim())
      );
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "Couldn't submit your answer.");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[hsl(var(--panel-ink))]">
        <p className="text-sm text-[hsl(var(--panel-ink-foreground))] opacity-70">Loading…</p>
      </div>
    );
  }

  if (error && !state) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[hsl(var(--panel-ink))] px-6">
        <div className="w-full max-w-sm">
          <Alert variant="error">{error}</Alert>
        </div>
      </div>
    );
  }

  if (!state) return null;

  return (
    <div className="min-h-screen bg-[hsl(var(--panel-ink))] text-[hsl(var(--panel-ink-foreground))]">
      <div className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center px-6 py-16">
        {error && (
          <div className="mb-6">
            <Alert variant="error">{error}</Alert>
          </div>
        )}

        {state.status === "cancelled" && (
          <div className="text-center">
            <h1 className="font-display text-2xl">This interview has been cancelled</h1>
            <p className="mt-2 opacity-70">Please reach out to your institute for details.</p>
          </div>
        )}

        {(state.status === "ready" || state.status === "created") && (
          <div className="space-y-8">
            <div>
              <p className="font-display text-xl italic opacity-80">Mock Interview</p>
              <h1 className="mt-2 font-display text-3xl">Let&rsquo;s get you set up</h1>
            </div>

            {!state.resume_verified && (
              <div className="space-y-3 rounded-md border border-white/15 p-6">
                <p className="font-medium">Step 1: Confirm your resume</p>
                <p className="text-sm opacity-70">
                  We&rsquo;ll reference the resume you submitted to your institute during this
                  interview.
                </p>
                <Button
                  type="button"
                  loading={actionLoading}
                  onClick={handleResumeCheck}
                  className="w-auto px-6"
                >
                  Confirm and continue
                </Button>
              </div>
            )}

            {state.resume_verified && !state.device_checked && (
              <div className="space-y-3 rounded-md border border-white/15 p-6">
                <p className="font-medium">Step 2: Check your camera and microphone</p>
                <p className="text-sm opacity-70">
                  Make sure your browser has camera and microphone access before continuing.
                </p>
                <Button
                  type="button"
                  loading={actionLoading}
                  onClick={handleDeviceCheck}
                  className="w-auto px-6"
                >
                  My camera and mic are working
                </Button>
              </div>
            )}

            {state.resume_verified && state.device_checked && (
              <div className="space-y-3 rounded-md border border-white/15 p-6">
                <p className="font-medium">You&rsquo;re all set</p>
                <p className="text-sm opacity-70">
                  This interview has three rounds — Technical, Managerial, and HR — timed
                  independently. Once you start, the timer begins.
                </p>
                <Button
                  type="button"
                  loading={actionLoading}
                  onClick={handleStart}
                  className="w-auto px-6"
                >
                  Start interview
                </Button>
              </div>
            )}
          </div>
        )}

        {state.status === "in_progress" && (
          <div className="space-y-8">
            <div className="flex items-center justify-between">
              <p className="text-sm uppercase tracking-wide opacity-60">
                {state.current_round ? ROUND_LABELS[state.current_round] : ""}
              </p>
              <p className="font-mono text-lg">{formatTime(secondsLeft)}</p>
            </div>

            <div className="flex justify-center">
              {avatarSession?.embed_url ? (
                <iframe
                  src={avatarSession.embed_url}
                  className="h-40 w-40 rounded-full border border-white/15"
                  allow="camera; microphone"
                  title="Interviewer avatar"
                />
              ) : (
                <div className="flex h-24 w-24 items-center justify-center rounded-full border border-white/15 bg-white/5">
                  <span className="font-display text-3xl italic opacity-60">AI</span>
                </div>
              )}
            </div>

            {questionAudioUrl && (
              <audio key={questionAudioUrl} src={questionAudioUrl} autoPlay className="hidden" />
            )}

            {state.current_question ? (
              <form onSubmit={handleSubmitAnswer} className="space-y-5">
                <p className="font-display text-2xl leading-snug">
                  {state.current_question.question_text}
                </p>
                <Textarea
                  value={answer}
                  onChange={(e) => setAnswer(e.target.value)}
                  placeholder="Type your answer, or record it below…"
                  className="min-h-40 border-white/20 bg-white/5 text-[hsl(var(--panel-ink-foreground))] placeholder:text-white/40"
                  autoFocus
                />

                {voiceError && <Alert variant="error">{voiceError}</Alert>}

                <div className="flex flex-wrap gap-3">
                  <Button
                    type="button"
                    variant="ghost"
                    className="w-auto px-6 border border-white/20"
                    onClick={handleToggleRecording}
                    disabled={transcribing}
                  >
                    {transcribing
                      ? "Transcribing…"
                      : recording
                      ? "Stop recording"
                      : "Record answer"}
                  </Button>
                  <Button
                    type="submit"
                    loading={submitting}
                    disabled={!answer.trim()}
                    className="w-auto px-6"
                  >
                    Submit answer
                  </Button>
                </div>
              </form>
            ) : (
              <p className="opacity-70">Loading the next question…</p>
            )}
          </div>
        )}

        {state.status === "completed" && (
          <div className="text-center">
            <h1 className="font-display text-3xl">Interview complete</h1>
            <p className="mt-2 opacity-70">
              Thank you for completing your mock interview. We&rsquo;re evaluating your
              answers now — this page will update automatically.
            </p>
          </div>
        )}

        {(state.status === "evaluating" || state.status === "report_generating") && (
          <div className="text-center">
            <h1 className="font-display text-3xl">Preparing your report</h1>
            <p className="mt-2 opacity-70">
              {state.status === "evaluating"
                ? "Evaluating your answers across each round…"
                : "Putting together your report…"}
            </p>
          </div>
        )}

        {state.status === "report_ready" && (
          <div className="space-y-8">
            <h1 className="font-display text-3xl">Your interview report</h1>

            {reportError && <Alert variant="error">{reportError}</Alert>}

            {!report ? (
              <p className="opacity-70">Loading your report…</p>
            ) : (
              <div className="space-y-6">
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                  {[
                    ["Overall", report.overall_score],
                    ["Technical", report.technical_score],
                    ["Managerial", report.managerial_score],
                    ["HR", report.hr_score],
                    ["Communication", report.communication_score],
                    ["Problem solving", report.problem_solving_score],
                  ].map(([label, score]) => (
                    <div key={label as string} className="rounded-md border border-white/15 p-4">
                      <p className="text-xs uppercase tracking-wide opacity-60">{label}</p>
                      <p className="mt-1 font-display text-2xl">{score}</p>
                    </div>
                  ))}
                </div>

                <ReportSection title="Strengths" items={report.strengths} />
                <ReportSection title="Areas to improve" items={report.weaknesses} />
                <ReportSection title="Technical skill gaps" items={report.technical_skill_gaps} />
                <ReportSection
                  title="Communication improvements"
                  items={report.communication_improvements}
                />
                <ReportSection title="Interview highlights" items={report.interview_highlights} />
                <ReportSection
                  title="Recommended preparation"
                  items={report.recommended_preparation}
                />
                <ReportSection title="Improvement plan" items={report.improvement_plan} />
              </div>
            )}
          </div>
        )}

        {state.status === "failed" && (
          <div className="text-center">
            <h1 className="font-display text-2xl">Something went wrong</h1>
            <p className="mt-2 opacity-70">
              We couldn&rsquo;t finish generating your report. Please reach out to your
              institute for help.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

function ReportSection({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div>
      <p className="text-sm font-medium uppercase tracking-wide opacity-60">{title}</p>
      <ul className="mt-2 list-inside list-disc space-y-1 opacity-90">
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

export default function InterviewSessionPage() {
  return (
    <Suspense fallback={null}>
      <InterviewSessionContent />
    </Suspense>
  );
}
