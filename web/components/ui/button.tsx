import { ButtonHTMLAttributes, forwardRef } from "react";
import { cn } from "@/lib/cn";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "ghost";
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", loading, disabled, children, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        className={cn(
          "focus-ring inline-flex h-11 w-full items-center justify-center rounded-md text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60",
          variant === "primary" &&
            "bg-primary text-primary-foreground hover:bg-primary/90",
          variant === "ghost" &&
            "bg-transparent text-foreground hover:bg-muted",
          className
        )}
        {...props}
      >
        {loading ? "Please wait…" : children}
      </button>
    );
  }
);
Button.displayName = "Button";
