"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth";
import { parseUuidParam } from "@/lib/guards";
import { getMyDocument } from "@/features/dms/api/dms";
import { dmsKeys } from "@/features/dms/queryKeys";
import { employeeDocsHref, myDocsHref } from "@/features/dms/routes";

import { DSCard } from "@/components/ds/DSCard";
import { EmptyState } from "@/components/ds/EmptyState";
import { ErrorState } from "@/components/ds/ErrorState";
import { PageHeader } from "@/components/ds/PageHeader";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

export default function DmsDocumentCompatibilityPage({
  params,
}: {
  params: { docId?: string };
}) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const permissions = useAuth((s) => s.permissions);
  const granted = React.useMemo(() => new Set(permissions ?? []), [permissions]);
  const canReadDocs = granted.has("dms:document:read");
  const canOpenHrDocs = granted.has("hr:employee:read") || granted.has("dms:document:write") || granted.has("dms:document:verify");

  const docId = parseUuidParam(params.docId);
  const employeeId = parseUuidParam(searchParams.get("employeeId"));
  const employeeIdRaw = searchParams.get("employeeId");

  React.useEffect(() => {
    if (!docId) return;
    if (!employeeId) return;
    router.replace(employeeDocsHref({ employeeId, docId }));
  }, [docId, employeeId, router]);

  const myDocQ = useQuery({
    queryKey: dmsKeys.myDoc(docId),
    enabled: Boolean(docId && !employeeId && canReadDocs),
    queryFn: () => getMyDocument(docId as string),
    retry: false,
  });

  React.useEffect(() => {
    if (!docId || employeeId) return;
    if (!myDocQ.data) return;
    router.replace(myDocsHref({ docId }));
  }, [docId, employeeId, myDocQ.data, router]);

  if (!params.docId) {
    return (
      <ErrorState
        title="Missing document id"
        error={new Error("Open this page from a document link.")}
      />
    );
  }

  if (!docId) {
    return (
      <ErrorState
        title="Invalid document id"
        error={new Error(`Got: ${params.docId}`)}
      />
    );
  }

  if (employeeIdRaw && !employeeId) {
    return (
      <ErrorState
        title="Invalid employee context"
        error={new Error(`Got: ${employeeIdRaw}`)}
      />
    );
  }

  if (employeeId || myDocQ.isLoading) {
    return (
      <div className="space-y-6">
        <PageHeader title="Open document" subtitle="Resolving the best document view for this link." />
        <DSCard surface="card" className="space-y-3 p-[var(--ds-space-20)]">
          <Skeleton className="h-6 w-56" />
          <Skeleton className="h-4 w-72" />
          <Skeleton className="h-24 w-full" />
        </DSCard>
      </div>
    );
  }

  const recoveryActions = (
    <div className="flex flex-wrap gap-2">
      {canReadDocs ? (
        <Button asChild variant="secondary">
          <Link href={myDocsHref()}>Go to My Documents</Link>
        </Button>
      ) : null}
      {canOpenHrDocs ? (
        <Button asChild variant="outline">
          <Link href={employeeDocsHref()}>Go to Employee Documents</Link>
        </Button>
      ) : null}
    </div>
  );

  if (myDocQ.isError) {
    return (
      <ErrorState
        title="We could not open this document directly"
        error={myDocQ.error}
        details={
          <div className="space-y-3">
            <div className="text-sm text-text-2">Document ID: {docId}</div>
            {recoveryActions}
          </div>
        }
      />
    );
  }

  return (
    <EmptyState
      title="We could not open this document directly"
      description="Use My Documents or Employee Documents to continue."
      primaryAction={recoveryActions}
    />
  );
}
