"use client";

import * as React from "react";
import Link from "next/link";
import { toast } from "sonner";
import { ChevronDown, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { HrPageShell } from "@/features/hr/components/layout/HrPageShell";
import { HrHeader } from "@/features/hr/components/layout/HrHeader";
import { GradientButton } from "@/features/hr/components/cards/GradientButton";
import { PanelCard } from "@/features/hr/components/cards/PanelCard";
import { EmptyStateCard } from "@/features/hr/components/cards/EmptyStateCard";
import { KanbanBoard } from "@/features/hr/components/pipeline/KanbanBoard";
import { ApplicationDrawer } from "@/features/hr/components/pipeline/ApplicationDrawer";
import type { PipelineCardUi, PipelineStageUi } from "@/features/hr/components/pipeline/types";
import { useSelection } from "@/lib/selection";
import { useOpenings } from "@/features/hr/hooks/useOpenings";
import { usePipelineStages } from "@/features/hr/hooks/usePipelineStages";
import { useApplications } from "@/features/hr/hooks/useApplications";
import type { UUID } from "@/lib/types";

function safeLocalStorageGet(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeLocalStorageSet(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    // ignore
  }
}

export default function HRPipelinePage() {
  const storeId = useSelection((s) => s.storeId) as UUID | undefined;
  const openingsQ = useOpenings(storeId ?? null);

  // We avoid `useSearchParams()` here because Next may attempt to pre-render this
  // page during build, and `useSearchParams()` requires a Suspense boundary.
  // This page is client-only anyway, so reading from `window.location.search`
  // after mount is sufficient.
  const [openingFromUrl, setOpeningFromUrl] = React.useState<UUID | null>(null);
  const [openingId, setOpeningId] = React.useState<UUID | null>(null);

  React.useEffect(() => {
    try {
      const qs = new URLSearchParams(window.location.search);
      setOpeningFromUrl((qs.get("opening") ?? null) as UUID | null);
    } catch {
      setOpeningFromUrl(null);
    }
  }, []);

  // When the URL param is present, treat it as the source of truth.
  React.useEffect(() => {
    if (openingFromUrl) setOpeningId(openingFromUrl);
  }, [openingFromUrl]);

  // Select a default opening when we have a store + opening list.
  React.useEffect(() => {
    if (!storeId) {
      setOpeningId(null);
      return;
    }
    if (openingFromUrl) return;
    if (openingId) return;

    const list = openingsQ.list.data ?? [];
    if (list.length === 0) return;

    const saved = safeLocalStorageGet(`hr:lastOpening:${storeId}`);
    const valid = saved && list.some((o) => o.id === saved);
    setOpeningId((valid ? saved : list[0].id) as UUID);
  }, [storeId, openingsQ.list.data, openingFromUrl, openingId]);

  React.useEffect(() => {
    if (!storeId || !openingId) return;
    safeLocalStorageSet(`hr:lastOpening:${storeId}`, openingId);
  }, [storeId, openingId]);

  const stagesQ = usePipelineStages(openingId);
  const appsQ = useApplications(openingId);

  const [selectedAppId, setSelectedAppId] = React.useState<UUID | null>(null);
  const [drawerOpen, setDrawerOpen] = React.useState(false);

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

  function onMove(cardId: string, stageId: string) {
    appsQ.moveStage.mutate(
      { applicationId: cardId as UUID, stageId: stageId as UUID },
      {
        onSuccess: () => toast("Moved"),
        onError: (err) =>
          toast("Could not move", {
            description: err instanceof Error ? err.message : "Unknown error",
          }),
      }
    );
  }

  function onOpenCandidate(cardId: string) {
    setSelectedAppId(cardId as UUID);
    setDrawerOpen(true);
  }

  return (
    <HrPageShell>
      <HrHeader
        title="Pipeline"
        subtitle="ATS-style board for candidate progression."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  type="button"
                  variant="outline"
                  className="border-white/10 bg-white/[0.03] hover:bg-white/[0.06]"
                  disabled={openingsQ.list.isPending || (openingsQ.list.data?.length ?? 0) === 0}
                  aria-label="Select opening"
                >
                  {openingId
                    ? openingsQ.list.data?.find((o) => o.id === openingId)?.title ?? "Select opening"
                    : "Select opening"}
                  <ChevronDown className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-72">
                {(openingsQ.list.data ?? []).map((o) => (
                  <DropdownMenuItem
                    key={o.id}
                    onClick={() => setOpeningId(o.id)}
                    className="flex flex-col items-start gap-0.5"
                  >
                    <div className="text-sm font-medium">{o.title}</div>
                    <div className="text-xs text-muted-foreground tabular-nums">
                      {o.status}
                    </div>
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>

            <GradientButton asChild>
              <Link href="/hr/openings/new">
                <Sparkles className="h-4 w-4" />
                Create opening
              </Link>
            </GradientButton>
          </div>
        }
      />

      {!storeId ? (
        <div className="mt-6">
          <EmptyStateCard
            title="Select a store"
            description="Choose a store to manage openings and pipeline."
            icon={Sparkles}
          />
        </div>
      ) : openingsQ.list.isPending ? (
        <div className="mt-6">
          <EmptyStateCard title="Loading openings…" description="Fetching your openings." icon={Sparkles} />
        </div>
      ) : (openingsQ.list.data?.length ?? 0) === 0 ? (
        <div className="mt-6">
          <EmptyStateCard
            title="No openings yet"
            description="Create an opening first, then upload resumes and run screening."
            icon={Sparkles}
            actions={
              <GradientButton asChild>
                <Link href="/hr/openings/new">Create opening</Link>
              </GradientButton>
            }
          />
        </div>
      ) : !openingId ? (
        <div className="mt-6">
          <EmptyStateCard
            title="Select an opening"
            description="Pick an opening to view its pipeline."
            icon={Sparkles}
          />
        </div>
      ) : stagesQ.isError ? (
        <div className="mt-6">
          <EmptyStateCard
            title="Could not load pipeline"
            description={stagesQ.error instanceof Error ? stagesQ.error.message : "Unknown error"}
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
        </div>
      ) : (stagesQ.data?.length ?? 0) === 0 && !stagesQ.isPending ? (
        <div className="mt-6">
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
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
            <div className="lg:col-span-9">
              <KanbanBoard
                stages={pipelineStagesUi}
                cards={pipelineCardsUi}
                onMove={onMove}
                onOpenCandidate={onOpenCandidate}
              />
            </div>

            <div className="space-y-6 lg:col-span-3">
              <PanelCard title="Stage conversion" description="Mock funnel stats.">
                <div className="space-y-3 text-sm text-muted-foreground">
                  <div className="rounded-2xl bg-white/[0.02] p-3 ring-1 ring-white/5">
                    Screened → Interview:{" "}
                    <span className="text-foreground/90 tabular-nums">38%</span>
                  </div>
                  <div className="rounded-2xl bg-white/[0.02] p-3 ring-1 ring-white/5">
                    Interview → Offer:{" "}
                    <span className="text-foreground/90 tabular-nums">22%</span>
                  </div>
                  <div className="rounded-2xl bg-white/[0.02] p-3 ring-1 ring-white/5">
                    Offer → Hired:{" "}
                    <span className="text-foreground/90 tabular-nums">12%</span>
                  </div>
                </div>
              </PanelCard>
            </div>
          </div>

          <ApplicationDrawer
            open={drawerOpen}
            onOpenChange={setDrawerOpen}
            application={selectedApplication}
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
    </HrPageShell>
  );
}
