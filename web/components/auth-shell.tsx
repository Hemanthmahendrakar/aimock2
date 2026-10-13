import { ReactNode } from "react";

const ROUNDS = [
  { label: "Technical", note: "DSA, fundamentals, resume projects" },
  { label: "Managerial", note: "Ownership, prioritization, scenarios" },
  { label: "HR", note: "Motivation, communication, fit" },
];

export function AuthShell({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div
        className="hidden flex-col justify-between p-12 lg:flex"
        style={{
          background: "hsl(var(--panel-ink))",
          color: "hsl(var(--panel-ink-foreground))",
        }}
      >
        <div>
          <p className="font-display text-2xl italic">Mock Interview Platform</p>
          <p className="mt-6 max-w-sm text-balance font-display text-3xl leading-snug">
            Give every student a rigorous, structured interview before it counts.
          </p>
        </div>

        <ol className="space-y-5">
          {ROUNDS.map((round, i) => (
            <li key={round.label} className="flex gap-4">
              <span
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-medium"
                style={{
                  border: "1px solid hsl(var(--panel-accent) / 0.5)",
                  color: "hsl(var(--panel-accent))",
                }}
              >
                {i + 1}
              </span>
              <div>
                <p className="font-medium">{round.label}</p>
                <p className="text-sm opacity-70">{round.note}</p>
              </div>
            </li>
          ))}
        </ol>

        <p className="text-sm opacity-60">Institute Mode</p>
      </div>

      <div className="flex items-center justify-center px-6 py-16">
        <div className="w-full max-w-sm space-y-8">
          <div className="space-y-2 lg:hidden">
            <p className="font-display text-xl italic">Mock Interview Platform</p>
          </div>
          <div className="space-y-1.5">
            <h1 className="font-display text-2xl">{title}</h1>
            {subtitle && (
              <p className="text-sm text-muted-foreground">{subtitle}</p>
            )}
          </div>
          {children}
        </div>
      </div>
    </div>
  );
}
