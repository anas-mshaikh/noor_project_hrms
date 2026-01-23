"use client";

import * as React from "react";
import Link from "next/link";
import { toast } from "sonner";
import { UserPlus } from "lucide-react";

import { HrPageShell } from "@/features/hr/components/layout/HrPageShell";
import { HrHeader } from "@/features/hr/components/layout/HrHeader";
import { GradientButton } from "@/features/hr/components/cards/GradientButton";
import { StatCard } from "@/features/hr/components/cards/StatCard";
import { GlassCard } from "@/features/hr/components/cards/GlassCard";
import { PanelCard } from "@/features/hr/components/cards/PanelCard";
import { ProgressRing } from "@/features/hr/components/onboarding/ProgressRing";
import { TagChip } from "@/features/hr/components/candidates/TagChip";
import { useMockLoading } from "@/features/hr/hooks/useMockLoading";
import { HR_ONBOARDING } from "@/features/hr/mock/data";

export default function HROnboardingPage() {
  const { loading } = useMockLoading(600);

  const active = HR_ONBOARDING.length;
  const pendingDocs = HR_ONBOARDING.reduce((acc, e) => acc + e.documents.filter((d) => d.status === "PENDING").length, 0);
  const completed = HR_ONBOARDING.filter((e) => e.progress_pct >= 90).length;

  return (
    <HrPageShell>
      <HrHeader
        title="Onboarding"
        subtitle="Checklists and document collection (UI-only)."
        actions={
          <GradientButton onClick={() => toast("Coming soon", { description: "Add onboarding employee" })}>
            <UserPlus className="h-4 w-4" />
            New onboarding
          </GradientButton>
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="space-y-6 lg:col-span-8">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <StatCard label="Active onboarding" value={active} loading={loading} />
            <StatCard label="Pending docs" value={pendingDocs} loading={loading} />
            <StatCard label="Completed" value={completed} loading={loading} />
          </div>

          <GlassCard className="p-5">
            <div className="text-sm font-semibold tracking-tight">Employees</div>
            <div className="mt-4 space-y-3">
              {loading ? (
                Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="h-16 rounded-2xl bg-white/[0.03] ring-1 ring-white/10" />
                ))
              ) : (
                HR_ONBOARDING.map((e) => (
                  <Link
                    key={e.employee_id}
                    href={`/hr/onboarding/${e.employee_id}`}
                    className="flex items-center justify-between gap-3 rounded-2xl bg-white/[0.02] p-4 ring-1 ring-white/5 hover:bg-white/[0.05]"
                  >
                    <div className="min-w-0">
                      <div className="text-sm font-medium">
                        {e.name} <span className="text-muted-foreground">({e.employee_code})</span>
                      </div>
                      <div className="mt-1 flex flex-wrap gap-2 text-xs text-muted-foreground">
                        <TagChip className="bg-white/[0.03]">{e.department}</TagChip>
                        <TagChip className="bg-white/[0.03]">{e.tasks.filter((t) => t.status !== "DONE").length} tasks open</TagChip>
                      </div>
                    </div>
                    <ProgressRing value={e.progress_pct} />
                  </Link>
                ))
              )}
            </div>
          </GlassCard>
        </div>

        <div className="space-y-6 lg:col-span-4">
          <PanelCard title="What’s next" description="Demo-only guidance.">
            <div className="space-y-3 text-sm text-muted-foreground">
              <div className="rounded-2xl bg-white/[0.02] p-3 ring-1 ring-white/5">
                Upload missing documents for faster activation.
              </div>
              <div className="rounded-2xl bg-white/[0.02] p-3 ring-1 ring-white/5">
                Provision mobile access as the final step.
              </div>
            </div>
          </PanelCard>
        </div>
      </div>
    </HrPageShell>
  );
}

