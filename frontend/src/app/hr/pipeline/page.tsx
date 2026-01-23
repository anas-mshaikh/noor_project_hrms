"use client";

import * as React from "react";
import { toast } from "sonner";
import { Sparkles } from "lucide-react";

import { HrPageShell } from "@/features/hr/components/layout/HrPageShell";
import { HrHeader } from "@/features/hr/components/layout/HrHeader";
import { GradientButton } from "@/features/hr/components/cards/GradientButton";
import { PanelCard } from "@/features/hr/components/cards/PanelCard";
import { KanbanBoard } from "@/features/hr/components/pipeline/KanbanBoard";
import { CandidateDrawer } from "@/features/hr/components/candidates/CandidateDrawer";
import { HR_PIPELINE_CARDS, HR_PIPELINE_STAGES, HR_RUN_RESULTS_BY_ID } from "@/features/hr/mock/data";
import type { HrCandidate, HrPipelineStage } from "@/features/hr/mock/types";

function findCandidateById(id: string): HrCandidate | null {
  for (const results of Object.values(HR_RUN_RESULTS_BY_ID)) {
    const hit = results.find((r) => r.candidate.id === id);
    if (hit) return hit.candidate;
  }
  return null;
}

export default function HRPipelinePage() {
  const [cards, setCards] = React.useState(HR_PIPELINE_CARDS);
  const [selected, setSelected] = React.useState<HrCandidate | null>(null);
  const [drawerOpen, setDrawerOpen] = React.useState(false);

  function onMove(cardId: string, stageKey: HrPipelineStage["key"]) {
    setCards((prev) => prev.map((c) => (c.id === cardId ? { ...c, stage: stageKey } : c)));
    toast("Moved (mock)", { description: `→ ${stageKey}` });
  }

  function onOpenCandidate(cardId: string) {
    const candidate = findCandidateById(cardId);
    setSelected(candidate);
    setDrawerOpen(true);
  }

  return (
    <HrPageShell>
      <HrHeader
        title="Pipeline"
        subtitle="ATS-style board for candidate progression (UI-only)."
        actions={
          <GradientButton onClick={() => toast("Coming soon", { description: "Bulk actions" })}>
            <Sparkles className="h-4 w-4" />
            Bulk actions
          </GradientButton>
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="lg:col-span-9">
          <KanbanBoard
            stages={HR_PIPELINE_STAGES}
            cards={cards}
            onMove={onMove}
            onOpenCandidate={onOpenCandidate}
          />
        </div>

        <div className="space-y-6 lg:col-span-3">
          <PanelCard title="Stage conversion" description="Mock funnel stats.">
            <div className="space-y-3 text-sm text-muted-foreground">
              <div className="rounded-2xl bg-white/[0.02] p-3 ring-1 ring-white/5">
                Screened → Interview: <span className="text-foreground/90 tabular-nums">38%</span>
              </div>
              <div className="rounded-2xl bg-white/[0.02] p-3 ring-1 ring-white/5">
                Interview → Offer: <span className="text-foreground/90 tabular-nums">22%</span>
              </div>
              <div className="rounded-2xl bg-white/[0.02] p-3 ring-1 ring-white/5">
                Offer → Hired: <span className="text-foreground/90 tabular-nums">12%</span>
              </div>
            </div>
          </PanelCard>
        </div>
      </div>

      <CandidateDrawer open={drawerOpen} onOpenChange={setDrawerOpen} candidate={selected} />
    </HrPageShell>
  );
}

