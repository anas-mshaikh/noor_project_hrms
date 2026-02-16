"use client";

import * as React from "react";
import { Loader2 } from "lucide-react";
import { useTranslation } from "@/lib/i18n";

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
  saving?: boolean;
};

export function OpeningWizard({ onSave, saving }: OpeningWizardProps) {
  const { t } = useTranslation();
  const [step, setStep] = React.useState(0);
  const [draft, setDraft] = React.useState<WizardDraft>({
    title: "",
    department: "",
    location: "",
    jdText: "",
    requirements: ["Customer service", "POS handling"],
  });
  const [reqInput, setReqInput] = React.useState("");

  const STEPS = React.useMemo(
    () =>
      [
        t("hr.opening_wizard.steps.basics", { defaultValue: "Basics" }),
        t("hr.opening_wizard.steps.jd", { defaultValue: "Job Description" }),
        t("hr.opening_wizard.steps.requirements", { defaultValue: "Requirements" }),
      ] as const,
    [t]
  );

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
                  <Label htmlFor="title">
                    {t("hr.opening_wizard.title_label", { defaultValue: "Title" })}
                  </Label>
                  <Input
                    id="title"
                    placeholder={t("hr.opening_wizard.title_placeholder", {
                      defaultValue: "e.g. Cashier",
                    })}
                    value={draft.title}
                    onChange={(e) => setDraft((d) => ({ ...d, title: e.target.value }))}
                    className="border-white/10 bg-white/[0.03]"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="dept">
                    {t("hr.opening_wizard.department_label", { defaultValue: "Department" })}
                  </Label>
                  <Input
                    id="dept"
                    placeholder={t("hr.opening_wizard.department_placeholder", {
                      defaultValue: "e.g. Front Desk",
                    })}
                    value={draft.department}
                    onChange={(e) =>
                      setDraft((d) => ({ ...d, department: e.target.value }))
                    }
                    className="border-white/10 bg-white/[0.03]"
                  />
                </div>
                <div className="space-y-2 md:col-span-2">
                  <Label htmlFor="loc">
                    {t("hr.opening_wizard.location_label", { defaultValue: "Location" })}
                  </Label>
                  <Input
                    id="loc"
                    placeholder={t("hr.opening_wizard.location_placeholder", {
                      defaultValue: "e.g. Riyadh",
                    })}
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
                <Label htmlFor="jd">
                  {t("hr.opening_wizard.jd_label", { defaultValue: "Job description" })}
                </Label>
                <textarea
                  id="jd"
                  value={draft.jdText}
                  onChange={(e) => setDraft((d) => ({ ...d, jdText: e.target.value }))}
                  placeholder={t("hr.opening_wizard.jd_placeholder", {
                    defaultValue: "Paste the job description here…",
                  })}
                  className="min-h-44 w-full resize-y rounded-2xl border border-white/10 bg-white/[0.03] px-3 py-2 text-sm outline-none ring-offset-background focus-visible:ring-2 focus-visible:ring-violet-300/50"
                />
              </div>
            ) : null}

            {step === 2 ? (
              <div>
                <div className="flex flex-col gap-2 md:flex-row md:items-end">
                  <div className="flex-1 space-y-2">
                    <Label htmlFor="req">
                      {t("hr.opening_wizard.add_requirement_label", {
                        defaultValue: "Add requirement",
                      })}
                    </Label>
                    <Input
                      id="req"
                      value={reqInput}
                      onChange={(e) => setReqInput(e.target.value)}
                      placeholder={t("hr.opening_wizard.add_requirement_placeholder", {
                        defaultValue: "e.g. Weekend shifts",
                      })}
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
                    {t("hr.opening_wizard.add", { defaultValue: "Add" })}
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
              {t("hr.opening_wizard.back", { defaultValue: "Back" })}
            </Button>
            <div className="flex gap-2">
              {canNext ? (
                <Button
                  type="button"
                  onClick={() => setStep((s) => Math.min(STEPS.length - 1, s + 1))}
                  className="rounded-2xl bg-white/[0.06] hover:bg-white/[0.09]"
                >
                  {t("hr.opening_wizard.next", { defaultValue: "Next" })}
                </Button>
              ) : (
                <Button
                  type="button"
                  onClick={() => {
                    onSave(draft);
                  }}
                  disabled={Boolean(saving)}
                  className="rounded-2xl bg-gradient-to-r from-violet-500 to-fuchsia-500 text-white hover:from-violet-400 hover:to-fuchsia-400"
                >
                  {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                  {saving
                    ? t("hr.opening_wizard.saving", { defaultValue: "Saving…" })
                    : t("hr.opening_wizard.save_opening", { defaultValue: "Save Opening" })}
                </Button>
              )}
            </div>
          </div>
        </GlassCard>
      </div>

      <div className="lg:col-span-4">
        <GlassCard className="p-5">
          <div className="text-sm font-semibold tracking-tight">
            {t("hr.opening_wizard.preview_title", { defaultValue: "Preview" })}
          </div>
          <div className="mt-2 text-sm text-muted-foreground">
            {t("hr.opening_wizard.preview_description", {
              defaultValue: "This is how the opening will appear in the HR list.",
            })}
          </div>
          <div className="mt-4 space-y-3 rounded-2xl bg-white/[0.02] p-4 ring-1 ring-white/5">
            <div className="text-base font-semibold">
              {draft.title ||
                t("hr.opening_wizard.untitled_opening", { defaultValue: "Untitled opening" })}
            </div>
            <div className="text-xs text-muted-foreground">
              {draft.department ||
                t("hr.opening_wizard.department_fallback", { defaultValue: "Department" })}{" "}
              •{" "}
              {draft.location ||
                t("hr.opening_wizard.location_fallback", { defaultValue: "Location" })}
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
