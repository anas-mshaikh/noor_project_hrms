"use client";

import * as React from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Filter, FolderOpen, Plus } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { HrPageShell } from "@/features/hr/components/layout/HrPageShell";
import { HrHeader } from "@/features/hr/components/layout/HrHeader";
import { GradientButton } from "@/features/hr/components/cards/GradientButton";
import { OpeningCard } from "@/features/hr/components/openings/OpeningCard";
import { EmptyStateCard } from "@/features/hr/components/cards/EmptyStateCard";
import { PanelCard } from "@/features/hr/components/cards/PanelCard";
import { TagChip } from "@/features/hr/components/candidates/TagChip";
import { useMockLoading } from "@/features/hr/hooks/useMockLoading";
import { useReducedMotion } from "@/features/hr/hooks/useReducedMotion";
import { staggerContainer, staggerItem } from "@/features/hr/lib/motion";
import { HR_OPENINGS, HR_RUNS } from "@/features/hr/mock/data";

type FilterKey = "ACTIVE" | "ARCHIVED" | "ALL";

export default function HROpeningsPage() {
  const reducedMotion = useReducedMotion();
  const { loading } = useMockLoading(600);
  const [filter, setFilter] = React.useState<FilterKey>("ACTIVE");

  const openings = HR_OPENINGS.filter((o) => (filter === "ALL" ? true : o.status === filter));
  const isEmpty = !loading && openings.length === 0;

  const topByVolume = HR_OPENINGS.slice()
    .filter((o) => o.status === "ACTIVE")
    .sort((a, b) => b.resumes_count - a.resumes_count)
    .slice(0, 5);

  const recentRuns = HR_RUNS.slice()
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
    .slice(0, 4);

  return (
    <HrPageShell>
      <HrHeader
        title="Openings"
        subtitle="Create openings, upload resumes, and run AI screening."
        chips={["Mock data", "Backend wiring later"]}
        actions={
          <>
            <GradientButton asChild>
              <Link href="/hr/openings/new">
                <Plus className="h-4 w-4" />
                Create Opening
              </Link>
            </GradientButton>
            <Button
              type="button"
              variant="outline"
              className="border-white/10 bg-white/[0.03] hover:bg-white/[0.06]"
              onClick={() => toast("Coming soon", { description: "Filters" })}
            >
              <Filter className="h-4 w-4" />
              Filters
            </Button>
          </>
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="space-y-5 lg:col-span-8">
          <div className="flex flex-wrap items-center gap-2">
            {(["ACTIVE", "ARCHIVED", "ALL"] as const).map((k) => (
              <button
                key={k}
                type="button"
                onClick={() => setFilter(k)}
                className={
                  k === filter
                    ? "rounded-full bg-white/[0.06] px-3 py-1 text-xs text-foreground ring-1 ring-white/15"
                    : "rounded-full bg-white/[0.03] px-3 py-1 text-xs text-muted-foreground ring-1 ring-white/10 hover:bg-white/[0.05]"
                }
                aria-label={`Filter ${k.toLowerCase()}`}
              >
                {k}
              </button>
            ))}
          </div>

          {isEmpty ? (
            <EmptyStateCard
              title="No openings found"
              description="Create an opening to start collecting resumes and screening candidates."
              icon={FolderOpen}
              actions={
                <GradientButton asChild>
                  <Link href="/hr/openings/new">Create Opening</Link>
                </GradientButton>
              }
            />
          ) : (
            <motion.div
              variants={staggerContainer(reducedMotion)}
              initial="hidden"
              animate="show"
              className="grid grid-cols-1 gap-4 md:grid-cols-2"
            >
              {openings.map((o) => (
                <motion.div key={o.id} variants={staggerItem(reducedMotion)}>
                  {loading ? (
                    <div className="rounded-3xl bg-white/[0.03] p-5 ring-1 ring-white/10">
                      <div className="h-4 w-44 rounded bg-white/10" />
                      <div className="mt-2 h-3 w-56 rounded bg-white/10" />
                      <div className="mt-4 flex gap-2">
                        <div className="h-7 w-20 rounded-full bg-white/10" />
                        <div className="h-7 w-24 rounded-full bg-white/10" />
                        <div className="h-7 w-28 rounded-full bg-white/10" />
                      </div>
                    </div>
                  ) : (
                    <OpeningCard opening={o} />
                  )}
                </motion.div>
              ))}
            </motion.div>
          )}
        </div>

        <div className="space-y-6 lg:col-span-4">
          <PanelCard title="Top openings by volume" description="Highest resume volume (mock).">
            <div className="space-y-3">
              {loading ? (
                Array.from({ length: 4 }).map((_, i) => (
                  <div
                    key={i}
                    className="rounded-2xl bg-white/[0.02] p-3 ring-1 ring-white/5"
                  >
                    <div className="h-3 w-40 rounded bg-white/10" />
                    <div className="mt-2 h-3 w-28 rounded bg-white/10" />
                  </div>
                ))
              ) : (
                topByVolume.map((o) => (
                  <Link
                    key={o.id}
                    href={`/hr/openings/${o.id}`}
                    className="block rounded-2xl bg-white/[0.02] p-3 ring-1 ring-white/5 hover:bg-white/[0.05]"
                  >
                    <div className="text-sm font-medium">{o.title}</div>
                    <div className="mt-1 flex flex-wrap gap-2 text-xs text-muted-foreground">
                      <TagChip className="bg-white/[0.03]">{o.resumes_count} resumes</TagChip>
                      <TagChip className="bg-white/[0.03]">{o.in_pipeline_count} pipeline</TagChip>
                    </div>
                  </Link>
                ))
              )}
            </div>
          </PanelCard>

          <PanelCard title="Recent runs" actionLabel="See runs" onAction={() => toast("Coming soon")}>
            <div className="space-y-3">
              {loading ? (
                Array.from({ length: 3 }).map((_, i) => (
                  <div
                    key={i}
                    className="rounded-2xl bg-white/[0.02] p-3 ring-1 ring-white/5"
                  >
                    <div className="h-3 w-52 rounded bg-white/10" />
                    <div className="mt-2 h-3 w-28 rounded bg-white/10" />
                  </div>
                ))
              ) : (
                recentRuns.map((r) => (
                  <Link
                    key={r.id}
                    href={`/hr/runs/${r.id}`}
                    className="block rounded-2xl bg-white/[0.02] p-3 ring-1 ring-white/5 hover:bg-white/[0.05]"
                  >
                    <div className="text-sm font-medium">{r.title}</div>
                    <div className="mt-1 text-xs text-muted-foreground">
                      {r.status} • {r.progress_done}/{r.progress_total}
                    </div>
                  </Link>
                ))
              )}
            </div>
          </PanelCard>
        </div>
      </div>
    </HrPageShell>
  );
}

