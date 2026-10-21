# Institute pilot: end-to-end acceptance checklist

This checklist validates the real journey rather than treating a successful container startup as proof that the product works.

## Start cleanly

From the project root in PowerShell:

```powershell
docker compose config
docker compose up --build -d
docker compose ps
Invoke-RestMethod http://localhost:8000/api/v1/health
```

Expected health response includes `status: ok`. Confirm `postgres`, `redis`, `minio`, `api`, `worker`, and `web` are running. The API container runs `flask db upgrade` on startup.

## Run automated backend checks

```powershell
docker compose exec api python manage.py seed-roles
docker compose exec api pytest -v
```

If `pytest` is not installed in the runtime image, install development dependencies inside the API container or use a dev image that installs `requirements-dev.txt`. Do not interpret a missing test runner as a passing test suite.

## UI journey

Open `http://localhost:3000` and complete each item with a fresh test institute:

- [ ] Register an institute and verify the verification flow (console mode logs links; a real email provider must be configured for delivery).
- [ ] Log in and open the institute dashboard.
- [ ] Create a campus at **Campuses**.
- [ ] Create a company at **Companies**.
- [ ] Add a question in **Question Bank**. Add at least the target number of questions for every round when using `custom` mode.
- [ ] Add a student and attach a resume through the supported institute resume flow.
- [ ] Create a campaign, selecting the campus, company, role, job description and question source.
- [ ] Assign the student to the campaign and activate it.
- [ ] Open the assigned interview as the student and complete each round.
- [ ] Confirm evaluation/report generation completes and the report is visible to the student/institute.
- [ ] Confirm institute analytics change based on the completed interview and filters work.
- [ ] Confirm the interview screen shows the institute identity/branding as expected.

## Background jobs and logs

```powershell
docker compose logs --tail=150 api
docker compose logs --tail=150 worker
docker compose logs --tail=150 web
```

Confirm Redis/Celery tasks actually execute; tests configured with eager tasks alone do not verify worker integration.

## Known external dependencies / limitations

- Real email delivery requires SMTP or SES configuration.
- Real AI generation requires a configured supported AI provider and valid credentials; otherwise the heuristic fallback may be used.
- Real speech/avatar experience depends on valid provider credentials and an implemented/configured avatar vendor. Do not present a placeholder avatar provider as a production integration.
- Do not use development secrets or default MinIO credentials in a public deployment.

## Failure report to capture

For a failing step, capture:

1. Exact UI step and timestamp.
2. Browser console error and failed request URL/status.
3. `docker compose ps` output.
4. Relevant service logs (`api`, `worker`, or `web`).
5. Test output, if applicable.

Remove passwords, access tokens, cookies, resume contents, and API keys before sharing logs.
