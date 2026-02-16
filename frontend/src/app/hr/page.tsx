"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import {
  CalendarClock,
  CheckCircle2,
  ClipboardList,
  Sparkles,
  Users2,
  Zap,
} from "lucide-react";
import { toast } from "sonner";
import { useTranslation } from "@/lib/i18n";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { HrPageShell } from "@/features/hr/components/layout/HrPageShell";
import { HrHeader } from "@/features/hr/components/layout/HrHeader";
import { GradientButton } from "@/features/hr/components/cards/GradientButton";
import { StatCard } from "@/features/hr/components/cards/StatCard";
import { GlassCard } from "@/features/hr/components/cards/GlassCard";
import { EmptyStateCard } from "@/features/hr/components/cards/EmptyStateCard";
import { PanelCard } from "@/features/hr/components/cards/PanelCard";
import { useMockLoading } from "@/features/hr/hooks/useMockLoading";
import { useReducedMotion } from "@/features/hr/hooks/useReducedMotion";
import { staggerContainer, staggerItem } from "@/features/hr/lib/motion";
import { HR_ONBOARDING, HR_PIPELINE_CARDS } from "@/features/hr/mock/data";
import { useSelection } from "@/lib/selection";
import { useOpenings } from "@/features/hr/hooks/useOpenings";
import { StorePicker } from "@/components/StorePicker";

type ActivityItem = {
  id: string;
  text: string;
  when: string;
  icon: React.ComponentType<{ className?: string }>;
};

export default function HROverviewPage() {
  const { t } = useTranslation();
  const reducedMotion = useReducedMotion();
  const { loading } = useMockLoading(600);

  const branchId = useSelection((s) => s.branchId);
  const showDebugIds =
    process.env.NEXT_PUBLIC_SHOW_DEBUG_IDS === "true" ||
    process.env.NODE_ENV === "development";
  const { list } = useOpenings(branchId ?? null);

  const openings = list.data ?? [];
  const activeOpenings = openings.filter((o) => o.status === "ACTIVE").length;
  const inPipeline = HR_PIPELINE_CARDS.filter((c) => c.stage !== "rejected").length;
  const onboardingActive = HR_ONBOARDING.length;
  const screened7d = 128;

  const topOpening = openings.find((o) => o.status === "ACTIVE") ?? null;

  const isEmpty = Boolean(branchId) && !list.isPending && activeOpenings === 0;

  const chips = [
    !branchId
      ? t("hr.common.select_branch", { defaultValue: "Select a branch" })
      : showDebugIds
        ? `branch_id: ${branchId}`
        : null,
    topOpening
      ? `${t("hr.overview_page.top_opening_prefix", { defaultValue: "Top opening:" })} ${topOpening.title}`
      : null,
    t("hr.overview_page.last_run_chip", { defaultValue: "Last run: Cashier (DONE)" }),
  ].filter(Boolean) as string[];

  const activity: ActivityItem[] = [
    {
      id: "a1",
      text: t("hr.overview_page.activity_1", {
        defaultValue: "Screening run completed — Cashier",
      }),
      when: t("hr.overview_page.when_2m", { defaultValue: "2m ago" }),
      icon: Zap,
    },
    {
      id: "a2",
      text: t("hr.overview_page.activity_2", {
        defaultValue: "12 candidates moved to Interview",
      }),
      when: t("hr.overview_page.when_1h", { defaultValue: "1h ago" }),
      icon: Users2,
    },
    {
      id: "a3",
      text: t("hr.overview_page.activity_3", {
        defaultValue: "Offer sent — Sales Associate",
      }),
      when: t("hr.overview_page.when_yesterday", { defaultValue: "Yesterday" }),
      icon: CheckCircle2,
    },
  ];

  return (
    <HrPageShell>
      <HrHeader
        title={t("hr.overview_page.title", { defaultValue: "HR Overview" })}
        subtitle={t("hr.overview_page.subtitle", {
          defaultValue: "AI-powered hiring → pipeline → onboarding.",
        })}
        chips={chips}
        actions={
          <>
            <GradientButton
              onClick={() =>
                toast(t("common.coming_soon", { defaultValue: "Coming soon" }), {
                  description: t("hr.overview_page.run_screening", { defaultValue: "Run Screening" }),
                })
              }
            >
              {t("hr.overview_page.run_screening", { defaultValue: "Run Screening" })}
            </GradientButton>
            <Button asChild variant="outline" className="border-white/10 bg-white/[0.03] hover:bg-white/[0.06]">
              <Link href="/hr/openings/new">
                {t("hr.overview_page.create_opening", { defaultValue: "Create Opening" })}
              </Link>
            </Button>
            <Button
              type="button"
              variant="outline"
              className="border-white/10 bg-white/[0.03] hover:bg-white/[0.06]"
              onClick={() =>
                toast(t("common.coming_soon", { defaultValue: "Coming soon" }), {
                  description: t("hr.overview_page.upload_resumes", { defaultValue: "Upload Resumes" }),
                })
              }
            >
              {t("hr.overview_page.upload_resumes", { defaultValue: "Upload Resumes" })}
            </Button>
          </>
        }
      />

      {!branchId ? (
        <EmptyStateCard
          title={t("hr.overview_page.empty_title", {
            defaultValue: "Select a branch to manage HR",
          })}
          description={t("hr.overview_page.empty_description", {
            defaultValue:
              "HR data is branch-scoped. Pick a branch to view openings and uploads.",
          })}
          icon={Users2}
          actions={<div className="w-full max-w-xl"><StorePicker /></div>}
        />
      ) : list.isError ? (
        <EmptyStateCard
          title={t("hr.overview_page.error_title", {
            defaultValue: "Could not load HR data",
          })}
          description={list.error instanceof Error ? list.error.message : "Unknown error"}
          icon={Users2}
          actions={
            <Button
              type="button"
              variant="outline"
              className="border-white/10 bg-white/[0.03] hover:bg-white/[0.06]"
              onClick={() => list.refetch()}
            >
              {t("hr.common.retry", { defaultValue: "Retry" })}
            </Button>
          }
        />
      ) : (
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="space-y-6 lg:col-span-8">
          <motion.div
            variants={staggerContainer(reducedMotion)}
            initial="hidden"
            animate="show"
            className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4"
          >
            <motion.div variants={staggerItem(reducedMotion)}>
              <StatCard
                label={t("hr.overview_page.stats_active_openings", { defaultValue: "Active Openings" })}
                value={list.isPending ? "—" : activeOpenings}
                icon={ClipboardList}
                loading={loading || list.isPending}
              />
            </motion.div>
            <motion.div variants={staggerItem(reducedMotion)}>
              <StatCard
                label={t("hr.overview_page.stats_screened_7d", { defaultValue: "Candidates Screened (7d)" })}
                value={screened7d}
                icon={Zap}
                loading={loading}
              />
            </motion.div>
            <motion.div variants={staggerItem(reducedMotion)}>
              <StatCard
                label={t("hr.overview_page.stats_in_pipeline", { defaultValue: "In Pipeline" })}
                value={inPipeline}
                icon={Users2}
                loading={loading}
              />
            </motion.div>
            <motion.div variants={staggerItem(reducedMotion)}>
              <StatCard
                label={t("hr.overview_page.stats_onboarding_active", { defaultValue: "Onboarding Active" })}
                value={onboardingActive}
                icon={CheckCircle2}
                loading={loading}
              />
            </motion.div>
          </motion.div>

          {isEmpty ? (
            <EmptyStateCard
              title={t("hr.overview_page.no_openings_title", { defaultValue: "No openings yet" })}
              description={t("hr.overview_page.no_openings_description", {
                defaultValue:
                  "Create your first opening and upload resumes to start screening candidates.",
              })}
              icon={Users2}
              actions={
                <>
                  <GradientButton asChild>
                    <Link href="/hr/openings/new">
                      {t("hr.overview_page.create_opening", { defaultValue: "Create Opening" })}
                    </Link>
                  </GradientButton>
                  <Button
                    type="button"
                    variant="outline"
                    className="border-white/10 bg-white/[0.03] hover:bg-white/[0.06]"
                    onClick={() =>
                      toast(t("common.coming_soon", { defaultValue: "Coming soon" }), {
                        description: t("hr.overview_page.upload_resumes", { defaultValue: "Upload Resumes" }),
                      })
                    }
                  >
                    {t("hr.overview_page.upload_resumes", { defaultValue: "Upload Resumes" })}
                  </Button>
                </>
              }
            />
          ) : (
            <>
              <GlassCard className="p-5">
                <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                  <div>
                    <div className="text-sm font-semibold tracking-tight">
                      {t("hr.overview_page.insights_title", { defaultValue: "AI Insights" })}
                    </div>
                    <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                      <span className="inline-flex items-center gap-1">
                        <span className="h-2 w-2 rounded-full bg-emerald-300/80" />
                        {t("hr.overview_page.insights_actual", { defaultValue: "Actual" })}
                      </span>
                      <span className="inline-flex items-center gap-1">
                        <span className="h-2 w-2 rounded-full bg-fuchsia-300/80" />
                        {t("hr.overview_page.insights_ai_projected", { defaultValue: "AI Projected" })}
                      </span>
                    </div>
                  </div>
                  <GradientButton
                    className="md:self-start"
                    onClick={() =>
                      toast(t("common.coming_soon", { defaultValue: "Coming soon" }), {
                        description: t("hr.overview_page.insights_review_top", { defaultValue: "Review Top Matches" }),
                      })
                    }
                  >
                    {t("hr.overview_page.insights_review_top", { defaultValue: "Review Top Matches" })}
                  </GradientButton>
                </div>

                <div className="mt-4 text-sm text-muted-foreground">
                  {loading ? (
                    <div className="space-y-2">
                      <Skeleton className="h-4 w-5/6 bg-white/10" />
                      <Skeleton className="h-4 w-4/6 bg-white/10" />
                    </div>
                  ) : (
                    <p>
                      {t("hr.overview_page.insights_body", {
                        defaultValue:
                          "Throughput is trending up. Tighten the “Applied → Screened” SLA to 24h for high-volume openings to improve candidate response rates.",
                      })}
                    </p>
                  )}
                </div>
              </GlassCard>

              <GlassCard className="p-5">
                <div className="text-sm font-semibold tracking-tight">
                  {t("hr.overview_page.activity_title", { defaultValue: "Recent Activity" })}
                </div>
                <div className="mt-4 space-y-3">
                  {loading ? (
                    <>
                      {Array.from({ length: 3 }).map((_, i) => (
                        <div
                          key={i}
                          className="flex items-center justify-between gap-3 rounded-2xl bg-white/[0.02] p-3 ring-1 ring-white/5"
                        >
                          <div className="flex items-center gap-3">
                            <Skeleton className="h-9 w-9 rounded-xl bg-white/10" />
                            <div className="space-y-2">
                              <Skeleton className="h-3 w-60 bg-white/10" />
                              <Skeleton className="h-3 w-28 bg-white/10" />
                            </div>
                          </div>
                          <Skeleton className="h-3 w-14 bg-white/10" />
                        </div>
                      ))}
                    </>
                  ) : (
                    activity.map((a) => {
                      const Icon = a.icon;
                      return (
                        <div
                          key={a.id}
                          className="flex items-center justify-between gap-3 rounded-2xl bg-white/[0.02] p-3 ring-1 ring-white/5"
                        >
                          <div className="flex min-w-0 items-center gap-3">
                            <div className="relative h-9 w-9 shrink-0 rounded-xl bg-white/5 ring-1 ring-white/10">
                              <div className="pointer-events-none absolute inset-0 rounded-xl bg-[radial-gradient(16px_circle_at_30%_25%,rgba(168,85,247,0.32),transparent_60%)]" />
                              <Icon className="absolute left-1/2 top-1/2 h-4 w-4 -translate-x-1/2 -translate-y-1/2 text-foreground/80" />
                            </div>
                            <div className="min-w-0">
                              <div className="truncate text-sm font-medium">{a.text}</div>
                              <div className="truncate text-xs text-muted-foreground">{a.when}</div>
                            </div>
                          </div>
                          <div className="shrink-0 text-xs text-muted-foreground">{a.when}</div>
                        </div>
                      );
                    })
                  )}
                </div>
              </GlassCard>
            </>
          )}
        </div>

        <div className="space-y-6 lg:col-span-4">
          <PanelCard
            title={t("hr.overview_page.priority_tasks_title", { defaultValue: "Priority tasks" })}
            actionLabel={t("hr.overview_page.priority_tasks_action", { defaultValue: "See all" })}
            onAction={() =>
              toast(t("common.coming_soon", { defaultValue: "Coming soon" }), {
                description: t("hr.overview_page.priority_tasks_action_desc", {
                  defaultValue: "See all tasks",
                }),
              })
            }
            description={t("hr.overview_page.priority_tasks_description", {
              defaultValue: "Today’s high-signal actions.",
            })}
          >
            <div className="space-y-3">
              {[
                {
                  id: "followups",
                  title: t("hr.overview_page.task_followups_title", { defaultValue: "Follow-ups" }),
                  subtitle: t("hr.overview_page.task_followups_subtitle", { defaultValue: "Candidate outreach" }),
                  meta: "3/4",
                  icon: ClipboardList
                },
                {
                  id: "contract",
                  title: t("hr.overview_page.task_contract_title", { defaultValue: "Contract Review" }),
                  subtitle: t("hr.overview_page.task_contract_subtitle", { defaultValue: "Offer letter" }),
                  meta: "1/2",
                  icon: CheckCircle2
                },
                {
                  id: "interviews",
                  title: t("hr.overview_page.task_interviews_title", { defaultValue: "Interviews" }),
                  subtitle: t("hr.overview_page.task_interviews_subtitle", { defaultValue: "Scheduled today" }),
                  meta: "2",
                  icon: CalendarClock
                },
              ].map((it) => {
                const Icon = it.icon;
                return (
                  <div
                    key={it.id}
                    className="flex items-center justify-between gap-3 rounded-2xl bg-white/[0.02] p-3 ring-1 ring-white/5"
                  >
                    <div className="flex min-w-0 items-center gap-3">
                      <div className="relative h-9 w-9 shrink-0 rounded-xl bg-white/5 ring-1 ring-white/10">
                        <div className="pointer-events-none absolute inset-0 rounded-xl bg-[radial-gradient(16px_circle_at_30%_25%,rgba(168,85,247,0.32),transparent_60%)]" />
                        <Icon className="absolute left-1/2 top-1/2 h-4 w-4 -translate-x-1/2 -translate-y-1/2 text-foreground/80" />
                      </div>
                      <div className="min-w-0">
                        <div className="truncate text-sm font-medium">{it.title}</div>
                        <div className="truncate text-xs text-muted-foreground">{it.subtitle}</div>
                      </div>
                    </div>
                    <div className="shrink-0 text-xs text-muted-foreground tabular-nums">{it.meta}</div>
                  </div>
                );
              })}
            </div>
          </PanelCard>

          <GlassCard className="p-5">
            <div className="flex items-center gap-2 text-sm font-semibold tracking-tight">
              <Sparkles className="h-4 w-4 text-violet-200" />
              {t("hr.overview_page.assistant_title", { defaultValue: "Assistant" })}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              {t("hr.overview_page.assistant_description", {
                defaultValue: "Quick actions to accelerate your hiring loop (mock).",
              })}
            </div>

            <div className="mt-4 grid grid-cols-2 gap-3">
              {[
                { id: "summary", label: t("hr.overview_page.assistant_action_summary", { defaultValue: "Candidate Summary" }) },
                { id: "questions", label: t("hr.overview_page.assistant_action_questions", { defaultValue: "Interview Questions" }) },
                { id: "gaps", label: t("hr.overview_page.assistant_action_gaps", { defaultValue: "Find Skill Gaps" }) },
                { id: "offer", label: t("hr.overview_page.assistant_action_offer", { defaultValue: "Draft Offer Email" }) },
              ].map((a) => (
                <Button
                  key={a.id}
                  type="button"
                  variant="ghost"
                  onClick={() => toast("Coming soon", { description: a.label })}
                  className="h-auto flex-col items-start gap-1 rounded-2xl bg-white/[0.02] p-3 text-start ring-1 ring-white/5 hover:bg-white/[0.05] hover:text-foreground"
                  aria-label={a.label}
                >
                  <div className="text-sm font-medium">{a.label}</div>
                  <div className="text-xs text-muted-foreground">
                    {t("common.coming_soon", { defaultValue: "Coming soon" })}
                  </div>
                </Button>
              ))}
            </div>
          </GlassCard>
        </div>
      </div>
      )}
    </HrPageShell>
  );
}
