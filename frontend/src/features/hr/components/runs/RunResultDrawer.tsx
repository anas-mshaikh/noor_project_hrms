"use client";

import * as React from "react";
import { AlertTriangle, Code2, FileText, Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";

import type { ScreeningResultRowOut, UUID } from "@/lib/types";
import { toastApiError } from "@/lib/toastApiError";
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
import { ScorePill } from "@/features/hr/components/candidates/ScorePill";
import { TagChip } from "@/features/hr/components/candidates/TagChip";
import { useParsedResume } from "@/features/hr/hooks/useParsedResume";
import { useExplainActions } from "@/features/hr/hooks/useExplainActions";
import { useScreeningExplanation } from "@/features/hr/hooks/useScreeningExplanation";
import { toScorePercent } from "@/features/hr/lib/scoring";
import { useSelection } from "@/lib/selection";

type RunResultDrawerProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  runId: UUID;
  result: ScreeningResultRowOut | null;
};

function parseStatusCode(err: unknown): number | null {
  if (!(err instanceof Error)) return null;
  const m = err.message.trim();
  const maybe = Number(m.slice(0, 3));
  return Number.isFinite(maybe) ? maybe : null;
}

function asStringArray(v: unknown): string[] {
  if (!Array.isArray(v)) return [];
  return v.filter((x): x is string => typeof x === "string").slice(0, 6);
}

type EvidenceItem = { claim: string; quote: string };
function asEvidence(v: unknown): EvidenceItem[] {
  if (!Array.isArray(v)) return [];
  const out: EvidenceItem[] = [];
  for (const item of v) {
    if (!item || typeof item !== "object") continue;
    const claim = (item as Record<string, unknown>).claim;
    const quote = (item as Record<string, unknown>).quote;
    if (typeof claim === "string" && typeof quote === "string") {
      out.push({ claim, quote });
    }
    if (out.length >= 4) break;
  }
  return out;
}

function cleanTextFromArtifact(data: Record<string, unknown> | undefined): string {
  const clean = data?.clean_text;
  if (typeof clean === "string") return clean;
  const maybe = data?.cleanText;
  if (typeof maybe === "string") return maybe;
  return "";
}

export function RunResultDrawer({
  open,
  onOpenChange,
  runId,
  result,
}: RunResultDrawerProps) {
  const [showDev, setShowDev] = React.useState(false);
  const [pollExplain, setPollExplain] = React.useState(false);

  const branchId = useSelection((s) => (s.branchId as UUID | undefined) ?? null);

  const resumeId = (result?.resume_id ?? null) as UUID | null;
  const parsedQ = useParsedResume(branchId, resumeId, open);

  const explainQ = useScreeningExplanation(branchId, runId, resumeId, {
    enabled: open && Boolean(resumeId),
    pollIntervalMs: pollExplain ? 2000 : undefined,
  });
  const explain = useExplainActions(branchId, runId);

  const explainStatus = parseStatusCode(explainQ.error);
  const parsedStatus = parseStatusCode(parsedQ.error);

  React.useEffect(() => {
    if (explainQ.data) setPollExplain(false);
  }, [explainQ.data]);

  React.useEffect(() => {
    if (!open) {
      setShowDev(false);
      setPollExplain(false);
    }
  }, [open]);

  const displayScore = result ? toScorePercent(result.final_score) : 0;

  // Explanation JSON schema (Phase 4 prompt v1).
  const exp = (explainQ.data?.explanation_json ?? {}) as Record<string, unknown>;
  const expFit = typeof exp.fit_score === "number" ? Math.round(exp.fit_score) : null;
  const expSummary = typeof exp.one_line_summary === "string" ? exp.one_line_summary : null;
  const expMatched = asStringArray(exp.matched_requirements);
  const expMissing = asStringArray(exp.missing_requirements);
  const expStrengths = asStringArray(exp.strengths);
  const expRisks = asStringArray(exp.risks);
  const expEvidence = asEvidence(exp.evidence);

  const cleanText = cleanTextFromArtifact(parsedQ.data as Record<string, unknown> | undefined);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-2xl border-white/10 bg-white/[0.03] backdrop-blur-xl">
        <SheetHeader className="gap-2">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <SheetTitle className="truncate">
                {result?.original_filename ?? "Candidate"}
              </SheetTitle>
              <SheetDescription className="truncate">
                {result ? `resume_id: ${result.resume_id}` : "Select a result to preview."}
              </SheetDescription>
            </div>
            {result ? (
              <div className="shrink-0 text-right">
                <div className="text-[10px] font-medium text-muted-foreground">
                  Model score
                </div>
                <ScorePill score={displayScore} />
              </div>
            ) : null}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {result?.best_view_type ? <TagChip>{result.best_view_type}</TagChip> : null}
            {result?.retrieval_score != null ? (
              <TagChip className="bg-white/[0.03]">retrieval: {result.retrieval_score.toFixed(3)}</TagChip>
            ) : null}
          </div>
        </SheetHeader>

        <div className="mt-4 flex items-center justify-between gap-2">
          <div className="text-xs text-muted-foreground">
            {pollExplain ? "Generating explanation…" : "Candidate details"}
          </div>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              className="h-8 rounded-xl border-white/10 bg-white/[0.03] px-3 text-xs hover:bg-white/[0.06]"
              onClick={() => setShowDev((v) => !v)}
            >
              <Code2 className="h-3.5 w-3.5" />
              Developer
            </Button>
          </div>
        </div>

        <div className="mt-3 space-y-4">
          {/* Explanation */}
          <div className="rounded-2xl bg-white/[0.02] p-4 ring-1 ring-white/10">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                <Sparkles className="h-4 w-4" />
                Explanation
              </div>
              <Button
                type="button"
                className="h-8 rounded-xl bg-white/[0.06] px-3 text-xs hover:bg-white/[0.09]"
                onClick={() => {
                  if (!resumeId) return;
                  setPollExplain(true);
                  explain.recomputeOne.mutate(
                    { resumeId, force: true },
                    {
                      onSuccess: () => {
                        toast("Explanation queued", { description: "Generating…" });
                      },
                      onError: (err) => {
                        setPollExplain(false);
                        toastApiError(err);
                      },
                    }
                  );
                }}
                disabled={!resumeId || explain.recomputeOne.isPending}
                aria-label="Generate explanation"
              >
                {explain.recomputeOne.isPending ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  "Generate"
                )}
              </Button>
            </div>

            {explainQ.isFetching ? (
              <div className="mt-3 space-y-2">
                <Skeleton className="h-3 w-5/6 bg-white/10" />
                <Skeleton className="h-3 w-4/6 bg-white/10" />
              </div>
            ) : explainQ.data ? (
              <div className="mt-3 space-y-4">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-sm font-medium tracking-tight">
                    LLM Summary
                  </div>
                  {typeof expFit === "number" ? (
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-medium text-muted-foreground">
                        LLM fit
                      </span>
                      <ScorePill
                        score={Math.max(0, Math.min(100, expFit))}
                      />
                    </div>
                  ) : null}
                </div>
                {expSummary ? <div className="text-sm text-muted-foreground">{expSummary}</div> : null}

                {(expMatched.length || expMissing.length) ? (
                  <div className="grid gap-3 md:grid-cols-2">
                    <div>
                      <div className="text-xs font-medium text-muted-foreground">Matched</div>
                      <ul className="mt-2 space-y-2 text-sm">
                        {expMatched.map((r) => (
                          <li key={r} className="flex items-start gap-2">
                            <span className="mt-1 h-1.5 w-1.5 rounded-full bg-emerald-300/80" />
                            <span className="text-foreground/90">{r}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                    <div>
                      <div className="text-xs font-medium text-muted-foreground">Missing</div>
                      <ul className="mt-2 space-y-2 text-sm">
                        {expMissing.map((r) => (
                          <li key={r} className="flex items-start gap-2">
                            <span className="mt-1 h-1.5 w-1.5 rounded-full bg-fuchsia-300/70" />
                            <span className="text-foreground/90">{r}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                ) : null}

                {(expStrengths.length || expRisks.length) ? (
                  <div className="grid gap-3 md:grid-cols-2">
                    <div>
                      <div className="text-xs font-medium text-muted-foreground">Strengths</div>
                      <ul className="mt-2 space-y-2 text-sm">
                        {expStrengths.map((r) => (
                          <li key={r} className="flex items-start gap-2">
                            <span className="mt-1 h-1.5 w-1.5 rounded-full bg-violet-300/70" />
                            <span className="text-foreground/90">{r}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                    <div>
                      <div className="text-xs font-medium text-muted-foreground">Risks</div>
                      <ul className="mt-2 space-y-2 text-sm">
                        {expRisks.map((r) => (
                          <li key={r} className="flex items-start gap-2">
                            <span className="mt-1 h-1.5 w-1.5 rounded-full bg-rose-300/70" />
                            <span className="text-foreground/90">{r}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                ) : null}

                {expEvidence.length ? (
                  <div>
                    <div className="text-xs font-medium text-muted-foreground">Evidence</div>
                    <div className="mt-2 space-y-2">
                      {expEvidence.map((e, idx) => (
                        <div key={idx} className="rounded-2xl bg-white/[0.02] p-3 ring-1 ring-white/5">
                          <div className="text-xs font-medium text-muted-foreground">{e.claim}</div>
                          <div className="mt-1 text-sm text-foreground/90">
                            <span className="text-muted-foreground">“</span>
                            {e.quote}
                            <span className="text-muted-foreground">”</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            ) : explainStatus === 404 ? (
              <div className="mt-3 text-sm text-muted-foreground">
                No explanation yet.
              </div>
            ) : explainStatus === 400 ? (
              <div className="mt-3 text-sm text-muted-foreground">
                Explanations are not configured on the backend (Gemini API key).
              </div>
            ) : explainStatus === 409 ? (
              <div className="mt-3 text-sm text-muted-foreground">
                Run is not DONE yet.
              </div>
            ) : explainQ.isError ? (
              <div className="mt-3 flex items-start gap-2 text-sm">
                <AlertTriangle className="mt-0.5 h-4 w-4 text-rose-300" />
                <div className="text-muted-foreground">
                  {explainQ.error instanceof Error ? explainQ.error.message : "Could not load explanation"}
                </div>
              </div>
            ) : null}
          </div>

          <Separator className="bg-white/10" />

          {/* Parsed text */}
          <div className="rounded-2xl bg-white/[0.02] ring-1 ring-white/10 overflow-hidden">
            <div className="flex items-center justify-between gap-2 border-b border-white/10 px-4 py-3">
              <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                <FileText className="h-4 w-4" />
                Parsed resume
              </div>
              <div className="text-xs text-muted-foreground">
                {parsedQ.isFetching ? "Loading…" : parsedQ.data ? "Preview" : "—"}
              </div>
            </div>

            {parsedQ.isFetching ? (
              <div className="p-4 space-y-3">
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Fetching…
                </div>
                <Skeleton className="h-3 w-5/6 bg-white/10" />
                <Skeleton className="h-3 w-4/6 bg-white/10" />
                <Skeleton className="h-3 w-3/6 bg-white/10" />
              </div>
            ) : parsedStatus === 409 ? (
              <div className="p-4 text-sm text-muted-foreground">
                Resume is still parsing.
              </div>
            ) : parsedQ.isError ? (
              <div className="p-4">
                <div className="flex items-start gap-2 text-sm">
                  <AlertTriangle className="mt-0.5 h-4 w-4 text-rose-300" />
                  <div>
                    <div className="font-medium">Could not load parsed resume</div>
                    <div className="mt-1 text-xs text-muted-foreground">
                      {parsedQ.error instanceof Error ? parsedQ.error.message : "Unknown error"}
                    </div>
                  </div>
                </div>
              </div>
            ) : !parsedQ.data ? (
              <div className="p-4 text-sm text-muted-foreground">No parsed artifact available.</div>
            ) : showDev ? (
              <pre className="max-h-[50vh] overflow-auto p-4 text-xs text-foreground/90 whitespace-pre-wrap">
                {JSON.stringify(parsedQ.data, null, 2)}
              </pre>
            ) : (
              <div className={cn("max-h-[50vh] overflow-auto p-4", cleanText ? "" : "text-muted-foreground")}>
                {cleanText ? (
                  <pre className="whitespace-pre-wrap text-sm leading-relaxed text-foreground/90">
                    {cleanText.slice(0, 12000)}
                    {cleanText.length > 12000 ? "\n\n…(truncated)" : ""}
                  </pre>
                ) : (
                  <div className="text-sm">
                    Parsed artifact loaded, but no <code>clean_text</code> field found.
                  </div>
                )}
              </div>
            )}
          </div>

          {showDev && explainQ.data ? (
            <div className="rounded-2xl bg-white/[0.02] p-4 ring-1 ring-white/10">
              <div className="text-xs font-medium text-muted-foreground">Explanation JSON</div>
              <pre className="mt-2 max-h-[40vh] overflow-auto text-xs text-foreground/90 whitespace-pre-wrap">
                {JSON.stringify(explainQ.data.explanation_json, null, 2)}
              </pre>
            </div>
          ) : null}
        </div>
      </SheetContent>
    </Sheet>
  );
}
