# Email verification removal

This project build removes email verification from the institute registration and login flow.

## Changes
- Institute registration creates an active institute and active admin account.
- Registration no longer creates verification tokens or sends verification emails.
- The `/api/v1/institute/auth/verify-email` endpoint and frontend verification page were removed.
- The frontend registration success state now tells the user to log in.
- Legacy accounts still marked `pending_verification` are activated after their password is successfully checked. Disabled accounts remain disabled.
- Password validation, password-based login, lockout, JWT cookies, refresh tokens, and role/tenant authorization remain in place.
- Password reset email functionality remains separate from email verification.

## Existing database
The old `email_verified_at` column and `email_verification_tokens` table may still exist in an already-initialized database because existing migration history is intentionally not rewritten. The application no longer maps or uses them. They can be dropped later through a new migration after confirming no other deployed version uses them.

## Validation
Python source files were checked with `compileall`. Full pytest execution requires installing `services/api/requirements-dev.txt` and `services/api/requirements.txt`; it could not run in the packaging environment because Flask is not installed there.
