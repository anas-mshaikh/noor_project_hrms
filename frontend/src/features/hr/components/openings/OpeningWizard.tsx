"use client";

import * as React from "react";
import { toast } from "sonner";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { GlassCard } from "@/features/hr/components/cards/GlassCard";
import { TagChip } from "@/features/hr/components/candidates/TagChip";

type WizardDraft = {
  title: string;
  department: string;
  location: string;
  jdText: string;
  requirements: string[];
};

type OpeningWizardProps = {
  onSave: (draft: WizardDraft) => void;
};

const STEPS = ["Basics", "Job Description", "Requirements"] as const;

export function OpeningWizard({ onSave }: OpeningWizardProps) {
  const [step, setStep] = React.useState(0);
  const [draft, setDraft] = React.useState<WizardDraft>({
    title: "",
    department: "",
    location: "",
    jdText: "",
    requirements: ["Customer service", "POS handling"],
  });
  const [reqInput, setReqInput] = React.useState("");

  const canNext = step < STEPS.length - 1;
  const canBack = step > 0;

  function addRequirement() {
    const v = reqInput.trim();
    if (!v) return;
    setDraft((d) => ({ ...d, requirements: [...d.requirements, v] }));
    setReqInput("");
  }

  return (
    <div className="grid gap-6 lg:grid-cols-12">
      <div className="space-y-4 lg:col-span-8">
        <GlassCard className="p-5">
          <div className="flex flex-wrap items-center gap-2">
            {STEPS.map((s, idx) => (
              <span
                key={s}
                className={cn(
                  "rounded-full px-3 py-1 text-xs ring-1",
                  idx === step
                    ? "bg-white/[0.06] text-foreground ring-white/15"
                    : "bg-white/[0.03] text-muted-foreground ring-white/10"
                )}
              >
                {idx + 1}. {s}
              </span>
            ))}
          </div>

          <div className="mt-5">
            {step === 0 ? (
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="title">Title</Label>
                  <Input
                    id="title"
                    placeholder="e.g. Cashier"
                    value={draft.title}
                    onChange={(e) => setDraft((d) => ({ ...d, title: e.target.value }))}
                    className="border-white/10 bg-white/[0.03]"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="dept">Department</Label>
                  <Input
                    id="dept"
                    placeholder="e.g. Front Desk"
                    value={draft.department}
                    onChange={(e) =>
                      setDraft((d) => ({ ...d, department: e.target.value }))
                    }
                    className="border-white/10 bg-white/[0.03]"
                  />
                </div>
                <div className="space-y-2 md:col-span-2">
                  <Label htmlFor="loc">Location</Label>
                  <Input
                    id="loc"
                    placeholder="e.g. Dariyapur"
                    value={draft.location}
                    onChange={(e) =>
                      setDraft((d) => ({ ...d, location: e.target.value }))
                    }
                    className="border-white/10 bg-white/[0.03]"
                  />
                </div>
              </div>
            ) : null}

            {step === 1 ? (
              <div className="space-y-2">
                <Label htmlFor="jd">Job description</Label>
                <textarea
                  id="jd"
                  value={draft.jdText}
                  onChange={(e) => setDraft((d) => ({ ...d, jdText: e.target.value }))}
                  placeholder="Paste the job description here…"
                  className="min-h-44 w-full resize-y rounded-2xl border border-white/10 bg-white/[0.03] px-3 py-2 text-sm outline-none ring-offset-background focus-visible:ring-2 focus-visible:ring-violet-300/50"
                />
              </div>
            ) : null}

            {step === 2 ? (
              <div>
                <div className="flex flex-col gap-2 md:flex-row md:items-end">
                  <div className="flex-1 space-y-2">
                    <Label htmlFor="req">Add requirement</Label>
                    <Input
                      id="req"
                      value={reqInput}
                      onChange={(e) => setReqInput(e.target.value)}
                      placeholder="e.g. Weekend shifts"
                      className="border-white/10 bg-white/[0.03]"
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          addRequirement();
                        }
                      }}
                    />
                  </div>
                  <Button
                    type="button"
                    onClick={addRequirement}
                    className="rounded-2xl bg-white/[0.06] hover:bg-white/[0.09]"
                  >
                    Add
                  </Button>
                </div>

                <div className="mt-4 flex flex-wrap gap-2">
                  {draft.requirements.map((r) => (
                    <TagChip key={r}>{r}</TagChip>
                  ))}
                </div>
              </div>
            ) : null}
          </div>

          <div className="mt-6 flex flex-wrap justify-between gap-2">
            <Button
              type="button"
              variant="ghost"
              disabled={!canBack}
              onClick={() => setStep((s) => Math.max(0, s - 1))}
              className="rounded-2xl"
            >
              Back
            </Button>
            <div className="flex gap-2">
              {canNext ? (
                <Button
                  type="button"
                  onClick={() => setStep((s) => Math.min(STEPS.length - 1, s + 1))}
                  className="rounded-2xl bg-white/[0.06] hover:bg-white/[0.09]"
                >
                  Next
                </Button>
              ) : (
                <Button
                  type="button"
                  onClick={() => {
                    toast("Saved (mock)", { description: "Opening created" });
                    onSave(draft);
                  }}
                  className="rounded-2xl bg-gradient-to-r from-violet-500 to-fuchsia-500 text-white hover:from-violet-400 hover:to-fuchsia-400"
                >
                  Save Opening
                </Button>
              )}
            </div>
          </div>
        </GlassCard>
      </div>

      <div className="lg:col-span-4">
        <GlassCard className="p-5">
          <div className="text-sm font-semibold tracking-tight">Preview</div>
          <div className="mt-2 text-sm text-muted-foreground">
            This is how the opening will appear in the HR list.
          </div>
          <div className="mt-4 space-y-3 rounded-2xl bg-white/[0.02] p-4 ring-1 ring-white/5">
            <div className="text-base font-semibold">
              {draft.title || "Untitled opening"}
            </div>
            <div className="text-xs text-muted-foreground">
              {draft.department || "Department"} • {draft.location || "Location"}
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {draft.requirements.slice(0, 4).map((r) => (
                <TagChip key={r} className="bg-white/[0.03]">
                  {r}
                </TagChip>
              ))}
            </div>
          </div>
        </GlassCard>
      </div>
    </div>
  );
}

