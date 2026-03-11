"use client";

import * as React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { parseUuidParam } from "@/lib/guards";
import type { MssEmployeeProfileOut } from "@/lib/types";
import { getTeamMember } from "@/features/mss/api/mss";
import { mssKeys } from "@/features/mss/queryKeys";

import { DSCard } from "@/components/ds/DSCard";
import { EmptyState } from "@/components/ds/EmptyState";
import { ErrorState } from "@/components/ds/ErrorState";
import { PageHeader } from "@/components/ds/PageHeader";
import { RightPanelStack } from "@/components/ds/RightPanelStack";
import { StatusChip } from "@/components/ds/StatusChip";
import { EntityProfileTemplate } from "@/components/ds/templates/EntityProfileTemplate";
import { Button } from "@/components/ui/button";

function formatId(id: string | null | undefined): string {
  if (!id) return "—";
  return id.length > 10 ? `${id.slice(0, 8)}…` : id;
}

export default function MssTeamMemberPage({ params }: { params: { employeeId?: string } }) {
  const routeParams = useParams() as { employeeId?: string | string[] };
  const employeeIdRaw =
    (Array.isArray(routeParams.employeeId) ? routeParams.employeeId[0] : routeParams.employeeId) ??
    params?.employeeId ??
    null;
  const employeeId = parseUuidParam(employeeIdRaw);
  const profileQ = useQuery({
    queryKey: employeeId ? mssKeys.member(employeeId) : ["mss", "member", "invalid", employeeIdRaw ?? "missing"],
    queryFn: () => getTeamMember(employeeId as string),
    enabled: Boolean(employeeId),
  });

  if (!employeeIdRaw) {
    return (
      <ErrorState
        title="Missing employee id"
        error={new Error("Open a team member from the team list.")}
        details={
          <Button asChild variant="outline">
            <Link href="/mss/team">Back to team</Link>
          </Button>
        }
      />
    );
  }

  if (!employeeId) {
    return (
      <ErrorState
        title="Invalid employee id"
        error={new Error(`Got: ${String(employeeIdRaw)}`)}
        details={
          <Button asChild variant="outline">
            <Link href="/mss/team">Back to team</Link>
          </Button>
        }
      />
    );
  }

  const profile = profileQ.data as MssEmployeeProfileOut | undefined;

  if (profileQ.error) {
    return (
      <ErrorState
        title="Could not load team member"
        error={profileQ.error}
        onRetry={profileQ.refetch}
      />
    );
  }

  return (
    <EntityProfileTemplate
      header={
        <PageHeader
          title={profile ? profile.employee.employee_code : "Team member"}
          subtitle={
            profile
              ? `${profile.person.first_name} ${profile.person.last_name}`.trim()
              : `Employee ID: ${employeeId}`
          }
          actions={
            <Button asChild variant="outline">
              <Link href="/mss/team">Back</Link>
            </Button>
          }
        />
      }
      main={
        profileQ.isLoading ? (
          <DSCard surface="card" className="p-[var(--ds-space-20)]">
            <div className="text-sm text-text-2">Loading…</div>
          </DSCard>
        ) : !profile ? (
          <EmptyState title="Not found" description="This employee does not exist or is not visible to you." />
        ) : (
          <div className="space-y-6">
            <DSCard surface="card" className="p-[var(--ds-space-20)]">
              <div className="text-sm font-semibold tracking-tight text-text-1">
                Overview
              </div>
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-4">
                  <div className="text-xs text-text-2">Status</div>
                  <div className="mt-1">
                    <StatusChip status={profile.employee.status} />
                  </div>
                </div>
                <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-4">
                  <div className="text-xs text-text-2">Join date</div>
                  <div className="mt-1 text-sm text-text-1">
                    {profile.employee.join_date ?? "—"}
                  </div>
                </div>
              </div>
            </DSCard>

            <DSCard surface="card" className="p-[var(--ds-space-20)]">
              <div className="text-sm font-semibold tracking-tight text-text-1">
                Contact
              </div>
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-4">
                  <div className="text-xs text-text-2">Email</div>
                  <div className="mt-1 text-sm text-text-1">
                    {profile.person.email ?? "—"}
                  </div>
                </div>
                <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-4">
                  <div className="text-xs text-text-2">Phone</div>
                  <div className="mt-1 text-sm text-text-1">
                    {profile.person.phone ?? "—"}
                  </div>
                </div>
              </div>
            </DSCard>
          </div>
        )
      }
      right={
        <RightPanelStack>
          <DSCard surface="panel" className="p-[var(--ds-space-20)]">
            <div className="text-sm font-semibold tracking-tight text-text-1">
              Employment (current)
            </div>
            <div className="mt-3 space-y-2 text-sm text-text-2">
              <div>
                <span className="text-text-3">branch</span>:{" "}
                <span className="text-text-1">
                  {profile?.current_employment?.branch_id
                    ? formatId(profile.current_employment.branch_id)
                    : "—"}
                </span>
              </div>
              <div>
                <span className="text-text-3">org unit</span>:{" "}
                <span className="text-text-1">
                  {profile?.current_employment?.org_unit_id
                    ? formatId(profile.current_employment.org_unit_id)
                    : "—"}
                </span>
              </div>
              <div>
                <span className="text-text-3">manager</span>:{" "}
                <span className="text-text-1">
                  {profile?.manager ? profile.manager.display_name : "—"}
                </span>
              </div>
            </div>
          </DSCard>
        </RightPanelStack>
      }
    />
  );
}
