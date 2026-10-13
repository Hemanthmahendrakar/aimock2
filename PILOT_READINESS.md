# Phase 14 — Pilot Readiness

Phase 14 in the roadmap is "Pilot With One Institute." This is not a
coding phase — it means a real institute registers, real students go
through real mock interviews, and someone watches what breaks. That
can't happen inside this build environment: there's no way to deploy
something reachable from the internet here, no real API keys were
ever exercised, and there are no real users to learn from.

What this document is instead: a production-readiness audit of
everything built in Phases 1–13, and a concrete runbook for actually
running the pilot once this is deployed somewhere real. Two real bugs
were found and fixed while writing it — see below.

## Bugs found and fixed during this audit

### 1. `SECRET_KEY` had an insecure fallback default (security)

`app/config/settings.py` previously read:
```python
SECRET_KEY = _require_env("SECRET_KEY", "dev-only-insecure-secret-change-me")
```
`_require_env` only raises when a variable is **completely unset with
no default** — passing a default here defeated that check entirely.
If `SECRET_KEY` were ever missed in a real deployment's environment
config, the app would have booted successfully and silently signed
every JWT, session cookie, and password-reset token with a fallback
string that's sitting in plain text in this repository. Anyone with
repo access could forge a valid institute-admin session or a valid
interview-session token.

**Fixed**: `SECRET_KEY = _require_env("SECRET_KEY")` — now the app
refuses to start at all without a real value. Confirmed this doesn't
break the test suite, since `tests/conftest.py` already sets its own
`SECRET_KEY` via `os.environ.setdefault(...)` independently of this
default.

### 2. The test suite could not have actually passed a real run (correctness)

`RATELIMIT_STORAGE_URI` is Redis-backed and keys by remote address,
which is constant across every request from Flask's test client.
`TestingConfig` never overrode this. Concretely: `/register` is
limited to 5 per hour, and the test suite calls it 26 times across 14
files — every prior "syntax-checked, not run" caveat I gave across
Phases 1–13 was true, but it was never going to be "run and pass"
either, for a reason that has nothing to do with any test's own logic.
A real run would have failed partway through the suite with 429s.

**Fixed**: `TestingConfig.RATELIMIT_ENABLED = False`, with the
reasoning documented inline in `settings.py`. This is Flask-Limiter's
own documented mechanism for this exact situation — it disables
enforcement, not the rate-limit code itself, so production behavior is
unaffected.

### 3. Two interview-session endpoints had no rate limit at all

While looking at rate limiting, `/interview/start` and
`/interview/answer` — both of which can trigger real AI Gateway calls
once a real provider is configured — had no limit. `/answer` in
particular can be called once per question *and* once per follow-up,
so an interview session token could otherwise be used to run up AI API
costs with no bound. Added `10 per hour` to `/start` and `60 per hour`
to `/answer` and `/question-audio` (generous enough for a real
interview's question count, bounded against abuse).

## What's genuinely unverified

Stated once here rather than repeated per file — every item below was
written without network access in this sandbox and needs real
verification before the pilot, not just code review:

- **`AnthropicProvider`** (`app/ai/providers/anthropic_provider.py`) —
  resume analysis, question generation, follow-ups, evaluation,
  report synthesis. Never called against the real Anthropic API.
- **`WhisperSTTProvider`** / **`ElevenLabsTTSProvider`** — never called
  against real OpenAI/ElevenLabs APIs.
- **`GenericAvatarProvider`** — this one is explicitly a *template*,
  not a real integration. Your spec names no avatar vendor, and real
  vendors (D-ID, HeyGen, Synthesia, Tavus) differ enough in actual
  request/response shape that this file's endpoint path and payload
  keys should be treated as illustrative, not correct. **This needs
  real implementation work against a chosen vendor before the pilot
  uses server-side avatars at all** — until then, `AVATAR_PROVIDER=none`
  is the only honest setting, and students see the static fallback.
- **MinIO → real S3**: local dev runs against MinIO. `S3_ENDPOINT_URL`,
  `S3_USE_PATH_STYLE`, and credentials all need to point at real AWS
  S3 (or another real S3-compatible provider) for the pilot, and that
  switch itself has never been exercised.
- **Celery worker under real load**: `CELERY_TASK_ALWAYS_EAGER=True`
  in tests means the actual async worker path (separate process,
  separate DB connections, real Redis broker) has never run.
- **The full docker-compose stack together**: each phase was
  reasoned about file-by-file; nobody has run
  `docker compose up --build` end-to-end.

## Known, deliberate limitations (decide before the pilot, don't just discover them)

- **Student report access can expire before the report is ready.**
  `INTERVIEW_SESSION_TOKEN_TTL` defaults to 3 hours; if evaluation +
  report generation takes longer than that (a real AI provider under
  load, a backlog), the student's session JWT expires and they get a
  401 trying to view their own report — there's no re-access flow,
  since Institute Mode has no persistent student login (see Phase 7's
  design notes). For a pilot, either extend the TTL generously or
  accept that institutes fetch/share reports on the student's behalf
  via the admin view.
- **Interview questions are a small static/heuristic bank** unless a
  real `AI_PROVIDER` is configured — 2–3 questions per topic, not
  genuinely adaptive without AI wired in.
- **No student-facing password/account recovery** — there are no
  student accounts to recover; access is purely via the emailed
  interview link.

## Pre-pilot infrastructure checklist

Actual deployment target and provider choices are yours to make — this
is what needs a real value before go-live, not what to choose:

- [ ] Real `SECRET_KEY` (long, random, generated once, stored in a
      secrets manager — not committed anywhere)
- [ ] Managed PostgreSQL, with automated backups turned on
- [ ] Managed Redis
- [ ] Real S3 bucket (private, versioning on for resumes), IAM
      credentials scoped to just that bucket
- [ ] `AI_PROVIDER=anthropic` + real `AI_API_KEY`, tested against a
      handful of real resumes/interviews before the pilot starts
- [ ] Decide `STT_PROVIDER`/`TTS_PROVIDER`/`AVATAR_PROVIDER` — or
      consciously leave them `none` for a text-only pilot, which is a
      completely reasonable choice for a first pilot
- [ ] Real mail provider (`MAIL_PROVIDER=ses` or `smtp` — currently
      `console`, which only logs; institute admins and students will
      never receive a real verification/invite email otherwise)
- [ ] `SENTRY_DSN` set, and confirm errors actually arrive there
- [ ] `FRONTEND_ORIGIN` set to the real deployed frontend URL (CORS
      will silently block everything otherwise)
- [ ] `COOKIE_DOMAIN` set correctly if frontend/backend are on
      different subdomains
- [ ] HTTPS terminated in front of both services — `COOKIE_SECURE=True`
      in `ProductionConfig` means cookies won't be set over plain HTTP
      at all
- [ ] Run the actual migration chain (`flask db upgrade`) against the
      real production database once, verify it end-to-end
- [ ] `python manage.py seed-roles` run once against production

## Suggested pilot runbook

1. **Pick one real institute contact** who will register the account
   themselves (don't register on their behalf — this is also your
   first real test of the registration/verification email flow).
2. **Start with a small roster** — 5–10 students, one campaign, text-
   only answers (leave STT/TTS/avatar off). Prove the core loop works
   before adding voice.
3. **Watch, don't assume**: the interview flow, the AI-generated
   questions' relevance, evaluation scores' plausibility, and report
   quality all need a human to actually read them and judge if they're
   reasonable — none of that was possible to verify in this sandbox.
4. **Have a rollback plan** for the AI provider specifically: if
   `AI_PROVIDER=anthropic` produces bad output, dropping back to
   `AI_PROVIDER=none` (heuristic) mid-pilot is a config change, not a
   deploy — confirm that's actually true in your environment before
   you need it.
5. **Collect feedback structurally**: what confused a student in the
   lobby/device-check steps, whether round timing felt right, whether
   report language felt fair — this maps directly to Phase 15
   ("Improve Based On Real Users") and is what that phase should
   actually be built from, not guesses.
6. **Don't scale past one institute** until the AI provider costs,
   Celery worker throughput, and S3 storage growth have all been
   observed for real, not estimated.

## Development pass update (2026-10-12)

Additional development work has been applied after the original audit:

- Added campus CRUD and campus association fields for students/campaigns.
- Added a tenant-aware company catalog and company/job-description campaign fields.
- Added an institute-owned question bank with technical/managerial/HR categories, difficulty, role, company and evaluation criteria.
- Added campaign question source selection (`ai`, `custom`, `mixed`) and connected curated questions to interview round creation with AI fallback.
- Added campus and question-bank frontend pages; updated campaign and student forms to use the new data.
- Added SMTP/SES mail delivery configuration and a frontend session refresh retry.

Still not confirmed as production-ready: external AI/STT/TTS/avatar provider calls, real mail delivery, clean Docker/PostgreSQL migration execution, Celery worker integration, full browser end-to-end flow, PDF report export, and student self-service resume intake. These need actual runtime testing and provider credentials where applicable. See `COMPLETION_STATUS.md` for the current handoff checklist.
