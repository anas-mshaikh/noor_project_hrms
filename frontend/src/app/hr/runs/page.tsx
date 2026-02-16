"use client";

import * as React from "react";
import Link from "next/link";
import { Sparkles, Zap } from "lucide-react";
import { toast } from "sonner";
import { useTranslation } from "@/lib/i18n";

import { Button } from "@/components/ui/button";
import { HrPageShell } from "@/features/hr/components/layout/HrPageShell";
import { HrHeader } from "@/features/hr/components/layout/HrHeader";
import { GradientButton } from "@/features/hr/components/cards/GradientButton";
import { DataTable } from "@/features/hr/components/tables/DataTable";
import { TagChip } from "@/features/hr/components/candidates/TagChip";
import { PanelCard } from "@/features/hr/components/cards/PanelCard";
import { useMockLoading } from "@/features/hr/hooks/useMockLoading";
import { HR_RUNS } from "@/features/hr/mock/data";
import type { HrScreeningRun } from "@/features/hr/mock/types";

export default function HRRunsPage() {
  const { t } = useTranslation();
  const { loading } = useMockLoading(600);

  const runs = HR_RUNS.slice().sort((a, b) => b.created_at.localeCompare(a.created_at));

  return (
    <HrPageShell>
      <HrHeader
        title={t("hr.runs_page.title", { defaultValue: "Screening Runs" })}
        subtitle={t("hr.runs_page.subtitle", {
          defaultValue:
            "Async screening runs (retrieve + rerank + explain) — UI-only for now.",
        })}
        actions={
          <>
            <GradientButton
              onClick={() =>
                toast(t("common.coming_soon", { defaultValue: "Coming soon" }), {
                  description: t("hr.runs_page.create_run", { defaultValue: "Create run" }),
                })
              }
            >
              <Sparkles className="h-4 w-4" />
              {t("hr.runs_page.new_run", { defaultValue: "New Run" })}
            </GradientButton>
            <Button
              type="button"
              variant="outline"
              className="border-white/10 bg-white/[0.03] hover:bg-white/[0.06]"
              onClick={() =>
                toast(t("common.coming_soon", { defaultValue: "Coming soon" }), {
                  description: t("hr.runs_page.run_templates", { defaultValue: "Run templates" }),
                })
              }
            >
              <Zap className="h-4 w-4" />
              {t("hr.runs_page.templates", { defaultValue: "Templates" })}
            </Button>
          </>
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="lg:col-span-8">
          <DataTable
            loading={loading}
            columns={[
              {
                key: "run",
                header: t("hr.runs_page.col_run", { defaultValue: "Run" }),
                className: "col-span-6",
                cell: (r: HrScreeningRun) => (
                  <Link href={`/hr/runs/${r.id}`} className="text-sm font-medium hover:underline">
                    {r.title}
                  </Link>
                ),
              },
              {
                key: "status",
                header: t("hr.runs_page.col_status", { defaultValue: "Status" }),
                className: "col-span-2",
                cell: (r: HrScreeningRun) => (
                  <TagChip className="bg-white/[0.03]">{r.status}</TagChip>
                ),
              },
              {
                key: "progress",
                header: t("hr.runs_page.col_progress", { defaultValue: "Progress" }),
                className: "col-span-4",
                cell: (r: HrScreeningRun) => (
                  <div className="text-xs text-muted-foreground tabular-nums">
                    {r.progress_done}/{r.progress_total}
                  </div>
                ),
              },
            ]}
            rows={runs}
            rowKey={(r: HrScreeningRun) => r.id}
            emptyTitle={t("hr.runs_page.empty_title", { defaultValue: "No runs yet" })}
            emptyDescription={t("hr.runs_page.empty_description", {
              defaultValue: "Create a screening run to generate ranked candidates.",
            })}
          />
        </div>

        <div className="space-y-6 lg:col-span-4">
          <PanelCard
            title={t("hr.runs_page.how_title", { defaultValue: "How runs work" })}
            description={t("hr.runs_page.how_description", { defaultValue: "Demo-focused overview." })}
          >
            <div className="space-y-3 text-sm text-muted-foreground">
              <div className="rounded-2xl bg-white/[0.02] p-3 ring-1 ring-white/5">
                {t("hr.runs_page.how_step_1", {
                  defaultValue: "Retrieve top-K via embeddings (BGE-M3)",
                })}
              </div>
              <div className="rounded-2xl bg-white/[0.02] p-3 ring-1 ring-white/5">
                {t("hr.runs_page.how_step_2", { defaultValue: "Rerank with bge-reranker-v2-m3" })}
              </div>
              <div className="rounded-2xl bg-white/[0.02] p-3 ring-1 ring-white/5">
                {t("hr.runs_page.how_step_3", {
                  defaultValue: "Generate structured explanations (Gemini)",
                })}
              </div>
            </div>
          </PanelCard>
        </div>
      </div>
    </HrPageShell>
  );
}
