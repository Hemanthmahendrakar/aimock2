// Mirrors the backend's password rule (app/schemas/auth_schemas.py) so
// users see the same requirement client-side before submitting.
export function passwordIssue(password: string): string | null {
  if (password.length < 10) return "Must be at least 10 characters.";
  if (!/[A-Za-z]/.test(password)) return "Must include at least one letter.";
  if (!/[0-9]/.test(password)) return "Must include at least one digit.";
  return null;
}

export function emailIssue(email: string): string | null {
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return "Enter a valid email.";
  return null;
}
