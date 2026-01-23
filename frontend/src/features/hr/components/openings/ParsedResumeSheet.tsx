"use client";

import * as React from "react";
import { AlertTriangle, Code2, FileText, Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";
import type { ParsedResumeArtifact, UUID } from "@/lib/types";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useParsedResume } from "@/features/hr/hooks/useParsedResume";

type ParsedResumeSheetProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  resumeId: UUID | null;
  title?: string;
};

function cleanTextFromArtifact(data: ParsedResumeArtifact | undefined): string {
  const clean = data?.clean_text;
  if (typeof clean === "string") return clean;
  // Some parsers might store it under a nested key; keep this defensive.
  const maybe = (data as Record<string, unknown> | undefined)?.cleanText;
  if (typeof maybe === "string") return maybe;
  return "";
}

export function ParsedResumeSheet({
  open,
  onOpenChange,
  resumeId,
  title,
}: ParsedResumeSheetProps) {
  const [showRaw, setShowRaw] = React.useState(false);

  const q = useParsedResume(resumeId, open);
  const cleanText = cleanTextFromArtifact(q.data);

  React.useEffect(() => {
    if (!open) setShowRaw(false);
  }, [open]);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-2xl border-white/10 bg-white/[0.03] backdrop-blur-xl">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2 text-base">
            <FileText className="h-4 w-4 text-violet-200" />
            {title ?? "Parsed resume"}
          </SheetTitle>
        </SheetHeader>

        <div className="mt-4 flex items-center justify-between gap-2">
          <div className="text-xs text-muted-foreground">
            {q.isFetching ? "Loading parsed artifact…" : q.data ? "Parsed text preview" : "—"}
          </div>
          <Button
            type="button"
            variant="outline"
            className="h-8 rounded-xl border-white/10 bg-white/[0.03] px-3 text-xs hover:bg-white/[0.06]"
            onClick={() => setShowRaw((v) => !v)}
            disabled={!q.data}
          >
            <Code2 className="h-3.5 w-3.5" />
            Developer
          </Button>
        </div>

        <div className="mt-3 rounded-2xl bg-white/[0.02] ring-1 ring-white/10 overflow-hidden">
          {q.isFetching ? (
            <div className="p-4 space-y-3">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Fetching…
              </div>
              <Skeleton className="h-3 w-5/6 bg-white/10" />
              <Skeleton className="h-3 w-4/6 bg-white/10" />
              <Skeleton className="h-3 w-3/6 bg-white/10" />
            </div>
          ) : q.isError ? (
            <div className="p-4">
              <div className="flex items-start gap-2 text-sm">
                <AlertTriangle className="mt-0.5 h-4 w-4 text-rose-300" />
                <div>
                  <div className="font-medium">Could not load parsed resume</div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {q.error instanceof Error ? q.error.message : "Unknown error"}
                  </div>
                </div>
              </div>
            </div>
          ) : !q.data ? (
            <div className="p-4 text-sm text-muted-foreground">No parsed artifact available.</div>
          ) : showRaw ? (
            <pre className="max-h-[70vh] overflow-auto p-4 text-xs text-foreground/90 whitespace-pre-wrap">
              {JSON.stringify(q.data, null, 2)}
            </pre>
          ) : (
            <div className={cn("max-h-[70vh] overflow-auto p-4", cleanText ? "" : "text-muted-foreground")}>
              {cleanText ? (
                <pre className="whitespace-pre-wrap text-sm leading-relaxed text-foreground/90">
                  {cleanText.slice(0, 15000)}
                  {cleanText.length > 15000 ? "\n\n…(truncated)" : ""}
                </pre>
              ) : (
                <div className="text-sm">Parsed artifact loaded, but no `clean_text` field found.</div>
              )}
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}

