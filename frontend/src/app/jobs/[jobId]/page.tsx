"use client";

/**
 * /jobs/[jobId]
 *
 * Purpose:
 * - Poll job status so the manager can see progress
 * - Cancel / Retry
 * - Link to report once DONE
 *
 * Backend endpoints used:
 * - GET  /api/v1/jobs/{job_id}
 * - POST /api/v1/jobs/{job_id}/cancel
 * - POST /api/v1/jobs/{job_id}/retry
 */

import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";

import { apiJson } from "@/lib/api";
import type { JobReadResponse } from "@/lib/types";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

type JobActionResponse = {
  job_id: string;
  status: string;
  enqueued?: boolean;
  queue_error?: string | null;
};

const TERMINAL = new Set(["DONE", "FAILED", "CANCELED"]);

// function paramToString(v: string | string[] | undefined): string | undefined {
//   if (!v) return undefined;
//   return Array.isArray(v) ? v[0] : v;
// }

export default function JobPage() {
  const params = useParams<{ jobId: string }>();
  const jobId = Array.isArray(params?.jobId) ? params.jobId[0] : params?.jobId;

  const jobQ = useQuery({
    queryKey: ["job", jobId],
    enabled: Boolean(jobId),
    queryFn: () => {
      if (!jobId) throw new Error("Missing jobId");
      return apiJson<JobReadResponse>(`/api/v1/jobs/${jobId}`);
    },
    refetchInterval: (query) => {
      const data = query.state.data as JobReadResponse | undefined;
      const status = data?.status;
      return status && TERMINAL.has(status) ? false : 2000;
    },
  });

  const cancelM = useMutation({
    mutationFn: () => {
      if (!jobId) throw new Error("Missing jobId");
      return apiJson<JobActionResponse>(`/api/v1/jobs/${jobId}/cancel`, {
        method: "POST",
      });
    },
    onSuccess: () => jobQ.refetch(),
  });

  const retryM = useMutation({
    mutationFn: () => {
      if (!jobId) throw new Error("Missing jobId");
      return apiJson<JobActionResponse>(`/api/v1/jobs/${jobId}/retry`, {
        method: "POST",
      });
    },
    onSuccess: () => jobQ.refetch(),
  });

  if (!jobId) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Job</CardTitle>
          <CardDescription className="text-destructive">
            Missing jobId in route.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  if (jobQ.isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Job</CardTitle>
          <CardDescription>Loading…</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  if (jobQ.isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Job</CardTitle>
          <CardDescription className="text-destructive">
            {String(jobQ.error)}
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const job = jobQ.data!;
  const isTerminal = TERMINAL.has(job.status);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Job Status</h1>
          <div className="mt-1 text-sm text-muted-foreground">
            job_id: <code className="text-xs">{jobId}</code>
          </div>
        </div>

        <Button asChild variant="outline">
          <Link href={`/reports/${jobId}`}>Open report</Link>
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Progress</CardTitle>
          <CardDescription>
            {job.started_at ? "Processing…" : "Queued…"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium">Status:</span>
              <Badge
                variant={job.status === "FAILED" ? "destructive" : "secondary"}
              >
                {job.status}
              </Badge>
              <span className="ml-auto tabular-nums text-muted-foreground">
                {job.progress}%
              </span>
            </div>

            <div className="h-2 w-full overflow-hidden rounded bg-muted">
              <div
                className={
                  job.status === "FAILED" ? "h-2 bg-destructive" : "h-2 bg-primary"
                }
                style={{
                  width: `${Math.min(
                    100,
                    Math.max(0, Number(job.progress) || 0)
                  )}%`,
                }}
              />
            </div>

            {job.error && (
              <div className="rounded-lg border border-destructive/20 bg-destructive/10 p-3 text-sm">
                <div className="font-medium text-destructive">Error</div>
                <pre className="mt-2 overflow-auto text-xs text-foreground">
                  {job.error}
                </pre>
              </div>
            )}

            <div className="text-xs text-muted-foreground">
              created_at: {new Date(job.created_at).toLocaleString()}
              {job.started_at
                ? ` • started_at: ${new Date(job.started_at).toLocaleString()}`
                : ""}
              {job.finished_at
                ? ` • finished_at: ${new Date(job.finished_at).toLocaleString()}`
                : ""}
            </div>

            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="outline"
                disabled={isTerminal || cancelM.isPending}
                onClick={() => cancelM.mutate()}
              >
                {cancelM.isPending ? "Canceling…" : "Cancel"}
              </Button>

              <Button
                type="button"
                variant="outline"
                disabled={
                  !(job.status === "FAILED" || job.status === "CANCELED") ||
                  retryM.isPending
                }
                onClick={() => retryM.mutate()}
              >
                {retryM.isPending ? "Retrying…" : "Retry"}
              </Button>

              <Button type="button" variant="outline" onClick={() => jobQ.refetch()}>
                Refresh now
              </Button>
            </div>

            {(cancelM.isError || retryM.isError) && (
              <div className="text-sm text-destructive">
                {String(cancelM.error ?? retryM.error)}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Debug</CardTitle>
          <CardDescription>Raw job JSON (useful while iterating).</CardDescription>
        </CardHeader>
        <CardContent>
          <pre className="overflow-auto rounded-lg bg-muted/30 p-3 text-xs">
            {JSON.stringify(job, null, 2)}
          </pre>
        </CardContent>
      </Card>
    </div>
  );
}
