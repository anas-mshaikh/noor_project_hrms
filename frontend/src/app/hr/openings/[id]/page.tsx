"use client";

import * as React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { toast } from "sonner";
import { motion } from "framer-motion";
import { ClipboardList, Sparkles, UploadCloud } from "lucide-react";

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
import { DataTable } from "@/features/hr/components/tables/DataTable";
import { KanbanBoard } from "@/features/hr/components/pipeline/KanbanBoard";
import { useMockLoading } from "@/features/hr/hooks/useMockLoading";
import { useReducedMotion } from "@/features/hr/hooks/useReducedMotion";
import { staggerContainer, staggerItem } from "@/features/hr/lib/motion";
import {
  getRunResults,
  HR_PIPELINE_CARDS,
  HR_PIPELINE_STAGES,
  HR_RUNS,
} from "@/features/hr/mock/data";
import type { HrOpening, HrScreeningRun } from "@/features/hr/mock/types";
import { useOpening } from "@/features/hr/hooks/useOpening";
import { useResumes } from "@/features/hr/hooks/useResumes";
import { useBatchPoll } from "@/features/hr/hooks/useBatchPoll";
import type { ResumeOut, UUID } from "@/lib/types";

type PageProps = { params: { id: string } };

function toBatchItem(r: ResumeOut): BatchProgressItem {
  // UI component expects these status literals. Backend uses the same strings.
  const status = (r.status as BatchProgressItem["status"]) ?? "UPLOADED";
  return {
    id: r.id,
    filename: r.original_filename,
    status,
    error: r.error,
  };
}

export default function HROpeningDetailPage(_props: PageProps) {
  const reducedMotion = useReducedMotion();
  const { loading } = useMockLoading(600);

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
            <GradientButton asChild>
              <Link href="/hr/runs">
                <Sparkles className="h-4 w-4" />
                Run Screening
              </Link>
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
              <GradientButton onClick={() => toast("Coming soon", { description: "Create screening run" })}>
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

          <DataTable
            loading={loading}
            columns={[
              {
                key: "title",
                header: "Run",
                className: "col-span-6",
                cell: (r: HrScreeningRun) => (
                  <div className="text-sm font-medium">{r.title}</div>
                ),
              },
              {
                key: "status",
                header: "Status",
                className: "col-span-2",
                cell: (r: HrScreeningRun) => (
                  <div className="text-xs text-muted-foreground">{r.status}</div>
                ),
              },
              {
                key: "progress",
                header: "Progress",
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
            emptyTitle="No runs yet"
            emptyDescription="Create a run to generate ranked candidates."
            className="overflow-hidden"
          />
        </TabsContent>

        <TabsContent value="pipeline" className="mt-4 space-y-6">
          <KanbanBoard stages={HR_PIPELINE_STAGES} cards={HR_PIPELINE_CARDS} />
        </TabsContent>
      </Tabs>
    </HrPageShell>
  );
}
