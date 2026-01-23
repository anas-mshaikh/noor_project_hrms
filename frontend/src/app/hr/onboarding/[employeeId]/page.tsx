"use client";

import * as React from "react";
import Link from "next/link";
import { toast } from "sonner";
import { ArrowLeft, Smartphone, UploadCloud } from "lucide-react";

import { Button } from "@/components/ui/button";
import { HrPageShell } from "@/features/hr/components/layout/HrPageShell";
import { HrHeader } from "@/features/hr/components/layout/HrHeader";
import { GradientButton } from "@/features/hr/components/cards/GradientButton";
import { GlassCard } from "@/features/hr/components/cards/GlassCard";
import { EmptyStateCard } from "@/features/hr/components/cards/EmptyStateCard";
import { PanelCard } from "@/features/hr/components/cards/PanelCard";
import { ProgressRing } from "@/features/hr/components/onboarding/ProgressRing";
import { OnboardingChecklist } from "@/features/hr/components/onboarding/OnboardingChecklist";
import { DocumentTile } from "@/features/hr/components/onboarding/DocumentTile";
import { useMockLoading } from "@/features/hr/hooks/useMockLoading";
import { getOnboardingEmployee } from "@/features/hr/mock/data";

type PageProps = { params: { employeeId: string } };

export default function HROnboardingEmployeePage({ params }: PageProps) {
  const { loading } = useMockLoading(600);
  const emp = getOnboardingEmployee(params.employeeId);

  return (
    <HrPageShell>
      <HrHeader
        title={emp ? emp.name : "Onboarding"}
        subtitle={emp ? `${emp.department} • ${emp.employee_code}` : `employee_id: ${params.employeeId}`}
        actions={
          <>
            <Button asChild variant="ghost" className="rounded-2xl">
              <Link href="/hr/onboarding">
                <ArrowLeft className="h-4 w-4" />
                Back
              </Link>
            </Button>
            <GradientButton onClick={() => toast("Coming soon", { description: "Request document" })}>
              <UploadCloud className="h-4 w-4" />
              Request doc
            </GradientButton>
          </>
        }
      />

      {!emp && !loading ? (
        <EmptyStateCard
          title="Employee not found"
          description="This is demo data. Go back to Onboarding to pick an employee."
          actions={
            <GradientButton asChild>
              <Link href="/hr/onboarding">Back to onboarding</Link>
            </GradientButton>
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          <div className="space-y-6 lg:col-span-8">
            <GlassCard className="p-5">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="text-sm font-semibold tracking-tight">Checklist</div>
                  <div className="mt-1 text-sm text-muted-foreground">Mark tasks as done once completed (UI-only).</div>
                </div>
                <ProgressRing value={emp?.progress_pct ?? 0} />
              </div>
              <div className="mt-4">
                {loading || !emp ? (
                  <div className="space-y-2">
                    {Array.from({ length: 4 }).map((_, i) => (
                      <div key={i} className="h-14 rounded-2xl bg-white/[0.03] ring-1 ring-white/10" />
                    ))}
                  </div>
                ) : (
                  <OnboardingChecklist tasks={emp.tasks} />
                )}
              </div>
            </GlassCard>

            <GlassCard className="p-5">
              <div className="text-sm font-semibold tracking-tight">Documents</div>
              <div className="mt-1 text-sm text-muted-foreground">Upload and verify documents (UI-only).</div>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                {loading || !emp ? (
                  Array.from({ length: 4 }).map((_, i) => (
                    <div key={i} className="h-16 rounded-2xl bg-white/[0.03] ring-1 ring-white/10" />
                  ))
                ) : (
                  emp.documents.map((d) => <DocumentTile key={d.id} doc={d} />)
                )}
              </div>
            </GlassCard>
          </div>

          <div className="space-y-6 lg:col-span-4">
            <PanelCard title="Provision mobile access" description="This will call backend in a later phase.">
              <Button
                type="button"
                className="w-full rounded-2xl bg-white/[0.06] hover:bg-white/[0.09]"
                onClick={() => toast("Coming soon", { description: "Provision mobile access" })}
              >
                <Smartphone className="h-4 w-4" />
                Provision access
              </Button>
            </PanelCard>

            <PanelCard title="Notes" description="Internal notes (mock).">
              <div className="rounded-2xl bg-white/[0.02] p-4 text-sm text-muted-foreground ring-1 ring-white/5">
                Keep onboarding notes here (Phase 7).
              </div>
            </PanelCard>
          </div>
        </div>
      )}
    </HrPageShell>
  );
}

