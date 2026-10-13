import { SelectHTMLAttributes, forwardRef } from "react";
import { cn } from "@/lib/cn";

export const Select = forwardRef<
  HTMLSelectElement,
  SelectHTMLAttributes<HTMLSelectElement>
>(({ className, children, ...props }, ref) => {
  return (
    <select
      ref={ref}
      className={cn(
        "focus-ring h-11 w-full rounded-md border border-border bg-white px-3 text-sm text-foreground",
        className
      )}
      {...props}
    >
      {children}
    </select>
  );
});
Select.displayName = "Select";
