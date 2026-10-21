"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { cn } from "@/lib/cn";
import { authApi } from "@/lib/api";

const NAV_ITEMS = [
  { href: "/institute/dashboard", label: "Dashboard" },
  { href: "/institute/students", label: "Students" },
  { href: "/institute/campuses", label: "Campuses" },
  { href: "/institute/companies", label: "Companies" },
  { href: "/institute/question-bank", label: "Question Bank" },
  { href: "/institute/campaigns", label: "Campaigns" },
  { href: "/institute/interview-templates", label: "Templates" },
  { href: "/institute/analytics", label: "Analytics" },
  { href: "/institute/profile", label: "Profile" },
  { href: "/institute/settings", label: "Branding" },
];

export function AppHeader() {
  const pathname = usePathname();
  const router = useRouter();

  async function handleLogout() {
    await authApi.logout();
    router.push("/institute/login");
  }

  return (
    <header className="border-b border-border">
      <div className="mx-auto flex max-w-3xl items-center justify-between px-6 py-5">
        <p className="font-display text-xl italic">Mock Interview Platform</p>
        <nav className="flex items-center gap-6">
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "text-sm text-muted-foreground hover:text-foreground",
                pathname === item.href && "font-medium text-foreground"
              )}
            >
              {item.label}
            </Link>
          ))}
          <button
            onClick={handleLogout}
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            Log out
          </button>
        </nav>
      </div>
    </header>
  );
}
