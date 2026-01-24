"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useParams } from "next/navigation";
import { Search, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { HrPageShell } from "@/features/hr/components/layout/HrPageShell";
import { HrHeader } from "@/features/hr/components/layout/HrHeader";
import { PanelCard } from "@/features/hr/components/cards/PanelCard";
import { GradientButton } from "@/features/hr/components/cards/GradientButton";
import { EmptyStateCard } from "@/features/hr/components/cards/EmptyStateCard";
import { ScorePill } from "@/features/hr/components/candidates/ScorePill";
import { TagChip } from "@/features/hr/components/candidates/TagChip";
import { RunStatusPill } from "@/features/hr/components/runs/RunStatusPill";
import { RunResultDrawer } from "@/features/hr/components/runs/RunResultDrawer";
import { useMockLoading } from "@/features/hr/hooks/useMockLoading";
import { useScreeningRun } from "@/features/hr/hooks/useScreeningRun";
import { useScreeningResults } from "@/features/hr/hooks/useScreeningResults";
import { useExplainActions } from "@/features/hr/hooks/useExplainActions";
import { hrQueryKeys } from "@/features/hr/api/queryKeys";
import { cancelScreeningRun, retryScreeningRun } from "@/features/hr/api/hr";
import type { ScreeningResultRowOut, UUID } from "@/lib/types";

function scoreToPct(score: number): number {
  if (!Number.isFinite(score)) return 0;
  const pct = score <= 1.0 ? score * 100 : score;
  return Math.max(0, Math.min(100, Math.round(pct)));
}

export default function HRRunDetailPage() {
  const { loading } = useMockLoading(600);
  const router = useRouter();
  const queryClient = useQueryClient();

  // In production builds, `useParams()` is the most reliable way to read dynamic
  // segments from a client component (vs relying on the server-provided props).
  const routeParams = useParams() as { runId?: string };
  const runId = (routeParams.runId ?? null) as UUID | null;

  const runQ = useScreeningRun(runId);
  const run = runQ.data;

  const [query, setQuery] = React.useState("");
  const [minScore, setMinScore] = React.useState(60);
  const [selected, setSelected] = React.useState<ScreeningResultRowOut | null>(
    null
  );
  const [drawerOpen, setDrawerOpen] = React.useState(false);

  const [page, setPage] = React.useState(1);
  const pageSize = 50;

  const resultsQ = useScreeningResults(runId, {
    enabled: run?.status === "DONE",
    page,
    pageSize,
  });

  const explain = useExplainActions(runId);

  const cancelMut = useMutation({
    mutationFn: () => cancelScreeningRun(runId as UUID),
    onSuccess: (updated) => {
      queryClient.setQueryData(hrQueryKeys.screeningRun(runId), updated);
      toast("Run cancelled");
    },
    onError: (err) => {
      toast("Could not cancel run", {
        description: err instanceof Error ? err.message : "Unknown error",
      });
    },
  });

  const retryMut = useMutation({
    mutationFn: () => retryScreeningRun(runId as UUID),
    onSuccess: (newRun) => {
      toast("Retry started", { description: `run_id: ${newRun.id}` });
      router.push(`/hr/runs/${newRun.id}`);
    },
    onError: (err) => {
      toast("Could not retry run", {
        description: err instanceof Error ? err.message : "Unknown error",
      });
    },
  });

  if (!runId) {
    return (
      <HrPageShell>
        <HrHeader title="Screening Run" subtitle="Loading…" />
        <div className="mt-6">
          <EmptyStateCard
            title="Loading run…"
            description="Preparing route context."
            icon={Sparkles}
          />
        </div>
      </HrPageShell>
    );
  }

  if (runQ.isError) {
    return (
      <HrPageShell>
        <HrHeader title="Screening Run" subtitle="Could not load run." />
        <div className="mt-6">
          <EmptyStateCard
            title="Run not found"
            description={
              runQ.error instanceof Error ? runQ.error.message : "Unknown error"
            }
            icon={Sparkles}
            actions={
              <Button
                type="button"
                variant="outline"
                className="border-white/10 bg-white/[0.03] hover:bg-white/[0.06]"
                onClick={() => runQ.refetch()}
              >
                Retry
              </Button>
            }
          />
        </div>
      </HrPageShell>
    );
  }

  const allRows = resultsQ.data?.results ?? [];
  const filtered = allRows
    .filter((r) => scoreToPct(r.final_score) >= minScore)
    .filter((r) => {
      const q = query.trim().toLowerCase();
      if (!q) return true;
      return (
        r.original_filename.toLowerCase().includes(q) ||
        r.resume_id.toLowerCase().includes(q)
      );
    });

  return (
    <HrPageShell>
      <HrHeader
        title="Screening Run"
        subtitle={
          run ? `opening_id: ${run.opening_id}` : runQ.isPending ? "Loading…" : "—"
        }
        chips={
          run
            ? [
                `status: ${run.status}`,
                process.env.NODE_ENV === "development"
                  ? `run_id: ${runId}`
                  : null,
              ].filter(Boolean) as string[]
            : undefined
        }
        actions={
          <>
            <GradientButton
              disabled={!run || run.status !== "DONE" || explain.enqueue.isPending}
              onClick={() => {
                explain.enqueue.mutate(
                  { topN: 20, force: false },
                  {
                    onSuccess: () =>
                      toast("Explanations queued", {
                        description: "Generating for top candidates…",
                      }),
                    onError: (err) =>
                      toast("Could not enqueue explanations", {
                        description:
                          err instanceof Error ? err.message : "Unknown error",
                      }),
                  }
                );
              }}
            >
              <Sparkles className="h-4 w-4" />
              Generate Explanations
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
            {loading || runQ.isPending ? (
              Array.from({ length: 10 }).map((_, i) => (
                <div key={i} className="h-20 rounded-2xl bg-white/[0.03] ring-1 ring-white/10" />
              ))
            ) : run?.status === "DONE" ? (
              resultsQ.isPending ? (
                Array.from({ length: 10 }).map((_, i) => (
                  <div key={i} className="h-20 rounded-2xl bg-white/[0.03] ring-1 ring-white/10" />
                ))
              ) : resultsQ.isError ? (
                <EmptyStateCard
                  title="Could not load results"
                  description={
                    resultsQ.error instanceof Error
                      ? resultsQ.error.message
                      : "Unknown error"
                  }
                  icon={Sparkles}
                  actions={
                    <Button
                      type="button"
                      variant="outline"
                      className="border-white/10 bg-white/[0.03] hover:bg-white/[0.06]"
                      onClick={() => resultsQ.refetch()}
                    >
                      Retry
                    </Button>
                  }
                />
              ) : filtered.length === 0 ? (
                <EmptyStateCard
                  title="No results"
                  description="No candidates matched the current filters."
                  icon={Sparkles}
                />
              ) : (
                filtered.map((r) => (
                  <button
                    key={r.resume_id}
                    type="button"
                    onClick={() => {
                      setSelected(r);
                      setDrawerOpen(true);
                    }}
                    className="w-full rounded-2xl bg-white/[0.02] p-4 text-left ring-1 ring-white/5 hover:bg-white/[0.05] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-300/60"
                    aria-label={`Open result ${r.original_filename}`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="rounded-full bg-white/[0.04] px-2 py-0.5 text-xs text-muted-foreground ring-1 ring-white/10 tabular-nums">
                            #{r.rank}
                          </span>
                          <div className="truncate text-sm font-semibold tracking-tight">
                            {r.original_filename}
                          </div>
                        </div>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {r.best_view_type ? <TagChip>{r.best_view_type}</TagChip> : null}
                          {r.rerank_score != null ? (
                            <TagChip className="bg-white/[0.03]">
                              rerank: {r.rerank_score.toFixed(3)}
                            </TagChip>
                          ) : null}
                        </div>
                        <div className="mt-3 text-xs text-muted-foreground tabular-nums">
                          resume_status: {r.resume_status} • embedding: {r.embedding_status}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <ScorePill score={scoreToPct(r.final_score)} />
                      </div>
                    </div>
                  </button>
                ))
              )
            ) : run?.status === "FAILED" ? (
              <EmptyStateCard
                title="Run failed"
                description={
                  run.error
                    ? String(run.error)
                    : "The backend reported a failure."
                }
                icon={Sparkles}
                actions={
                  <Button
                    type="button"
                    className="rounded-2xl bg-white/[0.06] hover:bg-white/[0.09]"
                    onClick={() => retryMut.mutate()}
                    disabled={retryMut.isPending}
                  >
                    Retry run
                  </Button>
                }
              />
            ) : run?.status === "CANCELLED" ? (
              <EmptyStateCard
                title="Run cancelled"
                description="This run was cancelled. You can start a new one from the Opening."
                icon={Sparkles}
              />
            ) : (
              <EmptyStateCard
                title="Results not ready"
                description={
                  run?.status === "RUNNING" && (run.progress_total ?? 0) === 0
                    ? "This run is starting up (model load/download). First run can take a couple minutes on CPU — keep this page open."
                    : "This run is still processing. Keep this page open — it will update automatically."
                }
                icon={Sparkles}
              />
            )}
          </div>

          {run?.status === "DONE" && resultsQ.data ? (
            <div className="flex items-center justify-between gap-2 pt-2">
              <div className="text-xs text-muted-foreground tabular-nums">
                Showing {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, resultsQ.data.total_results)} of{" "}
                {resultsQ.data.total_results}
              </div>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="outline"
                  className="h-8 rounded-xl border-white/10 bg-white/[0.03] px-3 text-xs hover:bg-white/[0.06]"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                >
                  Prev
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  className="h-8 rounded-xl border-white/10 bg-white/[0.03] px-3 text-xs hover:bg-white/[0.06]"
                  onClick={() => setPage((p) => p + 1)}
                  disabled={page * pageSize >= resultsQ.data.total_results}
                >
                  Next
                </Button>
              </div>
            </div>
          ) : null}
        </div>

        <div className="space-y-6 lg:col-span-4">
          <PanelCard title="Run status" description="Progress and quick actions.">
            <div className="rounded-2xl bg-white/[0.02] p-4 text-sm text-muted-foreground ring-1 ring-white/5">
              {run ? (
                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <RunStatusPill status={run.status} />
                    <div className="text-xs text-muted-foreground tabular-nums">
                      {run.progress_done}/{run.progress_total}
                    </div>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-white/5 ring-1 ring-white/10">
                    <div
                      className="h-full bg-violet-400/40"
                      style={{
                        width:
                          run.progress_total > 0
                            ? `${Math.min(
                                100,
                                Math.round((run.progress_done / run.progress_total) * 100)
                              )}%`
                            : "0%",
                      }}
                    />
                  </div>
                  {run.error ? (
                    <div className="text-xs text-rose-200/80">{run.error}</div>
                  ) : null}
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
                onClick={() => cancelMut.mutate()}
                disabled={
                  !run ||
                  !["QUEUED", "RUNNING"].includes(run.status) ||
                  cancelMut.isPending
                }
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
              {run?.status === "FAILED" ? (
                <Button
                  type="button"
                  className="rounded-2xl bg-white/[0.06] hover:bg-white/[0.09]"
                  onClick={() => retryMut.mutate()}
                  disabled={retryMut.isPending}
                >
                  Retry run
                </Button>
              ) : null}
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

      <RunResultDrawer
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
        runId={runId}
        result={selected}
      />
    </HrPageShell>
  );
}
