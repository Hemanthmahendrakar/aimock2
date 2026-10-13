# EC2 local file storage + API connection fix

This build replaces MinIO with a persistent host directory and routes browser API requests through Next.js to the Flask API over the Docker network.

## What changed

- Uploaded files are stored on the EC2 host under `./storage/uploads/` (relative to `docker-compose.yml`).
- API and Celery worker mount that same directory at `/app/storage/uploads`.
- Local file links are short-lived HMAC-signed API URLs; the upload directory is not public.
- The browser uses same-origin `/api/...` requests. Next.js proxies those requests to `http://api:8000`, fixing the old `localhost:8000` issue where a student's browser tried to call their own computer.
- API health endpoint is `/api/v1/health`. The bare `/` route is not defined and returns 404 by design. `/api/v1/institute/auth/me` returns 401 if there is no logged-in session.

## Before deploying over an existing MinIO installation

If MinIO already contains resumes or logos, migrate them before recreating the stack. Do not delete the old `minio_data` volume until the migration and verification are complete.

1. Back up the project and database first.
2. Upload/extract this project update into the existing project directory, preserving `services/api/.env` and the PostgreSQL volume.
3. While the existing containers are still running, copy MinIO objects into the currently bind-mounted API directory:

   ```bash
   docker compose exec api python scripts/migrate_minio_to_local.py
   ```

   The default script reads `http://minio:9000`, bucket `mock-interview-dev`, and the current development credentials. Override `OLD_MINIO_ENDPOINT`, `OLD_MINIO_ACCESS_KEY`, `OLD_MINIO_SECRET_KEY`, and `OLD_MINIO_BUCKET` if yours differ.

4. The script initially writes to `services/api/storage/uploads` because the currently running container bind-mounts `services/api` at `/app`. Copy the files to the new project-level storage directory on the host:

   ```bash
   mkdir -p storage/uploads
   if [ -d services/api/storage/uploads ]; then cp -a services/api/storage/uploads/. storage/uploads/; fi
   ```

5. Recreate the stack using the updated Compose file:

   ```bash
   mkdir -p storage/uploads
   docker compose config
   docker compose up -d --build --remove-orphans
   docker compose ps
   curl -i http://127.0.0.1:8000/api/v1/health
   curl -i http://127.0.0.1:3000/api/v1/health
   ```

   Both health requests should return HTTP 200 with a successful JSON response.

6. Test login, resume upload, resume download, and institute logo upload. Keep MinIO and its volume until those checks pass. Then remove the old MinIO container/service and storage only after you are certain no old files are needed.

## Important production notes

- Set a strong, random `SECRET_KEY` in the host `.env` before deploying.
- This Compose file sets `COOKIE_SECURE=false` for HTTP/IP-based testing. Once HTTPS is configured, set `COOKIE_SECURE=true` and set `FRONTEND_ORIGIN` to your HTTPS site origin.
- The current compose file still exposes PostgreSQL and Redis ports. For production, remove their host `ports:` mappings unless you have a specific private administration requirement, and restrict inbound EC2 security-group rules. Do not publicly expose the upload directory.
- This changes storage implementation; it does not automatically make the entire application feature-complete. If the API still fails, inspect `docker compose logs --tail=200 api web` and test the health endpoint above.
