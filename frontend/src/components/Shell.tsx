"use client";

/**
 * components/Shell.tsx
 *
 * Global layout wrapper:
 * - Sidebar navigation (desktop)
 * - Top bar with StorePicker (all sizes)
 * - Content container
 */

import Link from "next/link";
import { usePathname } from "next/navigation";

import { StorePicker } from "@/components/StorePicker";
import { useSelection } from "@/lib/selection";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  LayoutDashboard,
  Settings,
  Users,
  Video,
  PanelLeft,
  FileUp,
  Sparkles,
  Briefcase,
  Zap,
  LayoutGrid,
  UserPlus,
} from "lucide-react";

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  // We show these IDs as a tiny debug hint (helps while building MVP fast).
  const storeId = useSelection((s) => s.storeId);
  const cameraId = useSelection((s) => s.cameraId);

  const nav = [
    { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
    { href: "/setup", label: "Setup", icon: Settings },
    { href: "/employees", label: "Employees", icon: Users },
    { href: "/videos", label: "Videos", icon: Video },
    { href: "/admin/import", label: "Admin Import", icon: FileUp },
  ] as const;

  const hrNav = [
    { href: "/hr", label: "HR Overview", icon: Sparkles },
    { href: "/hr/openings", label: "Openings", icon: Briefcase },
    { href: "/hr/runs", label: "Runs", icon: Zap },
    { href: "/hr/pipeline", label: "Pipeline", icon: LayoutGrid },
    { href: "/hr/onboarding", label: "Onboarding", icon: UserPlus },
  ] as const;

  // Highlight nested routes under a section (e.g. /jobs/*, /reports/* under Videos).
  function isActive(href: string): boolean {
    if (href === "/videos") {
      return (
        pathname === "/videos" ||
        pathname.startsWith("/jobs/") ||
        pathname.startsWith("/reports/")
      );
    }
    if (href === "/hr") return pathname === "/hr";
    if (href.startsWith("/hr/")) return pathname === href || pathname.startsWith(`${href}/`);
    return pathname === href;
  }

  return (
    <div className="relative min-h-screen text-foreground">
      {/* App-wide "purple glass" backdrop so all pages feel cohesive. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(1200px_circle_at_10%_0%,rgba(168,85,247,0.22),transparent_55%),radial-gradient(900px_circle_at_85%_10%,rgba(236,72,153,0.16),transparent_55%),linear-gradient(to_bottom,rgba(2,6,23,1),rgba(15,23,42,0.96),rgba(2,6,23,1))]"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 -z-10 opacity-[0.045] mix-blend-overlay"
        style={{
          backgroundImage:
            "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.8' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='140' height='140' filter='url(%23n)' opacity='.35'/%3E%3C/svg%3E\")",
        }}
      />

      <div className="relative flex min-h-screen">
        {/* Desktop sidebar */}
        <aside className="hidden w-64 flex-col border-r border-border bg-white/[0.03] backdrop-blur-xl md:flex">
          <div className="flex h-14 items-center gap-2 border-b border-border px-4">
            <PanelLeft className="h-4 w-4 text-muted-foreground" />
            <Link href="/dashboard" className="font-semibold tracking-tight">
              Attendance Admin
            </Link>
          </div>

          <nav className="flex-1 p-2">
            {nav.map((item) => {
              const active = isActive(item.href);
              const Icon = item.icon;
              return (
                <Button
                  key={item.href}
                  asChild
                  variant="ghost"
                  className={cn(
                    "w-full justify-start",
                    active && "bg-accent text-accent-foreground"
                  )}
                >
                  <Link href={item.href}>
                    <Icon className="h-4 w-4" />
                    {item.label}
                  </Link>
                </Button>
              );
            })}

            <div className="mt-4 px-2 text-xs font-medium text-muted-foreground">
              HR Suite
            </div>
            {hrNav.map((item) => {
              const active = isActive(item.href);
              const Icon = item.icon;
              return (
                <Button
                  key={item.href}
                  asChild
                  variant="ghost"
                  className={cn(
                    "mt-1 w-full justify-start",
                    active && "bg-accent text-accent-foreground"
                  )}
                >
                  <Link href={item.href}>
                    <Icon className="h-4 w-4" />
                    {item.label}
                  </Link>
                </Button>
              );
            })}
          </nav>

          <div className="border-t border-border p-3">
            <div className="text-xs font-medium text-muted-foreground">
              Context
            </div>
            <div className="mt-2">
              <StorePicker />
            </div>
            <div className="mt-2 text-xs text-muted-foreground">
              {storeId ? `store_id: ${storeId}` : "Select a store"}
              {cameraId ? ` • camera_id: ${cameraId}` : ""}
            </div>
          </div>
        </aside>

        {/* Main column */}
        <div className="flex min-w-0 flex-1 flex-col">
          {/* Top bar (always visible, helps on mobile) */}
          <header className="sticky top-0 z-40 border-b border-border bg-white/[0.03] backdrop-blur-xl">
            <div className="mx-auto flex max-w-7xl flex-col gap-2 px-4 py-3 md:h-14 md:flex-row md:items-center md:gap-3 md:px-6 md:py-0">
              <div className="flex items-center gap-2 md:hidden">
                <PanelLeft className="h-4 w-4 text-muted-foreground" />
                <Link href="/dashboard" className="font-semibold">
                  Attendance Admin
                </Link>
              </div>

              <div className="ml-auto flex items-center gap-3">
                <div className="hidden text-xs text-muted-foreground md:block">
                  {storeId ? `store_id: ${storeId}` : "Select a store"}
                  {cameraId ? ` • camera_id: ${cameraId}` : ""}
                </div>
                <div className="md:hidden">
                  <StorePicker />
                </div>
              </div>

              {/* Mobile navigation (keeps the app usable on small screens). */}
              <nav className="flex flex-wrap items-center gap-1 md:hidden">
                {[...nav, ...hrNav].map((item) => {
                  const active = isActive(item.href);
                  const Icon = item.icon;
                  return (
                    <Button
                      key={item.href}
                      asChild
                      size="sm"
                      variant={active ? "secondary" : "ghost"}
                      className="justify-start"
                    >
                      <Link href={item.href}>
                        <Icon className="h-4 w-4" />
                        {item.label}
                      </Link>
                    </Button>
                  );
                })}
              </nav>
            </div>
          </header>

          <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 md:px-6">
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}
