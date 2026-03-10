"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth";
import { parseUuidParam } from "@/lib/guards";
import { DocumentDetailCard } from "@/features/dms/components/DocumentDetailCard";
import { listMyDocuments, getMyDocument } from "@/features/dms/api/dms";
import { dmsKeys } from "@/features/dms/queryKeys";
import { myDocsHref } from "@/features/dms/routes";

import { DataTable } from "@/components/ds/DataTable";
import { EmptyState } from "@/components/ds/EmptyState";
import { ErrorState } from "@/components/ds/ErrorState";
import { FilterBar } from "@/components/ds/FilterBar";
import { PageHeader } from "@/components/ds/PageHeader";
import { StatusChip } from "@/components/ds/StatusChip";
import { ListRightPanelTemplate } from "@/components/ds/templates/ListRightPanelTemplate";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

function formatDate(value: string | null | undefined): string {
  if (!value) return "-";
  try {
    return new Date(value).toLocaleDateString();
  } catch {
    return value;
  }
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "-";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export default function MyDocumentsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const permissions = useAuth((s) => s.permissions);
  const granted = React.useMemo(() => new Set(permissions ?? []), [permissions]);
  const canReadDocs = granted.has("dms:document:read");
  const canReadFiles = granted.has("dms:file:read");

  const [type, setType] = React.useState("");
  const [status, setStatus] = React.useState("");
  const limit = 25;

  const docId = parseUuidParam(searchParams.get("docId"));

  const docsQ = useInfiniteQuery({
    queryKey: dmsKeys.myDocs({ status: status || null, type: type || null, limit }),
    enabled: canReadDocs,
    queryFn: ({ pageParam }) =>
      listMyDocuments({
        status: status || null,
        type: type || null,
        limit,
        cursor: (pageParam as string | null) ?? null,
      }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });

  const detailQ = useQuery({
    queryKey: dmsKeys.myDoc(docId),
    enabled: Boolean(docId && canReadDocs),
    queryFn: () => getMyDocument(docId as string),
  });

  const items = React.useMemo(() => docsQ.data?.pages.flatMap((page) => page.items) ?? [], [docsQ.data]);
  const selected = React.useMemo(() => items.find((item) => item.id === docId) ?? detailQ.data ?? null, [docId, items, detailQ.data]);

  React.useEffect(() => {
    if (!docId && items.length > 0) {
      router.replace(myDocsHref({ docId: items[0].id }));
    }
  }, [docId, items, router]);

  function setSelectedDoc(nextDocId: string | null) {
    router.push(myDocsHref({ docId: nextDocId }));
  }

  if (!canReadDocs) {
    return (
      <ErrorState
        title="Access denied"
        error={new Error("Your account does not have access to documents.")}
      />
    );
  }

  return (
    <ListRightPanelTemplate
      header={<PageHeader title="My Documents" subtitle="Your current employee documents." />}
      main={
        <DataTable
          toolbar={
            <FilterBar
              search={{
                value: type,
                onChange: setType,
                placeholder: "Filter by document type code...",
                disabled: docsQ.isLoading,
              }}
              chips={
                <div className="flex items-center gap-2">
                  <Label className="text-xs text-text-2">Status</Label>
                  <select
                    className="h-9 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
                    value={status}
                    onChange={(e) => setStatus(e.target.value)}
                  >
                    <option value="">All</option>
                    <option value="DRAFT">Draft</option>
                    <option value="SUBMITTED">Submitted</option>
                    <option value="VERIFIED">Verified</option>
                    <option value="REJECTED">Rejected</option>
                    <option value="EXPIRED">Expired</option>
                  </select>
                </div>
              }
              rightActions={
                docsQ.hasNextPage ? (
                  <Button type="button" variant="secondary" disabled={docsQ.isFetchingNextPage} onClick={() => void docsQ.fetchNextPage()}>
                    {docsQ.isFetchingNextPage ? "Loading..." : "Load more"}
                  </Button>
                ) : null
              }
              onClearAll={status || type ? () => {
                setStatus("");
                setType("");
              } : undefined}
              clearDisabled={docsQ.isLoading}
            />
          }
          isLoading={docsQ.isLoading}
          error={docsQ.error}
          onRetry={docsQ.refetch}
          isEmpty={!docsQ.isLoading && !docsQ.error && items.length === 0}
          emptyState={
            <EmptyState
              title="No documents"
              description="Your documents will appear here once HR uploads them."
              align="center"
            />
          }
          skeleton={{ rows: 6, cols: 4 }}
        >
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Type</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Expiry</TableHead>
                <TableHead>Created</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => (
                <TableRow key={item.id} className="cursor-pointer" onClick={() => setSelectedDoc(item.id)}>
                  <TableCell>
                    <div className="font-medium text-text-1">{item.document_type_name}</div>
                    <div className="mt-1 text-xs text-text-3">{item.document_type_code}</div>
                  </TableCell>
                  <TableCell>
                    <StatusChip status={item.status} />
                  </TableCell>
                  <TableCell className="text-text-2">{item.expires_at ? formatDate(item.expires_at) : "-"}</TableCell>
                  <TableCell className="text-text-2">{formatDateTime(item.created_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </DataTable>
      }
      right={
        detailQ.isError ? (
          <ErrorState
            title="Not found"
            error={new Error("This document does not exist or is not accessible.")}
            details={
              <Button asChild variant="secondary">
                <Link href="/dms/my-docs">Go to My Documents</Link>
              </Button>
            }
          />
        ) : selected ? (
          <DocumentDetailCard document={selected} canReadFiles={canReadFiles} />
        ) : (
          <EmptyState
            title="Select a document"
            description="Choose a document to view current metadata and download it."
          />
        )
      }
    />
  );
}
