# AI Mock Interview Platform — Phases 1–13, plus Phase 14 (Pilot Readiness)

**Phase 1**: Institute Authentication (register, login, logout, email
verification, forgot/reset password, JWT sessions, tenant isolation).

**Phase 2**: Institute Profile & Branding (view/update institute details,
logo upload/delete via S3-compatible storage, primary/secondary brand
colors).

**Phase 3**: Student Management (add, list/search/filter, update, remove,
and CSV bulk import students). Students are data records managed by the
institute admin — not login accounts; student authentication is a
separate, interview-scoped session introduced in Phase 7.

**Phase 4**: Campaign Management (create interview drives with round
durations, difficulty, question categories; draft → active → completed
lifecycle, archivable from any state; assign/unassign students to a
campaign's roster).

**Phase 5**: Interview Configuration (reusable `InterviewTemplate` presets
— per-round duration, question categories/focus areas, evaluation
criteria weights, instructions for the AI interviewer — that a campaign
can be created from; explicit campaign fields always override the
template's values).

**Phase 6**: Resume Collection (upload PDF/DOCX to S3, versioned per
student, deterministic text extraction, heuristic structured candidate
profile: education, skills, languages, technologies, projects,
internships, experience, certifications, achievements). Runs as a Celery
background job, not inline on the upload request.

**Phase 7**: Interview Engine. Activating a campaign issues one
token-based interview invite per roster student. The student flow —
access-token exchange, resume/device checks, round-by-round questions
with a live timer, answer submission — is a completely separate trust
boundary from institute-admin auth (its own session JWT/cookie, never
touching `g.current_user`). Round progression is time- and
completion-driven, recomputed against wall-clock time on every request
rather than a scheduled sweep.

**Phase 8**: AI Question Engine. A real AI Gateway (`app/ai/`) backs both
resume analysis and interview questions — a provider interface, an
Anthropic-backed provider, and a heuristic/offline fallback that's what
tests and `AI_PROVIDER=none` (the default) actually run against. Each
round starts with `QUESTIONS_PER_ROUND_TARGET` (default 3) questions;
after every answer, the gateway decides whether a follow-up is warranted
(a short/vague answer gets probed, a thorough one doesn't), capped at
`MAX_QUESTIONS_PER_ROUND` (default 6). If the configured provider fails
for any reason, the gateway falls back to the heuristic provider for
that call rather than let the request fail — logged, never silently
swallowed.

**Phase 9**: Technical + Managerial + HR round specialization
(`round_competencies.py`). Each round draws from the spec's exact
subject/competency lists — technical: DSA, algorithms, OOP, DBMS, OS,
networks; managerial: decision making, ownership, teamwork, conflict
handling, leadership, problem solving, prioritization, project
understanding; HR: professional communication, self-awareness,
motivation, career goals, strengths/weaknesses, professional behavior,
role alignment — with a campaign's own `question_categories` /
`evaluation_criteria` taking precedence over these defaults when set.
Managerial questions are phrased as scenarios ("Imagine...", "Describe a
situation..."). Technical questions occasionally reference a skill
straight off the candidate's resume. Every question carries a `topic`
tag (admin-visible only) so Phase 10's evaluation engine can grade
against the right rubric dimension.

**Phase 10**: Evaluation Engine. When an interview reaches COMPLETED (end
of the HR round), a background Celery task grades it across four
independent dimensions — technical, managerial, HR (each from that
round's Q&A), and communication (across every answer in the interview,
since how someone communicates isn't confined to one round) — using the
spec's exact rubric criteria per dimension. Each `Evaluation` row carries
a score (0-100), per-criterion sub-scores, evidence, strengths,
weaknesses, and improvement suggestions — never a single generic-prompt
blob. The heuristic evaluator is deliberately honest about its limits:
it scores response completeness (filler words, repetition, pace, length)
and explicitly refuses to claim it can judge technical correctness or
reasoning quality — capped well below a perfect score, with that
limitation stated directly in the evidence field. Real AI evaluation
(`AI_PROVIDER=anthropic`) is explicitly instructed never to make
personality or psychological judgments, per the spec's caution.

Nothing beyond Phase 10 is implemented yet (no student-facing reports,
analytics).

## Stack

- **Frontend**: Next.js 14 (App Router) + TypeScript + Tailwind
- **Backend**: Flask (application factory) + Gunicorn
- **DB**: PostgreSQL + SQLAlchemy + Alembic
- **Cache/rate-limit store / Celery broker**: Redis
- **Object storage**: S3-compatible (MinIO locally)
- **Background jobs**: Celery (resume processing, evaluation)
- **AI**: `app/ai/` gateway — Anthropic provider + heuristic/offline fallback
- **Auth**: hand-rolled — Argon2id password hashing, JWT access tokens
  (httpOnly cookie) + rotating refresh tokens (hashed at rest), email
  verification and password reset via hashed single-use tokens. Student
  interview sessions are a **separate** JWT/cookie, a completely
  different trust boundary from institute-admin auth.

## Project layout

```
services/api/          Flask backend
  app/
    config/             environment-driven settings
    extensions/         db, migrate, cors, limiter, celery singletons
    models/             Institute, User, Student, Campaign, InterviewTemplate,
                         Interview/InterviewRound/InterviewQuestion/InterviewAnswer,
                         Evaluation, Resume/ResumeVersion/CandidateProfile, AuditLog
    repositories/        DB access only, no business logic
    services/             AuthService, InstituteService, StudentService,
                         CampaignService, InterviewTemplateService,
                         InterviewService (state machine), EvaluationService,
                         round_competencies.py, evaluation_rubrics.py,
                         heuristic_evaluator.py, candidate_profile_builder.py
    ai/                  AI Gateway — provider interface, Anthropic provider,
                         heuristic/offline fallback (app/ai/gateway.py is the
                         only seam the rest of the app depends on)
    tasks/               Celery tasks: resume processing, interview evaluation
    routes/auth/           /api/v1/institute/auth/* endpoints
    routes/institutes/     /api/v1/institute/{profile,branding,logo} endpoints
    routes/students/       /api/v1/institute/students/* endpoints (CRUD + CSV import)
    routes/campaigns/      /api/v1/institute/campaigns/* endpoints (CRUD, lifecycle, roster)
    routes/interview_templates/  /api/v1/institute/interview-templates/* endpoints
    routes/resumes/         /api/v1/institute/students/<id>/resume/* endpoints
    routes/institute_interviews/  /api/v1/institute/interviews/* (admin: view incl. evaluations, cancel)
    routes/interview/       /api/v1/interview/* (student session: access, state, answers)
    routes/               institute dashboard placeholder, health check
    utils/                 authorization decorators (institute admin AND
                         interview-session, two separate trust boundaries),
                         JWT/token helpers, file validation
  migrations/            0001 auth, 0002 students, 0003 campaigns,
                         0004 interview templates, 0005 resumes,
                         0006 interview engine, 0007 question topic,
                         0008 evaluations — hand-written Alembic migrations
  tests/                 pytest — one file per phase area, plus
                         test_tenant_isolation.py
  celery_worker.py        Celery worker entrypoint
web/                   Next.js frontend
  app/institute/         login, register, forgot/reset password, verify-email,
                         dashboard, profile, settings (branding), students
                         (incl. per-student detail + resume upload), campaigns
                         (incl. per-interview status), interview-templates
  app/interview/[id]     student-facing interview session (no institute nav —
                         separate trust boundary, separate session cookie)
docker-compose.yml     local dev: postgres, redis, minio, api, worker, web
```

## Running locally

1. Copy env files:
   ```bash
   cp services/api/.env.example services/api/.env
   cp web/.env.example web/.env.local
   ```
   Generate a real `SECRET_KEY` for `services/api/.env` (don't use the
   placeholder in production):
   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

2. Start everything:
   ```bash
   docker compose up --build
   ```
   This brings up Postgres, Redis, MinIO, the Flask API (port 8000), a
   Celery worker (resume processing + evaluation), and Next.js (port
   3000). The `api` service runs `flask db upgrade` on boot, applying
   all migrations automatically.

3. Seed the roles table (one-time, first run only):
   ```bash
   docker compose exec api python manage.py seed-roles
   ```
   The `minio-init` service auto-creates the `mock-interview-dev` bucket on
   first boot. MinIO's web console is at `http://localhost:9001`
   (user/pass: `minioadmin`/`minioadmin`).

4. Visit `http://localhost:3000` — you'll land on `/institute/login`.
   Register a new institute, then check the API container logs
   (`docker compose logs -f api`) for the verification email link, since
   the dev `MAIL_PROVIDER=console` just logs instead of sending real email.

5. To exercise the full interview flow: add a student, create a campaign,
   assign the student, activate the campaign (this issues an interview
   invite — check the API logs for the invite link, same console-mail
   pattern), and open that link in a separate browser/incognito window
   (it's a completely different session from your institute-admin login).

6. To use real AI instead of the offline heuristic fallback, set
   `AI_PROVIDER=anthropic` and `AI_API_KEY=...` in `services/api/.env`.
   **The Anthropic provider was written without network access to test
   it end-to-end — verify it against the real API before relying on it.**

## Running tests

```bash
cd services/api
pip install -r requirements-dev.txt
export TEST_DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/mock_interview_test
pytest -v
```

Tests never require network access — `AI_PROVIDER` defaults to `none`
(the heuristic/offline provider) in the test config, and
`CELERY_TASK_ALWAYS_EAGER=True` runs background jobs synchronously
in-process rather than needing a real worker.

`test_tenant_isolation.py` and the tenant-isolation test classes within
each phase's test file are the most important tests here — they register
two institutes and explicitly try to access/modify one institute's data
using the other institute's authenticated session, confirming the
backend resolves scope from the session only, never from client-supplied
IDs.

## Manually verifying tenant isolation

1. Register Institute A, verify its email (via the console-logged link),
   log in.
2. Hit `GET /api/v1/institute/dashboard?institute_id=<institute-b-id>` — the
   response still returns Institute A's `institute_id`. The route code never
   reads `institute_id` from the request at all; it only reads
   `g.current_user.institute_id`, set by `require_auth` from the verified
   JWT.

## What's NOT in Phase 1-10

Student-facing reports (Phase 11) and institute analytics (Phase 12) are
not implemented — `Evaluation` rows exist and are visible to institute
admins via `GET /api/v1/institute/interviews/<id>`, but there's no
polished report view, no aggregate scoring/summary, and no dashboard.

Notes:
- `interview_templates`/`interview_template_rounds` (Phase 5) are authored
  configuration only, applied by copying values onto a Campaign at
  creation time. `interviews`/`interview_rounds` (Phase 7) are the live
  state of an actual conducted interview, copying its round durations
  from the Campaign at the moment the interview is created — editing a
  campaign or its template afterward never reshapes an interview already
  issued.
- The AI Gateway (Phase 8/10) implements five of the spec's six
  functions: `analyze_resume`, `generate_question`, `generate_followup`,
  `evaluate_answer`, `evaluate_communication`. `generate_report` belongs
  to Phase 11 and isn't declared on the provider interface yet.
- The Anthropic provider (`app/ai/providers/anthropic_provider.py`) was
  written without network access to test it end-to-end — verify it
  against the real API before relying on it in production.
- Every AI-touching record carries a version tag (`extraction_method`,
  `question_source`, `evaluation_source` — `heuristic_v1` vs `ai_v1`) so
  it's always possible to tell which path produced it, including after
  switching providers.
- The heuristic round evaluator (technical/managerial/HR) is explicitly
  NOT a content judge — it scores response completeness only, capped at
  70/100, with that limitation stated in its own evidence output. The
  heuristic communication evaluator IS a real, if partial, implementation
  (filler words, repetition, pace are genuinely measurable without
  language understanding).

## Security notes

- Passwords: Argon2id via `argon2-cffi`, never logged, never returned in
  API responses.
- Tokens: refresh tokens, email-verification tokens, password-reset
  tokens, and interview access tokens are all stored as SHA-256 hashes
  only — the raw value is never persisted, so a DB leak alone can't be
  used to forge a session.
- Institute-admin auth and student interview-session auth are two
  completely separate trust boundaries (different JWTs, different
  cookies, different authorization decorators in
  `app/utils/authorization.py`) — one can never be used to access the
  other's endpoints.
- Account lockout: 5 failed institute-admin logins locks the account for
  15 minutes.
- Rate limiting: auth endpoints have per-IP rate limits via Flask-Limiter
  + Redis.
- `institute_id` is **never** trusted from client input anywhere in the
  codebase — every institute-scoped lookup derives it from the
  authenticated session (`g.current_institute_id`).
- The Anthropic provider's API key is only ever placed in the request
  header, never logged or included in error messages; all provider
  failures are caught and degrade to the heuristic fallback rather than
  crash or leak internals.

## New institute resource features (development pass)

The project now includes an institute-scoped campus manager and question bank, plus a company catalog. After updating the code, apply the new migration before using these APIs:

```bash
docker compose exec api flask db upgrade
```

New endpoints (all require an authenticated institute administrator):

- `GET/POST /api/v1/institute/campuses`
- `PATCH/DELETE /api/v1/institute/campuses/<campus_id>`
- `GET/POST /api/v1/institute/companies`
- `GET/POST /api/v1/institute/question-bank`
- `PATCH/DELETE /api/v1/institute/question-bank/<question_id>`

The question bank supports technical, managerial and HR questions, expected-answer criteria, difficulty, role and optional company association. Campaigns now accept `company_id`, `campus_id`, `job_description`, and `question_source` (`ai`, `custom`, or `mixed`). In custom/mixed mode, the interview engine attempts to select matching institute questions and falls back to the configured AI gateway when the bank doesn't have enough matching questions.

The web app has `/institute/campuses` and `/institute/question-bank` pages. SMTP and AWS SES mail providers are configurable; `console` remains the default for local development. For SMTP, configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_USE_TLS`, and `MAIL_FROM_ADDRESS`. For SES, configure AWS credentials/role and `MAIL_SES_REGION`.

These additions have passed Python syntax compilation in the build environment. Full database-backed tests, frontend production build, Docker startup, and real external-provider delivery still need to be executed in an environment with the project dependencies, Docker, database and provider credentials available.


### First-run Docker note

The compose file allows `services/api/.env` to be absent for a basic local boot and supplies a development-only `SECRET_KEY`. Copy `.env.example` to `.env` when configuring providers. Replace all development secrets before any non-local deployment.
#   a i m o c k 1  
 #   a i m o c k 2  
 #   a i m o c k 2  
 #   a i m o c k 2  
 