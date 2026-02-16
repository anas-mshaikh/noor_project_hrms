"use client";

import * as React from "react";
import { Loader2, MessageSquarePlus, XCircle } from "lucide-react";
import { toast } from "sonner";
import { useTranslation } from "@/lib/i18n";

import type { ApplicationOut, PipelineStageOut, UUID } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useApplicationNotes } from "@/features/hr/hooks/useApplicationNotes";
import { ParsedResumeSheet } from "@/features/hr/components/openings/ParsedResumeSheet";
import { useSelection } from "@/lib/selection";

type ApplicationDrawerProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  application: ApplicationOut | null;
  stages: PipelineStageOut[];
  onMoveStage?: (applicationId: UUID, stageId: UUID) => void;
  onReject?: (applicationId: UUID) => void;
  onHire?: (applicationId: UUID) => void;
  busy?: boolean;
};

function stageNameById(
  stages: PipelineStageOut[],
  stageId: UUID | null,
  fallback: string
): string {
  if (!stageId) return fallback;
  const hit = stages.find((s) => s.id === stageId);
  return hit?.name ?? fallback;
}

export function ApplicationDrawer({
  open,
  onOpenChange,
  application,
  stages,
  onMoveStage,
  onReject,
  onHire,
  busy,
}: ApplicationDrawerProps) {
  const { t } = useTranslation();
  const appId = (open ? application?.id : null) as UUID | null;
  const branchId = useSelection((s) => (s.branchId as UUID | undefined) ?? null);
  const notes = useApplicationNotes(branchId, appId);

  const [note, setNote] = React.useState("");
  const [parsedOpen, setParsedOpen] = React.useState(false);

  React.useEffect(() => {
    if (!open) {
      setNote("");
      setParsedOpen(false);
    }
  }, [open]);

  const stageName = application
    ? stageNameById(
        stages,
        application.stage_id,
        t("hr.common.unassigned", { defaultValue: "Unassigned" })
      )
    : "—";

  return (
    <>
      <Sheet open={open} onOpenChange={onOpenChange}>
        <SheetContent className="w-full sm:max-w-2xl border-white/10 bg-white/[0.03] backdrop-blur-xl">
          <SheetHeader className="gap-2">
            <SheetTitle className="truncate">
              {application?.resume.original_filename ??
                t("hr.application_drawer.title_fallback", { defaultValue: "Application" })}
            </SheetTitle>
            <SheetDescription className="truncate">
              {application
                ? `application_id: ${application.id}`
                : t("hr.application_drawer.select_prompt", {
                    defaultValue: "Select an application to preview.",
                  })}
            </SheetDescription>

            {application ? (
              <div className="flex flex-wrap items-center gap-2 pt-1">
                <span className="rounded-full bg-white/[0.04] px-2 py-0.5 text-xs text-muted-foreground ring-1 ring-white/10">
                  {stageName}
                </span>
                <span className="rounded-full bg-white/[0.04] px-2 py-0.5 text-xs text-muted-foreground ring-1 ring-white/10">
                  {application.status}
                </span>
                <span className="rounded-full bg-white/[0.04] px-2 py-0.5 text-xs text-muted-foreground ring-1 ring-white/10">
                  {t("hr.application_drawer.resume_status_prefix", { defaultValue: "resume:" })}{" "}
                  {application.resume.status}
                </span>
              </div>
            ) : null}
          </SheetHeader>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  type="button"
                  variant="outline"
                  className="h-9 rounded-xl border-white/10 bg-white/[0.03] px-3 text-xs hover:bg-white/[0.06]"
                  disabled={!application || !onMoveStage}
                >
                  {t("hr.application_drawer.move_stage", { defaultValue: "Move stage" })}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="w-52">
                {stages
                  .slice()
                  .sort((a, b) => a.sort_order - b.sort_order)
                  .map((s) => (
                    <DropdownMenuItem
                      key={s.id}
                      onClick={() => {
                        if (!application || !onMoveStage) return;
                        onMoveStage(application.id, s.id);
                      }}
                    >
                      {t("hr.application_drawer.move_to_prefix", { defaultValue: "Move to" })}{" "}
                      {s.name}
                    </DropdownMenuItem>
                  ))}
              </DropdownMenuContent>
            </DropdownMenu>

            <Button
              type="button"
              variant="outline"
              className="h-9 rounded-xl border-white/10 bg-white/[0.03] px-3 text-xs hover:bg-white/[0.06]"
              onClick={() => setParsedOpen(true)}
              disabled={!application}
            >
              {t("hr.application_drawer.view_parsed", { defaultValue: "View parsed" })}
            </Button>

            <div className="flex-1" />

            <Button
              type="button"
              variant="outline"
              className={cn(
                "h-9 rounded-xl border-rose-200/20 bg-rose-500/10 px-3 text-xs text-rose-100 hover:bg-rose-500/15",
                "focus-visible:ring-2 focus-visible:ring-rose-300/40"
              )}
              onClick={() => {
                if (!application || !onReject) return;
                onReject(application.id);
              }}
              disabled={!application || !onReject || Boolean(busy)}
            >
              <XCircle className="h-4 w-4" />
              {t("hr.application_drawer.reject", { defaultValue: "Reject" })}
            </Button>

            <Button
              type="button"
              className="h-9 rounded-xl bg-white/[0.06] px-3 text-xs hover:bg-white/[0.09]"
              onClick={() => {
                if (!application || !onHire) return;
                onHire(application.id);
              }}
              disabled={!application || !onHire || Boolean(busy)}
            >
              {t("hr.application_drawer.hire", { defaultValue: "Hire" })}
            </Button>
          </div>

          <Separator className="my-5 bg-white/10" />

          {/* Notes */}
          <div className="space-y-3">
            <div className="text-sm font-semibold tracking-tight">
              {t("hr.application_drawer.notes_title", { defaultValue: "Notes" })}
            </div>

            <div className="rounded-2xl bg-white/[0.02] p-4 ring-1 ring-white/10">
              {notes.list.isFetching ? (
                <div className="space-y-2">
                  <Skeleton className="h-3 w-5/6 bg-white/10" />
                  <Skeleton className="h-3 w-4/6 bg-white/10" />
                </div>
              ) : notes.list.isError ? (
                <div className="text-sm text-muted-foreground">
                  {t("hr.application_drawer.notes_load_failed", {
                    defaultValue: "Could not load notes.",
                  })}
                </div>
              ) : (notes.list.data?.length ?? 0) === 0 ? (
                <div className="text-sm text-muted-foreground">
                  {t("hr.application_drawer.notes_empty", {
                    defaultValue: "No notes yet. Add one below.",
                  })}
                </div>
              ) : (
                <div className="max-h-[40vh] space-y-3 overflow-auto pr-1">
                  {notes.list.data?.map((n) => (
                    <div key={n.id} className="rounded-2xl bg-white/[0.02] p-3 ring-1 ring-white/5">
                      <div className="text-sm text-foreground/90 whitespace-pre-wrap">
                        {n.note}
                      </div>
                      <div className="mt-2 text-[11px] text-muted-foreground tabular-nums">
                        {new Date(n.created_at).toLocaleString()}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="rounded-2xl bg-white/[0.02] p-4 ring-1 ring-white/10">
              <div className="flex items-start gap-3">
                <textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder={t("hr.application_drawer.note_placeholder", {
                    defaultValue: "Add a note…",
                  })}
                  className={cn(
                    "min-h-[90px] w-full resize-none rounded-xl border border-white/10 bg-white/[0.03] p-3 text-sm text-foreground/90",
                    "placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-300/60"
                  )}
                  aria-label="Add note"
                  disabled={!application || notes.create.isPending}
                />
                <Button
                  type="button"
                  className="h-10 rounded-xl bg-white/[0.06] px-3 text-xs hover:bg-white/[0.09]"
                  onClick={() => {
                    const text = note.trim();
                    if (!text) {
                      toast(
                        t("hr.application_drawer.note_empty_toast", {
                          defaultValue: "Note is empty",
                        })
                      );
                      return;
                    }
                    notes.create.mutate(
                      { note: text },
                      {
                        onSuccess: () => {
                          toast(
                            t("hr.application_drawer.note_added_toast", {
                              defaultValue: "Note added",
                            })
                          );
                          setNote("");
                        },
                        onError: (err) => {
                          toast(t("hr.application_drawer.note_add_failed", { defaultValue: "Could not add note" }), {
                            description:
                              err instanceof Error ? err.message : "Unknown error",
                          });
                        },
                      }
                    );
                  }}
                  disabled={!application || notes.create.isPending}
                  aria-label="Add note"
                >
                  {notes.create.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <MessageSquarePlus className="h-4 w-4" />
                  )}
                  {t("hr.application_drawer.add", { defaultValue: "Add" })}
                </Button>
              </div>
            </div>
          </div>
        </SheetContent>
      </Sheet>

      <ParsedResumeSheet
        open={parsedOpen}
        onOpenChange={setParsedOpen}
        resumeId={(application?.resume_id ?? null) as UUID | null}
        title={application?.resume.original_filename}
      />
    </>
  );
}
