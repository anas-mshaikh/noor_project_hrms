"use client";

import * as React from "react";
import Link from "next/link";
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
import { DataTable } from "@/features/hr/components/tables/DataTable";
import { KanbanBoard } from "@/features/hr/components/pipeline/KanbanBoard";
import { useMockLoading } from "@/features/hr/hooks/useMockLoading";
import { useReducedMotion } from "@/features/hr/hooks/useReducedMotion";
import { staggerContainer, staggerItem } from "@/features/hr/lib/motion";
import {
  getOpeningById,
  getRunResults,
  HR_PIPELINE_CARDS,
  HR_PIPELINE_STAGES,
  HR_RUNS,
} from "@/features/hr/mock/data";
import type { HrOpening, HrScreeningRun } from "@/features/hr/mock/types";

type PageProps = { params: { id: string } };

function placeholderOpening(id: string): HrOpening {
  return {
    id,
    title: "New opening (mock)",
    department: "Department",
    location: "Location",
    status: "ACTIVE",
    created_at: new Date().toISOString(),
    resumes_count: 0,
    in_pipeline_count: 0,
    last_run_id: null,
  };
}

export default function HROpeningDetailPage({ params }: PageProps) {
  const reducedMotion = useReducedMotion();
  const { loading } = useMockLoading(600);

  const opening = getOpeningById(params.id) ?? placeholderOpening(params.id);
  const runs = HR_RUNS.filter((r) => r.opening_id === opening.id).sort((a, b) => b.created_at.localeCompare(a.created_at));
  const lastRun = opening.last_run_id ? runs.find((r) => r.id === opening.last_run_id) : runs[0];
  const topCandidates = lastRun ? getRunResults(lastRun.id).slice(0, 5) : [];

  const uploadItems: BatchProgressItem[] = React.useMemo(
    () => [
      { id: "u1", filename: "resume_anas.pdf", status: "PARSED" },
      { id: "u2", filename: "resume_ayesha.docx", status: "PARSED" },
      { id: "u3", filename: "resume_bilal.pdf", status: "PARSING" },
      { id: "u4", filename: "resume_unknown.png", status: "FAILED", error: "Unsupported format (mock)" },
    ],
    []
  );

  return (
    <HrPageShell>
      <HrHeader
        title={opening.title}
        subtitle={`${opening.department} • ${opening.location}`}
        chips={[opening.status, `opening_id: ${opening.id}`]}
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
              onClick={() => toast("Coming soon", { description: "Upload resumes" })}
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
              <StatCard label="Resumes" value={opening.resumes_count} icon={ClipboardList} loading={loading} />
            </motion.div>
            <motion.div variants={staggerItem(reducedMotion)}>
              <StatCard label="In Pipeline" value={opening.in_pipeline_count} icon={Sparkles} loading={loading} />
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
          <ResumeDropzone />
          <PanelCard title="Batch progress" description="Parsing and indexing status (mock).">
            <BatchProgress items={uploadItems} loading={loading} />
          </PanelCard>
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
