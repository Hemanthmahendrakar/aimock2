import { cn } from "@/lib/cn";

export function Alert({
  variant = "info",
  children,
}: {
  variant?: "info" | "error" | "success";
  children: React.ReactNode;
}) {
  return (
    <div
      role={variant === "error" ? "alert" : "status"}
      className={cn(
        "rounded-md border px-3 py-2.5 text-sm",
        variant === "info" && "border-border bg-muted text-foreground",
        variant === "error" &&
          "border-destructive/30 bg-destructive/5 text-destructive",
        variant === "success" &&
          "border-primary/30 bg-primary/5 text-primary"
      )}
    >
      {children}
    </div>
  );
}
