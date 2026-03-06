"use client";

/**
 * /settings/workflow layout
 *
 * Workflow admin console frame (T6 Settings console template).
 *
 * Notes:
 * - This layout is UI-only permission gating; backend remains authoritative.
 */

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { DSCard } from "@/components/ds/DSCard";
import { ErrorState } from "@/components/ds/ErrorState";
import { PageHeader } from "@/components/ds/PageHeader";
import { SettingsConsoleTemplate } from "@/components/ds/templates/SettingsConsoleTemplate";
import { Button } from "@/components/ui/button";

type SubnavItem = {
  href: string;
  title: string;
  description?: string;
  requiredPermissions?: string[];
};

const REQUIRED = ["workflow:definition:read", "workflow:definition:write"];

const SUBNAV: SubnavItem[] = [
  {
    href: "/settings/workflow/definitions",
    title: "Definitions",
    description: "Routing and approval steps",
    requiredPermissions: REQUIRED,
  },
];

function hasAnyPermission(required: string[] | undefined, granted: Set<string>): boolean {
  if (!required || required.length === 0) return true;
  return required.some((p) => granted.has(p));
}

function SubnavLink({ item, active }: { item: SubnavItem; active: boolean }) {
  return (
    <Button
      asChild
      variant="ghost"
      className={cn(
        "h-auto w-full justify-start rounded-[var(--ds-radius-16)] px-3 py-2 text-left",
        active ? "bg-surface-2 text-text-1" : "text-text-2 hover:bg-surface-2"
      )}
    >
      <Link href={item.href} aria-current={active ? "page" : undefined}>
        <div className="space-y-0.5">
          <div className="text-sm font-medium">{item.title}</div>
          {item.description ? <div className="text-xs text-text-3">{item.description}</div> : null}
        </div>
      </Link>
    </Button>
  );
}

export default function SettingsWorkflowLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const permissions = useAuth((s) => s.permissions);
  const user = useAuth((s) => s.user);

  const granted = React.useMemo(() => new Set(permissions ?? []), [permissions]);
  const canView = hasAnyPermission(REQUIRED, granted);
  const subnavItems = SUBNAV.filter((i) => hasAnyPermission(i.requiredPermissions, granted));

  return (
    <SettingsConsoleTemplate
      header={<PageHeader title="Workflow" subtitle="Definitions and routing configuration." />}
      subnav={
        <DSCard surface="panel" className="p-[var(--ds-space-12)]">
          <div className="space-y-1">
            {subnavItems.map((item) => (
              <SubnavLink
                key={item.href}
                item={item}
                active={pathname === item.href || pathname.startsWith(`${item.href}/`)}
              />
            ))}
          </div>
        </DSCard>
      }
      content={
        !user ? (
          <ErrorState
            title="Sign in required"
            error={new Error("Please sign in to manage workflow settings.")}
            details={
              <Button asChild variant="secondary">
                <Link href="/login">Sign in</Link>
              </Button>
            }
          />
        ) : !canView ? (
          <ErrorState
            title="Access denied"
            error={new Error("Your account does not have access to Workflow settings.")}
          />
        ) : (
          children
        )
      }
    />
  );
}

