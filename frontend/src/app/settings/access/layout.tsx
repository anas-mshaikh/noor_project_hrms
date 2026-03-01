"use client";

/**
 * /settings/access layout
 *
 * IAM console frame (T6 Settings console template).
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

const USERS_PERMS = ["iam:user:read", "iam:user:write"];
const ROLES_PERMS = ["iam:role:assign", "iam:user:read", "iam:user:write"];
const PERMS_PERMS = ["iam:permission:read"];

const ACCESS_SUBNAV: SubnavItem[] = [
  {
    href: "/settings/access/users",
    title: "Users",
    description: "Accounts and assignments",
    requiredPermissions: USERS_PERMS,
  },
  {
    href: "/settings/access/roles",
    title: "Roles",
    description: "Catalog (read-only)",
    requiredPermissions: ROLES_PERMS,
  },
  {
    href: "/settings/access/permissions",
    title: "Permissions",
    description: "Catalog (read-only)",
    requiredPermissions: PERMS_PERMS,
  },
];

function hasAnyPermission(required: string[] | undefined, granted: Set<string>): boolean {
  if (!required || required.length === 0) return true;
  return required.some((p) => granted.has(p));
}

function SubnavLink({
  item,
  active,
}: {
  item: SubnavItem;
  active: boolean;
}) {
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
          {item.description ? (
            <div className="text-xs text-text-3">{item.description}</div>
          ) : null}
        </div>
      </Link>
    </Button>
  );
}

export default function SettingsAccessLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const permissions = useAuth((s) => s.permissions);
  const user = useAuth((s) => s.user);

  const granted = React.useMemo(() => new Set(permissions ?? []), [permissions]);
  const canViewAccess = hasAnyPermission([...USERS_PERMS, ...ROLES_PERMS, ...PERMS_PERMS], granted);

  const subnavItems = ACCESS_SUBNAV.filter((i) => hasAnyPermission(i.requiredPermissions, granted));

  return (
    <SettingsConsoleTemplate
      header={
        <PageHeader
          title="Roles & Access"
          subtitle="Manage users, role assignments, and permission catalogs."
        />
      }
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
            error={new Error("Please sign in to manage access settings.")}
            details={
              <Button asChild variant="secondary">
                <Link href="/login">Sign in</Link>
              </Button>
            }
          />
        ) : !canViewAccess ? (
          <ErrorState
            title="Access denied"
            error={new Error("Your account does not have access to Roles & Access settings.")}
          />
        ) : (
          children
        )
      }
    />
  );
}

