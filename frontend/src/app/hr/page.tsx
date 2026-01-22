"use client";

/**
 * /hr
 *
 * HR Overview (Phase 1 UI-only):
 * - Premium "purple glass" look & feel
 * - Mock data + skeleton loading pattern
 * - Motion via framer-motion with reduced-motion support
 *
 * This page intentionally does not call the backend yet.
 * We'll wire real data in a later phase.
 */

import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  CalendarClock,
  CheckCircle2,
  ClipboardList,
  Users2,
  Zap,
} from "lucide-react";
import { toast } from "sonner";

import { GlassCard } from "@/components/hr/GlassCard";
import { GradientButton } from "@/components/hr/GradientButton";
import { RightRailPanel } from "@/components/hr/RightRailPanel";
import { StatCard } from "@/components/hr/StatCard";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  pageFade,
  staggerContainer,
  staggerItem,
  usePrefersReducedMotion,
} from "@/lib/motion";

type ActivityItem = {
  id: string;
  text: string;
  when: string;
  icon: React.ComponentType<{ className?: string }>;
};

export default function HROverviewPage() {
  const reducedMotion = usePrefersReducedMotion();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const t = window.setTimeout(() => setLoading(false), 600);
    return () => window.clearTimeout(t);
  }, []);

  const kpis = useMemo(
    () => ({
      activeOpenings: 3,
      screened7d: 128,
      inPipeline: 22,
    }),
    []
  );

  // Empty state guardrail (for when real API wiring returns no rows).
  // With Phase 1 mock data this will be false, but the UI path is ready.
  const isEmpty = !loading && kpis.activeOpenings === 0;

  const priorityItems = useMemo(
    () => [
      {
        id: "followups",
        title: "Follow-ups",
        subtitle: "Candidate outreach",
        meta: "3/4",
        icon: ClipboardList,
      },
      {
        id: "contract",
        title: "Contract Review",
        subtitle: "Offer letter",
        meta: "1/2",
        icon: CheckCircle2,
      },
      {
        id: "interviews",
        title: "Interviews",
        subtitle: "Scheduled today",
        meta: "2",
        icon: CalendarClock,
      },
    ],
    []
  );

  const activity = useMemo<ActivityItem[]>(
    () => [
      {
        id: "a1",
        text: "Screening run completed — Cashier",
        when: "2m ago",
        icon: Zap,
      },
      {
        id: "a2",
        text: "12 candidates moved to Interview",
        when: "1h ago",
        icon: Users2,
      },
      {
        id: "a3",
        text: "Offer sent — Sales Associate",
        when: "Yesterday",
        icon: CheckCircle2,
      },
    ],
    []
  );

  return (
    <motion.div
      initial="hidden"
      animate="show"
      variants={pageFade(reducedMotion)}
      className="relative overflow-hidden rounded-3xl border border-white/10 bg-[radial-gradient(1200px_circle_at_10%_0%,rgba(168,85,247,0.25),transparent_55%),radial-gradient(900px_circle_at_85%_10%,rgba(236,72,153,0.18),transparent_55%),linear-gradient(to_bottom,rgba(2,6,23,1),rgba(15,23,42,0.96),rgba(2,6,23,1))] p-6 text-white md:p-8"
    >
      {/* Subtle "noise" overlay (very low opacity). */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-[0.045] mix-blend-overlay"
        style={{
          backgroundImage:
            "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.8' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='140' height='140' filter='url(%23n)' opacity='.35'/%3E%3C/svg%3E\")",
        }}
      />

      <div className="relative">
        {/* Header */}
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">
              HR Overview
            </h1>
            <p className="mt-1 text-sm text-white/70">
              AI-powered hiring → pipeline → onboarding.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <GradientButton
              onClick={() =>
                toast("Coming soon", { description: "Run Screening" })
              }
            >
              Run Screening
            </GradientButton>
            <Button
              type="button"
              variant="secondary"
              className="border border-white/10 bg-white/5 text-white hover:bg-white/10"
              onClick={() =>
                toast("Coming soon", { description: "Create Opening" })
              }
            >
              Create Opening
            </Button>
            <Button
              type="button"
              variant="secondary"
              className="border border-white/10 bg-white/5 text-white hover:bg-white/10"
              onClick={() =>
                toast("Coming soon", { description: "Upload Resumes" })
              }
            >
              Upload Resumes
            </Button>
          </div>
        </div>

        {/* Content grid */}
        <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-12">
          {/* Main (8 cols) */}
          <div className="space-y-6 lg:col-span-8">
            {/* KPI row */}
            <motion.div
              variants={staggerContainer(reducedMotion)}
              className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3"
            >
              <motion.div variants={staggerItem(reducedMotion)}>
                <StatCard
                  label="Active Openings"
                  value={kpis.activeOpenings}
                  icon={ClipboardList}
                  loading={loading}
                />
              </motion.div>
              <motion.div variants={staggerItem(reducedMotion)}>
                <StatCard
                  label="Candidates Screened (7d)"
                  value={kpis.screened7d}
                  icon={Zap}
                  loading={loading}
                />
              </motion.div>
              <motion.div variants={staggerItem(reducedMotion)}>
                <StatCard
                  label="In Pipeline"
                  value={kpis.inPipeline}
                  icon={Users2}
                  loading={loading}
                />
              </motion.div>
            </motion.div>

            {isEmpty ? (
              <GlassCard className="p-6">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="text-sm font-semibold tracking-tight">
                      No openings yet
                    </div>
                    <p className="mt-1 text-sm text-white/70">
                      Create your first opening and upload resumes to start
                      screening candidates.
                    </p>
                  </div>
                  <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-white/5 ring-1 ring-white/10">
                    <Users2 className="h-5 w-5 text-white/80" />
                  </div>
                </div>
                <div className="mt-4 flex flex-wrap items-center gap-2">
                  <GradientButton
                    onClick={() =>
                      toast("Coming soon", { description: "Create Opening" })
                    }
                  >
                    Create Opening
                  </GradientButton>
                  <Button
                    type="button"
                    variant="secondary"
                    className="border border-white/10 bg-white/5 text-white hover:bg-white/10"
                    onClick={() =>
                      toast("Coming soon", { description: "Upload Resumes" })
                    }
                  >
                    Upload Resumes
                  </Button>
                </div>
              </GlassCard>
            ) : (
              <>
                {/* AI Insights */}
                <GlassCard className="p-5">
                  <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                    <div>
                      <div className="text-sm font-semibold tracking-tight">
                        AI Insights
                      </div>
                      <div className="mt-1 flex items-center gap-2 text-xs text-white/60">
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
                      onClick={() =>
                        toast("Coming soon", {
                          description: "Review Top Matches",
                        })
                      }
                    >
                      Review Top Matches
                    </GradientButton>
                  </div>

                  <div className="mt-4 text-sm text-white/70">
                    {loading ? (
                      <div className="space-y-2">
                        <Skeleton className="h-4 w-5/6 bg-white/10" />
                        <Skeleton className="h-4 w-4/6 bg-white/10" />
                      </div>
                    ) : (
                      <p>
                        Your screening throughput is trending up. Consider
                        tightening the “Applied → Screened” SLA to 24h for
                        high-volume openings to improve candidate response rates.
                      </p>
                    )}
                  </div>
                </GlassCard>

                {/* Recent Activity */}
                <GlassCard className="p-5">
                  <div className="text-sm font-semibold tracking-tight">
                    Recent Activity
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
                                <Icon className="absolute left-1/2 top-1/2 h-4 w-4 -translate-x-1/2 -translate-y-1/2 text-white/80" />
                              </div>
                              <div className="min-w-0">
                                <div className="truncate text-sm font-medium">
                                  {a.text}
                                </div>
                                <div className="truncate text-xs text-white/60">
                                  {a.when}
                                </div>
                              </div>
                            </div>
                            <div className="shrink-0 text-xs text-white/60">
                              {a.when}
                            </div>
                          </div>
                        );
                      })
                    )}
                  </div>
                </GlassCard>
              </>
            )}
          </div>

          {/* Right rail (4 cols) */}
          <div className="space-y-6 lg:col-span-4">
            <RightRailPanel
              title="Priority tasks"
              actionLabel="See all"
              onAction={() =>
                toast("Coming soon", { description: "See all tasks" })
              }
              items={isEmpty ? [] : priorityItems}
              loading={loading}
            />

            <GlassCard className="p-5">
              <div className="text-sm font-semibold tracking-tight">Assistant</div>
              <div className="mt-1 text-xs text-white/60">
                Quick actions to accelerate your hiring loop.
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
                    onClick={() =>
                      toast("Coming soon", { description: a.label })
                    }
                    className="h-auto flex-col items-start gap-1 rounded-2xl bg-white/[0.02] p-3 text-left ring-1 ring-white/5 hover:bg-white/[0.05] hover:text-white"
                    aria-label={a.label}
                  >
                    <div className="text-sm font-medium">{a.label}</div>
                    <div className="text-xs text-white/60">Coming soon</div>
                  </Button>
                ))}
              </div>
            </GlassCard>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
