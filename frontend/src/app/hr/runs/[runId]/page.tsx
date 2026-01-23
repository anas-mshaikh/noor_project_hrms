"use client";

import * as React from "react";
import { Search, Sparkles } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { HrPageShell } from "@/features/hr/components/layout/HrPageShell";
import { HrHeader } from "@/features/hr/components/layout/HrHeader";
import { GradientButton } from "@/features/hr/components/cards/GradientButton";
import { PanelCard } from "@/features/hr/components/cards/PanelCard";
import { CandidateCard } from "@/features/hr/components/candidates/CandidateCard";
import { CandidateDrawer } from "@/features/hr/components/candidates/CandidateDrawer";
import { useMockLoading } from "@/features/hr/hooks/useMockLoading";
import { getRunById, getRunResults } from "@/features/hr/mock/data";
import type { HrCandidate } from "@/features/hr/mock/types";

type PageProps = { params: { runId: string } };

export default function HRRunDetailPage({ params }: PageProps) {
  const { loading } = useMockLoading(600);
  const run = getRunById(params.runId);
  const results = getRunResults(params.runId);

  const [query, setQuery] = React.useState("");
  const [minScore, setMinScore] = React.useState(60);
  const [selected, setSelected] = React.useState<HrCandidate | null>(null);
  const [drawerOpen, setDrawerOpen] = React.useState(false);

  const filtered = results
    .filter((r) => r.candidate.score >= minScore)
    .filter((r) => {
      const q = query.trim().toLowerCase();
      if (!q) return true;
      return (
        r.candidate.name.toLowerCase().includes(q) ||
        r.candidate.tags.some((t) => t.toLowerCase().includes(q))
      );
    });

  return (
    <HrPageShell>
      <HrHeader
        title={run?.title ?? "Screening Run"}
        subtitle={`Status: ${run?.status ?? "—"} • run_id: ${params.runId}`}
        chips={["Wow screen", "Mock data"]}
        actions={
          <>
            <GradientButton onClick={() => toast("Coming soon", { description: "Recompute run" })}>
              <Sparkles className="h-4 w-4" />
              Recompute
            </GradientButton>
            <Button
              type="button"
              variant="outline"
              className="border-white/10 bg-white/[0.03] hover:bg-white/[0.06]"
              onClick={() => toast("Coming soon", { description: "Export" })}
            >
              Export
            </Button>
          </>
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="space-y-4 lg:col-span-8">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div className="relative w-full md:max-w-sm">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search candidates…"
                className="border-white/10 bg-white/[0.03] pl-9"
                aria-label="Search candidates"
              />
            </div>

            <div className="flex items-center gap-3">
              <div className="text-xs text-muted-foreground tabular-nums">Min score</div>
              <input
                type="range"
                min={0}
                max={100}
                value={minScore}
                onChange={(e) => setMinScore(Number(e.target.value))}
                className="w-44"
                aria-label="Minimum score"
              />
              <div className="w-10 text-right text-xs text-muted-foreground tabular-nums">{minScore}</div>
            </div>
          </div>

          <div className="space-y-3">
            {loading ? (
              Array.from({ length: 10 }).map((_, i) => (
                <div key={i} className="h-20 rounded-2xl bg-white/[0.03] ring-1 ring-white/10" />
              ))
            ) : (
              filtered.map((r) => (
                <CandidateCard
                  key={r.candidate.id}
                  candidate={r.candidate}
                  rank={r.rank}
                  meta={
                    r.candidate.has_explanation
                      ? "Explanation ready"
                      : "Generating explanation…"
                  }
                  onClick={() => {
                    setSelected(r.candidate);
                    setDrawerOpen(true);
                  }}
                />
              ))
            )}
          </div>
        </div>

        <div className="space-y-6 lg:col-span-4">
          <PanelCard title="Run status" description="Progress and quick actions (mock).">
            <div className="rounded-2xl bg-white/[0.02] p-4 text-sm text-muted-foreground ring-1 ring-white/5">
              {run ? (
                <div className="space-y-1">
                  <div className="tabular-nums">
                    {run.progress_done}/{run.progress_total}
                  </div>
                  <div className="text-xs text-muted-foreground">{run.status}</div>
                </div>
              ) : (
                <div>Run not found.</div>
              )}
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button
                type="button"
                variant="outline"
                className="border-white/10 bg-white/[0.03] hover:bg-white/[0.06]"
                onClick={() => toast("Coming soon", { description: "Cancel run" })}
              >
                Cancel
              </Button>
              <Button
                type="button"
                className="rounded-2xl bg-white/[0.06] hover:bg-white/[0.09]"
                onClick={() => toast("Coming soon", { description: "Add top to pipeline" })}
              >
                Add top 10 to pipeline
              </Button>
            </div>
          </PanelCard>

          <PanelCard
            title="Tip"
            description="Try filtering by a higher score to reduce noise."
          >
            <div className="rounded-2xl bg-white/[0.02] p-4 text-sm text-muted-foreground ring-1 ring-white/5">
              Open any candidate to see matched/missing requirements and evidence quotes (mock).
            </div>
          </PanelCard>
        </div>
      </div>

      <CandidateDrawer open={drawerOpen} onOpenChange={setDrawerOpen} candidate={selected} />
    </HrPageShell>
  );
}

