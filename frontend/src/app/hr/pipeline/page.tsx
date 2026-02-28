"use client";

import * as React from "react";
import Link from "next/link";
import { toast } from "sonner";
import { ChevronDown, Sparkles } from "lucide-react";
import { useTranslation } from "@/lib/i18n";
import { toastApiError } from "@/lib/toastApiError";

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
import { StorePicker } from "@/components/StorePicker";
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
  const { t } = useTranslation();
  const branchId = useSelection((s) => s.branchId) as UUID | undefined;
  const openingsQ = useOpenings(branchId ?? null);

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
    if (!branchId) {
      setOpeningId(null);
      return;
    }
    if (openingFromUrl) return;
    if (openingId) return;

    const list = openingsQ.list.data ?? [];
    if (list.length === 0) return;

    const saved = safeLocalStorageGet(`hr:lastOpening:${branchId}`);
    const valid = saved && list.some((o) => o.id === saved);
    setOpeningId((valid ? saved : list[0].id) as UUID);
  }, [branchId, openingsQ.list.data, openingFromUrl, openingId]);

  React.useEffect(() => {
    if (!branchId || !openingId) return;
    safeLocalStorageSet(`hr:lastOpening:${branchId}`, openingId);
  }, [branchId, openingId]);

  const stagesQ = usePipelineStages(branchId ?? null, openingId);
  const appsQ = useApplications(branchId ?? null, openingId);

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
          {
            id: "__unassigned__",
            name: t("hr.common.unassigned", { defaultValue: "Unassigned" }),
            sort_order: -1,
            is_terminal: false,
          },
          ...stages,
        ]
      : stages;
  }, [stagesQ.data, appsQ.list.data, t]);

  const pipelineCardsUi: PipelineCardUi[] = React.useMemo(() => {
    return (appsQ.list.data ?? []).map((a) => ({
      id: a.id,
      stageId: a.stage_id ?? "__unassigned__",
      title: a.resume.original_filename,
      tags: [
        a.resume.status,
        a.status === "ACTIVE"
          ? t("hr.pipeline_page.tag_active", { defaultValue: "Active" })
          : a.status,
        a.source_run_id
          ? t("hr.pipeline_page.tag_from_run", { defaultValue: "From run" })
          : t("hr.pipeline_page.tag_manual", { defaultValue: "Manual" }),
      ].filter(Boolean),
      application: a,
    }));
  }, [appsQ.list.data, t]);

  function onMove(cardId: string, stageId: string) {
    appsQ.moveStage.mutate(
      { applicationId: cardId as UUID, stageId: stageId as UUID },
      {
        onSuccess: () =>
          toast(t("hr.pipeline_page.moved_toast", { defaultValue: "Moved" })),
        onError: (err) => toastApiError(err, t),
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
        title={t("hr.pipeline_page.title", { defaultValue: "Pipeline" })}
        subtitle={t("hr.pipeline_page.subtitle", {
          defaultValue: "ATS-style board for candidate progression.",
        })}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  type="button"
                  variant="outline"
                  className="border-white/10 bg-white/[0.03] hover:bg-white/[0.06]"
                  disabled={openingsQ.list.isPending || (openingsQ.list.data?.length ?? 0) === 0}
                  aria-label={t("hr.pipeline_page.select_opening", { defaultValue: "Select opening" })}
                >
                  {openingId
                    ? openingsQ.list.data?.find((o) => o.id === openingId)?.title ??
                      t("hr.pipeline_page.select_opening", { defaultValue: "Select opening" })
                    : t("hr.pipeline_page.select_opening", { defaultValue: "Select opening" })}
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
                {t("hr.openings_page.create_opening", { defaultValue: "Create opening" })}
              </Link>
            </GradientButton>
          </div>
        }
      />

      {!branchId ? (
        <div className="mt-6">
          <EmptyStateCard
            title={t("hr.common.select_branch", { defaultValue: "Select a branch" })}
            description={t("hr.pipeline_page.branch_description", {
              defaultValue: "Choose a branch to manage openings and pipeline.",
            })}
            icon={Sparkles}
            actions={<div className="w-full max-w-xl"><StorePicker /></div>}
          />
        </div>
      ) : openingsQ.list.isPending ? (
        <div className="mt-6">
          <EmptyStateCard
            title={t("hr.pipeline_page.loading_openings", { defaultValue: "Loading openings…" })}
            description={t("hr.pipeline_page.fetching_openings", { defaultValue: "Fetching your openings." })}
            icon={Sparkles}
          />
        </div>
      ) : (openingsQ.list.data?.length ?? 0) === 0 ? (
        <div className="mt-6">
          <EmptyStateCard
            title={t("hr.overview_page.no_openings_title", { defaultValue: "No openings yet" })}
            description={t("hr.pipeline_page.no_openings_description", {
              defaultValue:
                "Create an opening first, then upload resumes and run screening.",
            })}
            icon={Sparkles}
            actions={
              <GradientButton asChild>
                <Link href="/hr/openings/new">
                  {t("hr.openings_page.create_opening", { defaultValue: "Create opening" })}
                </Link>
              </GradientButton>
            }
          />
        </div>
      ) : !openingId ? (
        <div className="mt-6">
          <EmptyStateCard
            title={t("hr.pipeline_page.select_opening_title", { defaultValue: "Select an opening" })}
            description={t("hr.pipeline_page.select_opening_description", {
              defaultValue: "Pick an opening to view its pipeline.",
            })}
            icon={Sparkles}
          />
        </div>
      ) : stagesQ.isError ? (
        <div className="mt-6">
          <EmptyStateCard
            title={t("hr.pipeline_page.load_failed_title", { defaultValue: "Could not load pipeline" })}
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
                {t("hr.common.retry", { defaultValue: "Retry" })}
              </Button>
            }
          />
        </div>
      ) : (stagesQ.data?.length ?? 0) === 0 && !stagesQ.isPending ? (
        <div className="mt-6">
          <EmptyStateCard
            title={t("hr.pipeline_page.no_stages_title", { defaultValue: "No pipeline stages found" })}
            description={t("hr.pipeline_page.no_stages_description", {
              defaultValue:
                "This opening has no stages yet. Try refreshing or recreate the opening defaults.",
            })}
            icon={Sparkles}
            actions={
              <Button
                type="button"
                variant="outline"
                className="border-white/10 bg-white/[0.03] hover:bg-white/[0.06]"
                onClick={() => stagesQ.refetch()}
              >
                {t("hr.common.retry", { defaultValue: "Retry" })}
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
              <PanelCard
                title={t("hr.pipeline_page.stage_conversion_title", { defaultValue: "Stage conversion" })}
                description={t("hr.pipeline_page.stage_conversion_description", {
                  defaultValue: "Mock funnel stats.",
                })}
              >
                <div className="space-y-3 text-sm text-muted-foreground">
                  <div className="rounded-2xl bg-white/[0.02] p-3 ring-1 ring-white/5">
                    {t("hr.pipeline_page.conv_screened_interview", { defaultValue: "Screened → Interview:" })}{" "}
                    <span className="text-foreground/90 tabular-nums">38%</span>
                  </div>
                  <div className="rounded-2xl bg-white/[0.02] p-3 ring-1 ring-white/5">
                    {t("hr.pipeline_page.conv_interview_offer", { defaultValue: "Interview → Offer:" })}{" "}
                    <span className="text-foreground/90 tabular-nums">22%</span>
                  </div>
                  <div className="rounded-2xl bg-white/[0.02] p-3 ring-1 ring-white/5">
                    {t("hr.pipeline_page.conv_offer_hired", { defaultValue: "Offer → Hired:" })}{" "}
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
                  onSuccess: () =>
                    toast(t("hr.pipeline_page.moved_toast", { defaultValue: "Moved" })),
                  onError: (err) =>
                    toast(t("hr.pipeline_page.move_failed", { defaultValue: "Could not move" }), {
                      description:
                        err instanceof Error ? err.message : "Unknown error",
                    }),
                }
              );
            }}
            onReject={(applicationId) => {
              appsQ.reject.mutate(applicationId, {
                onSuccess: () =>
                  toast(t("hr.pipeline_page.rejected_toast", { defaultValue: "Rejected" })),
                onError: (err) =>
                  toast(t("hr.pipeline_page.reject_failed", { defaultValue: "Could not reject" }), {
                    description:
                      err instanceof Error ? err.message : "Unknown error",
                  }),
              });
            }}
            onHire={(applicationId) => {
              appsQ.hire.mutate(applicationId, {
                onSuccess: () =>
                  toast(t("hr.pipeline_page.hired_toast", { defaultValue: "Marked as hired" })),
                onError: (err) =>
                  toast(t("hr.pipeline_page.hire_failed", { defaultValue: "Could not hire" }), {
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
