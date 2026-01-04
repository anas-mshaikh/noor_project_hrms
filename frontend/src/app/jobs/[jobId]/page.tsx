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
      <div className="rounded border bg-white p-4">
        <h1 className="text-xl font-semibold">Job</h1>
        <div className="mt-2 text-sm text-red-600">Missing jobId in route.</div>
      </div>
    );
  }

  if (jobQ.isLoading) {
    return (
      <div className="rounded border bg-white p-4">
        <h1 className="text-xl font-semibold">Job</h1>
        <div className="mt-2 text-sm text-gray-600">Loading…</div>
      </div>
    );
  }

  if (jobQ.isError) {
    return (
      <div className="rounded border bg-white p-4">
        <h1 className="text-xl font-semibold">Job</h1>
        <div className="mt-2 text-sm text-red-600">{String(jobQ.error)}</div>
      </div>
    );
  }

  const job = jobQ.data!;
  const isTerminal = TERMINAL.has(job.status);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Job Status</h1>

      <section className="rounded border bg-white p-4">
        <div className="text-sm text-gray-600">
          job_id: <code className="text-xs">{jobId}</code>
        </div>

        <div className="mt-3 grid gap-2 text-sm">
          <div>
            <span className="font-medium">Status:</span>{" "}
            <span className="rounded bg-gray-100 px-2 py-1">{job.status}</span>
          </div>

          <div>
            <span className="font-medium">Progress:</span> {job.progress}%
          </div>

          <div className="h-2 w-full rounded bg-gray-200">
            <div
              className={`h-2 rounded ${
                job.status === "FAILED" ? "bg-red-600" : "bg-green-600"
              }`}
              style={{
                width: `${Math.min(
                  100,
                  Math.max(0, Number(job.progress) || 0)
                )}%`,
              }}
            />
          </div>

          {job.error && (
            <div className="mt-2 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              <div className="font-medium">Error</div>
              <pre className="mt-1 overflow-auto text-xs">{job.error}</pre>
            </div>
          )}

          <div className="mt-2 text-xs text-gray-500">
            created_at: {new Date(job.created_at).toLocaleString()}
            {job.started_at
              ? ` • started_at: ${new Date(job.started_at).toLocaleString()}`
              : ""}
            {job.finished_at
              ? ` • finished_at: ${new Date(job.finished_at).toLocaleString()}`
              : ""}
          </div>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <Link
            className="rounded border px-3 py-2 hover:bg-gray-50"
            href={`/reports/${jobId}`}
          >
            Open report
          </Link>

          <button
            className="rounded border px-3 py-2 hover:bg-gray-50 disabled:opacity-50"
            disabled={isTerminal || cancelM.isPending}
            onClick={() => cancelM.mutate()}
          >
            {cancelM.isPending ? "Canceling…" : "Cancel"}
          </button>

          <button
            className="rounded border px-3 py-2 hover:bg-gray-50 disabled:opacity-50"
            disabled={
              !(job.status === "FAILED" || job.status === "CANCELED") ||
              retryM.isPending
            }
            onClick={() => retryM.mutate()}
          >
            {retryM.isPending ? "Retrying…" : "Retry"}
          </button>

          <button
            className="rounded border px-3 py-2 hover:bg-gray-50"
            onClick={() => jobQ.refetch()}
          >
            Refresh now
          </button>
        </div>

        {(cancelM.isError || retryM.isError) && (
          <div className="mt-3 text-sm text-red-600">
            {String(cancelM.error ?? retryM.error)}
          </div>
        )}
      </section>

      <section className="rounded border bg-white p-4">
        <h2 className="text-sm font-medium">Debug (raw job JSON)</h2>
        <pre className="mt-2 overflow-auto rounded bg-gray-50 p-3 text-xs">
          {JSON.stringify(job, null, 2)}
        </pre>
      </section>
    </div>
  );
}
