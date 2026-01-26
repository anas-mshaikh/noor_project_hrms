"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useParams } from "next/navigation";
import { toast } from "sonner";
import { motion } from "framer-motion";
import { ClipboardList, Loader2, Sparkles, UploadCloud } from "lucide-react";
import { useMutation } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { HrPageShell } from "@/features/hr/components/layout/HrPageShell";
import { HrHeader } from "@/features/hr/components/layout/HrHeader";
import { GradientButton } from "@/features/hr/components/cards/GradientButton";
import { StatCard } from "@/features/hr/components/cards/StatCard";
import { PanelCard } from "@/features/hr/components/cards/PanelCard";
import { EmptyStateCard } from "@/features/hr/components/cards/EmptyStateCard";
import { ResumeDropzone } from "@/features/hr/components/openings/ResumeDropzone";
import { BatchProgress, type BatchProgressItem } from "@/features/hr/components/openings/BatchProgress";
import { ParsedResumeSheet } from "@/features/hr/components/openings/ParsedResumeSheet";
import { KanbanBoard } from "@/features/hr/components/pipeline/KanbanBoard";
import { ApplicationDrawer } from "@/features/hr/components/pipeline/ApplicationDrawer";
import { RunStatusPill } from "@/features/hr/components/runs/RunStatusPill";
import { useMockLoading } from "@/features/hr/hooks/useMockLoading";
import { useReducedMotion } from "@/features/hr/hooks/useReducedMotion";
import { useOpeningIndexStatus } from "@/features/hr/hooks/useOpeningIndexStatus";
import { usePipelineStages } from "@/features/hr/hooks/usePipelineStages";
import { useApplications } from "@/features/hr/hooks/useApplications";
import { staggerContainer, staggerItem } from "@/features/hr/lib/motion";
import {
  getRunResults,
  HR_RUNS,
} from "@/features/hr/mock/data";
import type { HrOpening } from "@/features/hr/mock/types";
import { useOpening } from "@/features/hr/hooks/useOpening";
import { useResumes } from "@/features/hr/hooks/useResumes";
import { useBatchPoll } from "@/features/hr/hooks/useBatchPoll";
import type { PipelineCardUi, PipelineStageUi } from "@/features/hr/components/pipeline/types";
import type { ApplicationOut, ResumeOut, UUID } from "@/lib/types";
import {
  createScreeningRun,
  enqueueOpeningEmbeddings,
  enqueueRunExplanations,
} from "@/features/hr/api/hr";
import { useScreeningRun } from "@/features/hr/hooks/useScreeningRun";

type PageProps = { params: { id: string } };

function toBatchItem(r: ResumeOut): BatchProgressItem {
  // UI component expects these status literals. Backend uses the same strings.
  const status = (r.status as BatchProgressItem["status"]) ?? "UPLOADED";
  return {
    id: r.id,
    filename: r.original_filename,
    status,
    embedding_status: r.embedding_status,
    error: r.error,
  };
}

export default function HROpeningDetailPage(_props: PageProps) {
  const reducedMotion = useReducedMotion();
  const { loading } = useMockLoading(600);
  const router = useRouter();

  // In production builds, using `useParams()` is the most reliable way to read dynamic
  // route segments from a client component.
  const routeParams = useParams() as { id?: string };
  const openingId = (routeParams.id ?? null) as UUID | null;
  const openingQ = useOpening(openingId);

  const opening: HrOpening | null = openingQ.data
    ? {
        id: openingQ.data.id,
        title: openingQ.data.title,
        status: (openingQ.data.status as HrOpening["status"]) ?? "ACTIVE",
        created_at: openingQ.data.created_at,
        department: "—",
        location: "—",
        resumes_count: 0,
        in_pipeline_count: 0,
        last_run_id: null,
      }
    : null;
  const isLoadingOpening = openingQ.isPending;

  const createRun = useMutation({
    mutationFn: () => {
      // `openingId` comes from the route; during the first render it can be null.
      // This mutation should never be invoked without an id, but we guard anyway
      // so the callback is type-safe and fails with a clear message if misused.
      if (!openingId) throw new Error("Missing opening id");
      return createScreeningRun(openingId, {});
    },
    onSuccess: (run) => {
      try {
        localStorage.setItem(`hr:lastRun:${openingId}`, run.id);
      } catch {
        // ignore (private browsing / storage disabled)
      }

      toast("Screening run started", {
        description: `run_id: ${run.id}`,
      });
      router.push(`/hr/runs/${run.id}`);
    },
    onError: (err) => {
      toast("Could not start run", {
        description: err instanceof Error ? err.message : "Unknown error",
      });
    },
  });

  const [lastRunId, setLastRunId] = React.useState<UUID | null>(null);
  React.useEffect(() => {
    try {
      const v = localStorage.getItem(`hr:lastRun:${openingId}`);
      setLastRunId((v as UUID) || null);
    } catch {
      setLastRunId(null);
    }
  }, [openingId]);

  const lastRunQ = useScreeningRun(lastRunId);
  const enqueueExplain = useMutation({
    mutationFn: () =>
      enqueueRunExplanations(lastRunId as UUID, { topN: 20, force: false }),
    onSuccess: () =>
      toast("Explanations queued", {
        description: "Generating for top candidates…",
      }),
    onError: (err) =>
      toast("Could not enqueue explanations", {
        description: err instanceof Error ? err.message : "Unknown error",
      }),
  });

  // While route params are not ready, keep the UI mounted but don't start fetching.
  if (!openingId) {
    return (
      <HrPageShell>
        <EmptyStateCard
          title="Loading opening…"
          description="Preparing route context."
          icon={Sparkles}
        />
      </HrPageShell>
    );
  }

  if (!opening && !isLoadingOpening) {
    return (
      <HrPageShell>
        <EmptyStateCard
          title="Opening not found"
          description="The requested opening was not returned from the backend."
          icon={Sparkles}
          actions={
            <GradientButton asChild>
              <Link href="/hr/openings">Back to openings</Link>
            </GradientButton>
          }
        />
      </HrPageShell>
    );
  }

  // While loading, render a non-mock placeholder so the page can mount without null checks everywhere.
  const openingUi: HrOpening =
    opening ??
    ({
      id: openingId,
      title: "Loading opening…",
      status: "ACTIVE",
      created_at: new Date().toISOString(),
      department: "—",
      location: "—",
      resumes_count: 0,
      in_pipeline_count: 0,
      last_run_id: null,
    } satisfies HrOpening);

  const runs = opening
    ? HR_RUNS.filter((r) => r.opening_id === openingUi.id).sort((a, b) =>
        b.created_at.localeCompare(a.created_at)
      )
    : [];
  const lastRun = openingUi.last_run_id
    ? runs.find((r) => r.id === openingUi.last_run_id)
    : runs[0];
  const topCandidates = lastRun ? getRunResults(lastRun.id).slice(0, 5) : [];

  const { list: resumesQ, upload: uploadMutation } = useResumes(openingId);
  const indexQ = useOpeningIndexStatus(openingId);

  // ATS / Pipeline (Phase 5): stages + applications for this opening.
  const stagesQ = usePipelineStages(openingId);
  const appsQ = useApplications(openingId);
  const [selectedAppId, setSelectedAppId] = React.useState<UUID | null>(null);
  const [appDrawerOpen, setAppDrawerOpen] = React.useState(false);
  const selectedApplication = React.useMemo(() => {
    if (!selectedAppId) return null;
    return (appsQ.list.data ?? []).find((a) => a.id === selectedAppId) ?? null;
  }, [appsQ.list.data, selectedAppId]);

  const pipelineStagesUi: PipelineStageUi[] = React.useMemo(() => {
    const stages = (stagesQ.data ?? []).map((s) => ({
      id: s.id,
      name: s.name,
      sort_order: s.sort_order,
      is_terminal: s.is_terminal,
    }));
    const hasUnassigned = (appsQ.list.data ?? []).some((a) => !a.stage_id);
    return hasUnassigned
      ? [
          { id: "__unassigned__", name: "Unassigned", sort_order: -1, is_terminal: false },
          ...stages,
        ]
      : stages;
  }, [stagesQ.data, appsQ.list.data]);

  const pipelineCardsUi: PipelineCardUi[] = React.useMemo(() => {
    return (appsQ.list.data ?? []).map((a) => ({
      id: a.id,
      stageId: a.stage_id ?? "__unassigned__",
      title: a.resume.original_filename,
      tags: [
        a.resume.status,
        a.status === "ACTIVE" ? "Active" : a.status,
        a.source_run_id ? "From run" : "Manual",
      ].filter(Boolean),
      application: a,
    }));
  }, [appsQ.list.data]);

  const enqueueEmbed = useMutation({
    mutationFn: () => enqueueOpeningEmbeddings(openingId as UUID, { force: false }),
    onSuccess: (resp) => {
      toast("Embedding queued", {
        description: `${resp.enqueued} enqueued, ${resp.skipped} skipped`,
      });
      resumesQ.refetch();
      indexQ.refetch();
    },
    onError: (err) => {
      toast("Could not enqueue embeddings", {
        description: err instanceof Error ? err.message : "Unknown error",
      });
    },
  });
  const [activeBatchId, setActiveBatchId] = React.useState<UUID | null>(null);
  const batchQ = useBatchPoll(
    activeBatchId ? { openingId, batchId: activeBatchId } : null
  );

  const [parsedOpen, setParsedOpen] = React.useState(false);
  const [parsedResumeId, setParsedResumeId] = React.useState<UUID | null>(null);
  const [parsedTitle, setParsedTitle] = React.useState<string | undefined>(undefined);

  const uploadItems: BatchProgressItem[] = React.useMemo(() => {
    return (resumesQ.data ?? []).map(toBatchItem);
  }, [resumesQ.data]);

  React.useEffect(() => {
    if (!batchQ.done) return;
    toast("Parsing completed", {
      description: `${batchQ.data?.parsed_count ?? 0} parsed, ${batchQ.data?.failed_count ?? 0} failed`,
    });
    // Refresh resume list once batch is done.
    resumesQ.refetch();
  }, [batchQ.done]); // eslint-disable-line react-hooks/exhaustive-deps

  React.useEffect(() => {
    if (!openingQ.data) return;
    try {
      localStorage.setItem(`hr:lastOpening:${openingQ.data.store_id}`, openingQ.data.id);
    } catch {
      // ignore
    }
  }, [openingQ.data]);

  return (
    <HrPageShell>
      <HrHeader
        title={openingUi.title}
        subtitle={`${openingUi.department} • ${openingUi.location}`}
        chips={[
          openingUi.status,
          process.env.NEXT_PUBLIC_SHOW_DEBUG_IDS === "true" ||
          process.env.NODE_ENV === "development"
            ? `opening_id: ${openingUi.id}`
            : null,
        ].filter(Boolean) as string[]}
        actions={
          <>
            <GradientButton
              type="button"
              disabled={createRun.isPending || openingQ.isPending}
              onClick={() => createRun.mutate()}
            >
              {createRun.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Sparkles className="h-4 w-4" />
              )}
              Run Screening
            </GradientButton>
            <Button
              type="button"
              variant="outline"
              className="border-white/10 bg-white/[0.03] hover:bg-white/[0.06]"
              onClick={() =>
                toast("Tip", {
                  description: "Use the Resumes tab to upload files.",
                })
              }
            >
              <UploadCloud className="h-4 w-4" />
              Upload Resumes
            </Button>
          </>
        }
      />

      <Tabs defaultValue="overview">
        <TabsList className="w-full justify-start gap-2 rounded-2xl bg-white/[0.03] p-1 ring-1 ring-white/10">
          <TabsTrigger value="overview" className="rounded-xl">
            Overview
          </TabsTrigger>
          <TabsTrigger value="resumes" className="rounded-xl">
            Resumes
          </TabsTrigger>
          <TabsTrigger value="screening" className="rounded-xl">
            Screening
          </TabsTrigger>
          <TabsTrigger value="pipeline" className="rounded-xl">
            Pipeline
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-4 space-y-6">
          <motion.div
            variants={staggerContainer(reducedMotion)}
            initial="hidden"
            animate="show"
            className="grid grid-cols-1 gap-4 md:grid-cols-3"
          >
            <motion.div variants={staggerItem(reducedMotion)}>
              <StatCard label="Resumes" value={openingUi.resumes_count} icon={ClipboardList} loading={loading} />
            </motion.div>
            <motion.div variants={staggerItem(reducedMotion)}>
              <StatCard label="In Pipeline" value={openingUi.in_pipeline_count} icon={Sparkles} loading={loading} />
            </motion.div>
            <motion.div variants={staggerItem(reducedMotion)}>
              <StatCard label="Last Run" value={lastRun?.status ?? "—"} icon={Sparkles} loading={loading} />
            </motion.div>
          </motion.div>

          <PanelCard title="Top candidates" description="From the most recent screening run (mock).">
            {topCandidates.length === 0 && !loading ? (
              <EmptyStateCard
                title="No run results yet"
                description="Run screening to generate ranked candidates."
                icon={Sparkles}
                actions={
                  <GradientButton asChild>
                    <Link href="/hr/runs">Run Screening</Link>
                  </GradientButton>
                }
              />
            ) : (
              <div className="space-y-3">
                {loading
                  ? Array.from({ length: 4 }).map((_, i) => (
                      <div key={i} className="h-14 rounded-2xl bg-white/[0.02] ring-1 ring-white/5" />
                    ))
                  : topCandidates.map((r) => (
                      <Link
                        key={r.candidate.id}
                        href={`/hr/runs/${r.run_id}`}
                        className="flex items-center justify-between gap-3 rounded-2xl bg-white/[0.02] p-3 ring-1 ring-white/5 hover:bg-white/[0.05]"
                      >
                        <div className="min-w-0">
                          <div className="truncate text-sm font-medium">{r.candidate.name}</div>
                          <div className="truncate text-xs text-muted-foreground">{r.candidate.current_title}</div>
                        </div>
                        <div className="text-xs text-muted-foreground tabular-nums">#{r.rank}</div>
                      </Link>
                    ))}
              </div>
            )}
          </PanelCard>
        </TabsContent>

        <TabsContent value="resumes" className="mt-4 space-y-6">
          {openingQ.isError ? (
            <EmptyStateCard
              title="Could not load opening"
              description={openingQ.error instanceof Error ? openingQ.error.message : "Unknown error"}
              icon={UploadCloud}
              actions={
                <Button
                  type="button"
                  variant="outline"
                  className="border-white/10 bg-white/[0.03] hover:bg-white/[0.06]"
                  onClick={() => openingQ.refetch()}
                >
                  Retry
                </Button>
              }
            />
          ) : (
            <>
              <ResumeDropzone
                uploading={uploadMutation.isPending}
                disabled={openingQ.isPending}
                helperText="Select multiple files. We'll parse them in the background and update statuses live."
                onFilesSelected={(files) => {
                  toast("Upload started", { description: `${files.length} file(s)` });
                  uploadMutation.mutate(
                    { files },
                    {
                      onSuccess: (resp) => {
                        setActiveBatchId(resp.batch_id);
                        batchQ.resetDone();
                        resumesQ.refetch();
                        toast("Uploaded", {
                          description: `Batch ${resp.batch_id} • ${resp.resume_ids.length} resume(s) queued`,
                        });
                      },
                      onError: (err) => {
                        toast("Upload failed", {
                          description: err instanceof Error ? err.message : "Unknown error",
                        });
                      },
                    }
                  );
                }}
              />

              <PanelCard
                title="Embeddings"
                description="Generate embeddings used by screening runs."
              >
                <div className="rounded-2xl bg-white/[0.02] p-4 text-sm text-muted-foreground ring-1 ring-white/5">
                  {indexQ.isPending ? (
                    <div className="space-y-2">
                      <div className="h-3 w-56 rounded bg-white/10" />
                      <div className="h-3 w-44 rounded bg-white/10" />
                    </div>
                  ) : indexQ.isError ? (
                    <div>Could not load embedding status.</div>
                  ) : indexQ.data ? (
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        Parsed{" "}
                        <span className="text-foreground/90 tabular-nums">
                          {indexQ.data.parsed_resumes}
                        </span>{" "}
                        • Embedded{" "}
                        <span className="text-foreground/90 tabular-nums">
                          {indexQ.data.embedded_resumes}
                        </span>{" "}
                        • Failed{" "}
                        <span className="text-foreground/90 tabular-nums">
                          {indexQ.data.embedding_failed}
                        </span>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Button
                          type="button"
                          variant="outline"
                          className="border-white/10 bg-white/[0.03] hover:bg-white/[0.06]"
                          onClick={() => enqueueEmbed.mutate()}
                          disabled={
                            enqueueEmbed.isPending ||
                            (indexQ.data.parsed_resumes ?? 0) === 0
                          }
                        >
                          {enqueueEmbed.isPending ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            "Embed resumes"
                          )}
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          className="border-white/10 bg-white/[0.03] hover:bg-white/[0.06]"
                          onClick={() => indexQ.refetch()}
                        >
                          Refresh
                        </Button>
                      </div>
                    </div>
                  ) : null}
                </div>
              </PanelCard>

              <PanelCard title="Batch progress" description="Resume parsing status (live).">
                {activeBatchId && batchQ.data ? (
                  <div className="mb-3 rounded-2xl bg-white/[0.02] p-4 text-sm text-muted-foreground ring-1 ring-white/5">
                    Total: <span className="text-foreground/90 tabular-nums">{batchQ.data.total_count}</span> • Parsed:{" "}
                    <span className="text-foreground/90 tabular-nums">{batchQ.data.parsed_count}</span> • Parsing:{" "}
                    <span className="text-foreground/90 tabular-nums">{batchQ.data.parsing_count}</span> • Failed:{" "}
                    <span className="text-foreground/90 tabular-nums">{batchQ.data.failed_count}</span>
                  </div>
                ) : null}

                <BatchProgress items={uploadItems} loading={resumesQ.isPending || loading} />

                {!resumesQ.isPending && uploadItems.length > 0 ? (
                  <div className="mt-3 space-y-2">
                    {uploadItems
                      .filter((it) => it.status === "PARSED")
                      .slice(0, 6)
                      .map((it) => (
                        <div key={it.id} className="flex items-center justify-between gap-3 rounded-2xl bg-white/[0.02] p-3 ring-1 ring-white/5">
                          <div className="min-w-0">
                            <div className="truncate text-sm font-medium">{it.filename}</div>
                            <div className="text-xs text-muted-foreground">Parsed</div>
                          </div>
                          <Button
                            type="button"
                            variant="outline"
                            className="h-8 rounded-xl border-white/10 bg-white/[0.03] px-3 text-xs hover:bg-white/[0.06]"
                            onClick={() => {
                              setParsedResumeId(it.id as UUID);
                              setParsedTitle(it.filename);
                              setParsedOpen(true);
                            }}
                          >
                            View Parsed
                          </Button>
                        </div>
                      ))}
                  </div>
                ) : null}
              </PanelCard>

              <ParsedResumeSheet
                open={parsedOpen}
                onOpenChange={setParsedOpen}
                resumeId={parsedResumeId}
                title={parsedTitle}
              />
            </>
          )}
        </TabsContent>

        <TabsContent value="screening" className="mt-4 space-y-6">
          <PanelCard title="Run configuration" description="Tune top-K and reranking (mock).">
            <div className="rounded-2xl bg-white/[0.02] p-4 text-sm text-muted-foreground ring-1 ring-white/5">
              View types: <span className="text-foreground/90">skills, experience, full</span> • Pool size:{" "}
              <span className="text-foreground/90">400</span> • Top N: <span className="text-foreground/90">200</span>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <GradientButton
                type="button"
                disabled={createRun.isPending || openingQ.isPending}
                onClick={() => createRun.mutate()}
              >
                {createRun.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Sparkles className="h-4 w-4" />
                )}
                Create Run
              </GradientButton>
              <Button
                type="button"
                variant="outline"
                className="border-white/10 bg-white/[0.03] hover:bg-white/[0.06]"
                onClick={() => toast("Coming soon", { description: "Edit config" })}
              >
                Edit config
              </Button>
            </div>
          </PanelCard>

          <PanelCard title="Latest run" description="Most recent run for this opening.">
            {!lastRunId ? (
              <EmptyStateCard
                title="No runs yet"
                description="Create a run to generate ranked candidates."
                icon={Sparkles}
                actions={
                  <GradientButton
                    type="button"
                    disabled={createRun.isPending || openingQ.isPending}
                    onClick={() => createRun.mutate()}
                  >
                    {createRun.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Sparkles className="h-4 w-4" />
                    )}
                    Create Run
                  </GradientButton>
                }
              />
            ) : lastRunQ.isPending ? (
              <div className="rounded-2xl bg-white/[0.02] p-4 ring-1 ring-white/5">
                <div className="h-4 w-40 rounded bg-white/10" />
                <div className="mt-3 h-3 w-64 rounded bg-white/10" />
              </div>
            ) : lastRunQ.isError ? (
              <EmptyStateCard
                title="Could not load run"
                description={
                  lastRunQ.error instanceof Error
                    ? lastRunQ.error.message
                    : "Unknown error"
                }
                icon={Sparkles}
                actions={
                  <Button
                    type="button"
                    variant="outline"
                    className="border-white/10 bg-white/[0.03] hover:bg-white/[0.06]"
                    onClick={() => lastRunQ.refetch()}
                  >
                    Retry
                  </Button>
                }
              />
            ) : lastRunQ.data ? (
              <div className="rounded-2xl bg-white/[0.02] p-4 ring-1 ring-white/5">
                <div className="flex items-center justify-between gap-2">
                  <RunStatusPill status={lastRunQ.data.status} />
                  <div className="text-xs text-muted-foreground tabular-nums">
                    {lastRunQ.data.progress_done}/{lastRunQ.data.progress_total}
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <GradientButton asChild>
                    <Link href={`/hr/runs/${lastRunId}`}>Open run</Link>
                  </GradientButton>
                  <Button
                    type="button"
                    variant="outline"
                    className="border-white/10 bg-white/[0.03] hover:bg-white/[0.06]"
                    onClick={() => {
                      if (lastRunQ.data?.status !== "DONE") {
                        toast("Run not done yet");
                        return;
                      }
                      enqueueExplain.mutate();
                    }}
                    disabled={
                      enqueueExplain.isPending || lastRunQ.data?.status !== "DONE"
                    }
                  >
                    Generate explanations
                  </Button>
                </div>
              </div>
            ) : null}
          </PanelCard>
        </TabsContent>

        <TabsContent value="pipeline" className="mt-4 space-y-6">
          {stagesQ.isError ? (
            <EmptyStateCard
              title="Could not load pipeline"
              description={
                stagesQ.error instanceof Error
                  ? stagesQ.error.message
                  : "Unknown error"
              }
              icon={Sparkles}
              actions={
                <Button
                  type="button"
                  variant="outline"
                  className="border-white/10 bg-white/[0.03] hover:bg-white/[0.06]"
                  onClick={() => {
                    stagesQ.refetch();
                    appsQ.list.refetch();
                  }}
                >
                  Retry
                </Button>
              }
            />
          ) : (stagesQ.data?.length ?? 0) === 0 && !stagesQ.isPending ? (
            <EmptyStateCard
              title="No pipeline stages found"
              description="This opening has no stages yet. Try refreshing or recreate the opening defaults."
              icon={Sparkles}
              actions={
                <Button
                  type="button"
                  variant="outline"
                  className="border-white/10 bg-white/[0.03] hover:bg-white/[0.06]"
                  onClick={() => stagesQ.refetch()}
                >
                  Retry
                </Button>
              }
            />
          ) : (
            <>
              <KanbanBoard
                stages={pipelineStagesUi}
                cards={pipelineCardsUi}
                onMove={(cardId, stageId) => {
                  appsQ.moveStage.mutate(
                    { applicationId: cardId as UUID, stageId: stageId as UUID },
                    {
                      onSuccess: () => toast("Moved"),
                      onError: (err) =>
                        toast("Could not move", {
                          description:
                            err instanceof Error ? err.message : "Unknown error",
                        }),
                    }
                  );
                }}
                onOpenCandidate={(cardId) => {
                  setSelectedAppId(cardId as UUID);
                  setAppDrawerOpen(true);
                }}
              />

              <ApplicationDrawer
                open={appDrawerOpen}
                onOpenChange={setAppDrawerOpen}
                application={selectedApplication as ApplicationOut | null}
                stages={stagesQ.data ?? []}
                onMoveStage={(applicationId, stageId) => {
                  appsQ.moveStage.mutate(
                    { applicationId, stageId },
                    {
                      onSuccess: () => toast("Moved"),
                      onError: (err) =>
                        toast("Could not move", {
                          description:
                            err instanceof Error ? err.message : "Unknown error",
                        }),
                    }
                  );
                }}
                onReject={(applicationId) => {
                  appsQ.reject.mutate(applicationId, {
                    onSuccess: () => toast("Rejected"),
                    onError: (err) =>
                      toast("Could not reject", {
                        description:
                          err instanceof Error ? err.message : "Unknown error",
                      }),
                  });
                }}
                onHire={(applicationId) => {
                  appsQ.hire.mutate(applicationId, {
                    onSuccess: () => toast("Marked as hired"),
                    onError: (err) =>
                      toast("Could not hire", {
                        description:
                          err instanceof Error ? err.message : "Unknown error",
                      }),
                  });
                }}
                busy={
                  appsQ.moveStage.isPending ||
                  appsQ.reject.isPending ||
                  appsQ.hire.isPending
                }
              />
            </>
          )}
        </TabsContent>
      </Tabs>
    </HrPageShell>
  );
}
