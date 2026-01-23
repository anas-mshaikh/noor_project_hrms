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
import { HR_OPENINGS, HR_ONBOARDING, HR_PIPELINE_CARDS } from "@/features/hr/mock/data";

type ActivityItem = {
  id: string;
  text: string;
  when: string;
  icon: React.ComponentType<{ className?: string }>;
};

export default function HROverviewPage() {
  const reducedMotion = useReducedMotion();
  const { loading } = useMockLoading(600);

  const activeOpenings = HR_OPENINGS.filter((o) => o.status === "ACTIVE").length;
  const inPipeline = HR_PIPELINE_CARDS.filter((c) => c.stage !== "rejected").length;
  const onboardingActive = HR_ONBOARDING.length;
  const screened7d = 128;

  const topOpening = HR_OPENINGS.slice()
    .filter((o) => o.status === "ACTIVE")
    .sort((a, b) => b.resumes_count - a.resumes_count)[0];

  const isEmpty = !loading && activeOpenings === 0;

  const chips = [
    topOpening ? `Top opening: ${topOpening.title}` : null,
    "Last run: Cashier (DONE)",
  ].filter(Boolean) as string[];

  const activity: ActivityItem[] = [
    { id: "a1", text: "Screening run completed — Cashier", when: "2m ago", icon: Zap },
    { id: "a2", text: "12 candidates moved to Interview", when: "1h ago", icon: Users2 },
    { id: "a3", text: "Offer sent — Sales Associate", when: "Yesterday", icon: CheckCircle2 },
  ];

  return (
    <HrPageShell>
      <HrHeader
        title="HR Overview"
        subtitle="AI-powered hiring → pipeline → onboarding."
        chips={chips}
        actions={
          <>
            <GradientButton onClick={() => toast("Coming soon", { description: "Run Screening" })}>
              Run Screening
            </GradientButton>
            <Button asChild variant="outline" className="border-white/10 bg-white/[0.03] hover:bg-white/[0.06]">
              <Link href="/hr/openings/new">Create Opening</Link>
            </Button>
            <Button
              type="button"
              variant="outline"
              className="border-white/10 bg-white/[0.03] hover:bg-white/[0.06]"
              onClick={() => toast("Coming soon", { description: "Upload Resumes" })}
            >
              Upload Resumes
            </Button>
          </>
        }
      />

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
                label="Active Openings"
                value={activeOpenings}
                icon={ClipboardList}
                loading={loading}
              />
            </motion.div>
            <motion.div variants={staggerItem(reducedMotion)}>
              <StatCard
                label="Candidates Screened (7d)"
                value={screened7d}
                icon={Zap}
                loading={loading}
              />
            </motion.div>
            <motion.div variants={staggerItem(reducedMotion)}>
              <StatCard label="In Pipeline" value={inPipeline} icon={Users2} loading={loading} />
            </motion.div>
            <motion.div variants={staggerItem(reducedMotion)}>
              <StatCard
                label="Onboarding Active"
                value={onboardingActive}
                icon={CheckCircle2}
                loading={loading}
              />
            </motion.div>
          </motion.div>

          {isEmpty ? (
            <EmptyStateCard
              title="No openings yet"
              description="Create your first opening and upload resumes to start screening candidates."
              icon={Users2}
              actions={
                <>
                  <GradientButton asChild>
                    <Link href="/hr/openings/new">Create Opening</Link>
                  </GradientButton>
                  <Button
                    type="button"
                    variant="outline"
                    className="border-white/10 bg-white/[0.03] hover:bg-white/[0.06]"
                    onClick={() => toast("Coming soon", { description: "Upload Resumes" })}
                  >
                    Upload Resumes
                  </Button>
                </>
              }
            />
          ) : (
            <>
              <GlassCard className="p-5">
                <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                  <div>
                    <div className="text-sm font-semibold tracking-tight">AI Insights</div>
                    <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                      <span className="inline-flex items-center gap-1">
                        <span className="h-2 w-2 rounded-full bg-emerald-300/80" />
                        Actual
                      </span>
                      <span className="inline-flex items-center gap-1">
                        <span className="h-2 w-2 rounded-full bg-fuchsia-300/80" />
                        AI Projected
                      </span>
                    </div>
                  </div>
                  <GradientButton
                    className="md:self-start"
                    onClick={() => toast("Coming soon", { description: "Review Top Matches" })}
                  >
                    Review Top Matches
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
                      Throughput is trending up. Tighten the “Applied → Screened” SLA to 24h for high-volume openings to
                      improve candidate response rates.
                    </p>
                  )}
                </div>
              </GlassCard>

              <GlassCard className="p-5">
                <div className="text-sm font-semibold tracking-tight">Recent Activity</div>
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
            title="Priority tasks"
            actionLabel="See all"
            onAction={() => toast("Coming soon", { description: "See all tasks" })}
            description="Today’s high-signal actions."
          >
            <div className="space-y-3">
              {[
                { id: "followups", title: "Follow-ups", subtitle: "Candidate outreach", meta: "3/4", icon: ClipboardList },
                { id: "contract", title: "Contract Review", subtitle: "Offer letter", meta: "1/2", icon: CheckCircle2 },
                { id: "interviews", title: "Interviews", subtitle: "Scheduled today", meta: "2", icon: CalendarClock },
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
              Assistant
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              Quick actions to accelerate your hiring loop (mock).
            </div>

            <div className="mt-4 grid grid-cols-2 gap-3">
              {[
                { id: "summary", label: "Candidate Summary" },
                { id: "questions", label: "Interview Questions" },
                { id: "gaps", label: "Find Skill Gaps" },
                { id: "offer", label: "Draft Offer Email" },
              ].map((a) => (
                <Button
                  key={a.id}
                  type="button"
                  variant="ghost"
                  onClick={() => toast("Coming soon", { description: a.label })}
                  className="h-auto flex-col items-start gap-1 rounded-2xl bg-white/[0.02] p-3 text-left ring-1 ring-white/5 hover:bg-white/[0.05] hover:text-foreground"
                  aria-label={a.label}
                >
                  <div className="text-sm font-medium">{a.label}</div>
                  <div className="text-xs text-muted-foreground">Coming soon</div>
                </Button>
              ))}
            </div>
          </GlassCard>
        </div>
      </div>
    </HrPageShell>
  );
}
