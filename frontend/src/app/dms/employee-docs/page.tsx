"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth";
import { parseUuidParam } from "@/lib/guards";
import { useSelection } from "@/lib/selection";
import { toastApiError } from "@/lib/toastApiError";
import { cn } from "@/lib/utils";
import type { DmsEmployeeDocumentCreateIn, UUID } from "@/lib/types";
import {
  addDocumentVersion,
  createEmployeeDocument,
  listDocumentTypes,
  listEmployeeDocuments,
  requestDocumentVerification,
} from "@/features/dms/api/dms";
import { uploadFile } from "@/features/dms/api/files";
import { DocumentDetailCard } from "@/features/dms/components/DocumentDetailCard";
import { employeeDocsHref } from "@/features/dms/routes";
import { dmsKeys } from "@/features/dms/queryKeys";
import { getEmployee, listEmployees } from "@/features/hr-core/api/hrCore";
import { hrCoreKeys } from "@/features/hr-core/queryKeys";

import { DataTable } from "@/components/ds/DataTable";
import { DSCard } from "@/components/ds/DSCard";
import { EmptyState } from "@/components/ds/EmptyState";
import { ErrorState } from "@/components/ds/ErrorState";
import { FilterBar } from "@/components/ds/FilterBar";
import { PageHeader } from "@/components/ds/PageHeader";
import { StatusChip } from "@/components/ds/StatusChip";
import { ListRightPanelTemplate } from "@/components/ds/templates/ListRightPanelTemplate";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
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

export default function EmployeeDocsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const qc = useQueryClient();

  const permissions = useAuth((s) => s.permissions);
  const granted = React.useMemo(() => new Set(permissions ?? []), [permissions]);
  const canReadDocs = granted.has("dms:document:read");
  const canWriteDocs = granted.has("dms:document:write");
  const canVerifyDocs = granted.has("dms:document:verify");
  const canReadFiles = granted.has("dms:file:read");
  const canWriteFiles = granted.has("dms:file:write");

  const companyId = useSelection((s) => s.companyId);
  const companyUuid = parseUuidParam(companyId);

  const employeeId = parseUuidParam(searchParams.get("employeeId"));
  const docId = parseUuidParam(searchParams.get("docId"));

  const [employeeSearch, setEmployeeSearch] = React.useState("");
  const [status, setStatus] = React.useState("");
  const [type, setType] = React.useState("");
  const limit = 25;

  const employeePickerQ = useQuery({
    queryKey: hrCoreKeys.employees({
      companyId: companyUuid,
      q: employeeSearch.trim() ? employeeSearch.trim() : null,
      status: null,
      branchId: null,
      orgUnitId: null,
      limit: 8,
      offset: 0,
    }),
    enabled: Boolean(companyUuid && canReadDocs),
    queryFn: () =>
      listEmployees({
        companyId: companyUuid,
        q: employeeSearch.trim() ? employeeSearch.trim() : null,
        limit: 8,
        offset: 0,
      }),
  });

  const employeeQ = useQuery({
    queryKey: hrCoreKeys.employee({ companyId: companyUuid, employeeId }),
    enabled: Boolean(companyUuid && employeeId && canReadDocs),
    queryFn: () => getEmployee({ companyId: companyUuid, employeeId: employeeId as UUID }),
  });

  const documentTypesQ = useQuery({
    queryKey: dmsKeys.documentTypes(),
    enabled: canReadDocs,
    queryFn: () => listDocumentTypes(),
  });

  const docsQ = useInfiniteQuery({
    queryKey: dmsKeys.employeeDocs({
      employeeId,
      status: status || null,
      type: type || null,
      limit,
    }),
    enabled: Boolean(employeeId && canReadDocs),
    queryFn: ({ pageParam }) =>
      listEmployeeDocuments({
        employeeId: employeeId as UUID,
        status: status || null,
        type: type || null,
        limit,
        cursor: (pageParam as string | null) ?? null,
      }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });

  const items = React.useMemo(() => docsQ.data?.pages.flatMap((page) => page.items) ?? [], [docsQ.data]);
  const selected = React.useMemo(() => items.find((item) => item.id === docId) ?? null, [docId, items]);

  React.useEffect(() => {
    if (!employeeId || docId || items.length === 0) return;
    router.replace(employeeDocsHref({ employeeId, docId: items[0].id }));
  }, [docId, employeeId, items, router]);

  function setEmployee(nextEmployeeId: UUID) {
    router.push(employeeDocsHref({ employeeId: nextEmployeeId }));
  }

  function setSelectedDoc(nextDocId: UUID | null) {
    if (!employeeId) return;
    router.push(employeeDocsHref({ employeeId, docId: nextDocId }));
  }

  const selectClassName = cn(
    "h-9 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
    "disabled:cursor-not-allowed disabled:opacity-50",
  );

  const [uploadOpen, setUploadOpen] = React.useState(false);
  const [uploadTypeCode, setUploadTypeCode] = React.useState("");
  const [uploadExpiry, setUploadExpiry] = React.useState("");
  const [uploadNotes, setUploadNotes] = React.useState("");
  const [uploadFileValue, setUploadFileValue] = React.useState<File | null>(null);
  const uploadInputRef = React.useRef<HTMLInputElement | null>(null);

  const uploadM = useMutation({
    mutationFn: async () => {
      if (!employeeId) throw new Error("Select an employee first.");
      if (!uploadTypeCode.trim()) throw new Error("Document type is required.");
      if (!uploadFileValue) throw new Error("File is required.");
      const file = await uploadFile(uploadFileValue);
      const payload: DmsEmployeeDocumentCreateIn = {
        document_type_code: uploadTypeCode.trim(),
        file_id: file.id,
        expires_at: uploadExpiry || null,
        notes: uploadNotes.trim() ? uploadNotes.trim() : null,
      };
      return createEmployeeDocument(employeeId, payload);
    },
    onSuccess: async (doc) => {
      setUploadOpen(false);
      setUploadTypeCode("");
      setUploadExpiry("");
      setUploadNotes("");
      setUploadFileValue(null);
      if (uploadInputRef.current) uploadInputRef.current.value = "";
      await qc.invalidateQueries({ queryKey: ["dms", "employee-docs"] });
      toast.success("Document uploaded");
      setSelectedDoc(doc.id);
    },
    onError: (err) => toastApiError(err),
  });

  const [replaceOpen, setReplaceOpen] = React.useState(false);
  const [replaceNotes, setReplaceNotes] = React.useState("");
  const [replaceFileValue, setReplaceFileValue] = React.useState<File | null>(null);
  const replaceInputRef = React.useRef<HTMLInputElement | null>(null);

  const replaceM = useMutation({
    mutationFn: async () => {
      if (!selected) throw new Error("Select a document first.");
      if (!replaceFileValue) throw new Error("File is required.");
      const file = await uploadFile(replaceFileValue);
      return addDocumentVersion(selected.id, {
        file_id: file.id,
        notes: replaceNotes.trim() ? replaceNotes.trim() : null,
      });
    },
    onSuccess: async (doc) => {
      setReplaceOpen(false);
      setReplaceNotes("");
      setReplaceFileValue(null);
      if (replaceInputRef.current) replaceInputRef.current.value = "";
      await qc.invalidateQueries({ queryKey: ["dms", "employee-docs"] });
      toast.success("Document replaced");
      setSelectedDoc(doc.id);
    },
    onError: (err) => toastApiError(err),
  });

  const verifyM = useMutation({
    mutationFn: async () => {
      if (!selected) throw new Error("Select a document first.");
      return requestDocumentVerification(selected.id);
    },
    onSuccess: async (res) => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["dms", "employee-docs"] }),
        qc.invalidateQueries({ queryKey: ["workflow", "outbox"] }),
      ]);
      toast.success("Verification request created");
      router.push(`/workflow/requests/${res.workflow_request_id}`);
    },
    onError: (err) => toastApiError(err),
  });

  if (!companyUuid) {
    return (
      <EmptyState
        title="Select a company"
        description="Employee documents are company-scoped. Select a company from the scope picker to continue."
        primaryAction={
          <Button asChild variant="secondary">
            <Link href="/scope">Go to scope</Link>
          </Button>
        }
      />
    );
  }

  if (!canReadDocs) {
    return (
      <ErrorState
        title="Access denied"
        error={new Error("Your account does not have access to employee documents.")}
      />
    );
  }

  const pickerItems = employeePickerQ.data?.items ?? [];

  if (!employeeId) {
    return (
      <div className="space-y-6">
        <PageHeader title="Employee Docs" subtitle="Select an employee to view documents." />
        <DataTable
          toolbar={
            <FilterBar
              search={{
                value: employeeSearch,
                onChange: setEmployeeSearch,
                placeholder: "Search employees by code or name...",
                disabled: employeePickerQ.isLoading,
              }}
              onClearAll={employeeSearch ? () => setEmployeeSearch("") : undefined}
              clearDisabled={employeePickerQ.isLoading}
            />
          }
          isLoading={employeePickerQ.isLoading}
          error={employeePickerQ.error}
          onRetry={employeePickerQ.refetch}
          isEmpty={!employeePickerQ.isLoading && !employeePickerQ.error && pickerItems.length === 0}
          emptyState={
            <EmptyState
              title="Select an employee"
              description="Choose an employee to open the document library."
              align="center"
            />
          }
          skeleton={{ rows: 6, cols: 3 }}
        >
          <div className="space-y-2">
            {pickerItems.map((employee) => (
              <button
                key={employee.employee_id}
                type="button"
                className="flex w-full items-center justify-between rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 px-4 py-3 text-left hover:bg-surface-2"
                onClick={() => setEmployee(employee.employee_id)}
              >
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium text-text-1">{employee.full_name}</div>
                  <div className="mt-1 text-xs text-text-2">{employee.employee_code}</div>
                </div>
                <StatusChip status={employee.status} />
              </button>
            ))}
          </div>
        </DataTable>
      </div>
    );
  }

  return (
    <ListRightPanelTemplate
      header={
        <PageHeader
          title="Employee Docs"
          subtitle={
            employeeQ.data
              ? `${employeeQ.data.person.first_name} ${employeeQ.data.person.last_name}`.trim()
              : "Employee document library"
          }
          actions={
            <div className="flex flex-wrap gap-2">
              <Button asChild type="button" variant="secondary">
                <Link href="/hr/employees">Employees</Link>
              </Button>
              <Sheet open={uploadOpen} onOpenChange={setUploadOpen}>
                <SheetTrigger asChild>
                  <Button type="button" disabled={!canWriteDocs || !canWriteFiles}>Upload doc</Button>
                </SheetTrigger>
                <SheetContent className="border-border-subtle bg-surface-2 backdrop-blur-xl">
                  <SheetHeader>
                    <SheetTitle>Upload document</SheetTitle>
                    <SheetDescription>Create a new employee document for the selected employee.</SheetDescription>
                  </SheetHeader>
                  <div className="space-y-4 px-4">
                    <div className="space-y-1">
                      <Label className="text-xs text-text-2">Employee</Label>
                      <Input
                        value={employeeQ.data ? `${employeeQ.data.person.first_name} ${employeeQ.data.person.last_name}`.trim() : employeeId}
                        readOnly
                      />
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="dms-upload-type" className="text-xs text-text-2">Document type</Label>
                      <select
                        id="dms-upload-type"
                        className={selectClassName}
                        value={uploadTypeCode}
                        onChange={(e) => setUploadTypeCode(e.target.value)}
                        disabled={uploadM.isPending}
                      >
                        <option value="">Select type...</option>
                        {(documentTypesQ.data?.items ?? []).map((item) => (
                          <option key={item.id} value={item.code}>{item.name} ({item.code})</option>
                        ))}
                      </select>
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="dms-upload-file" className="text-xs text-text-2">File</Label>
                      <input
                        id="dms-upload-file"
                        ref={uploadInputRef}
                        type="file"
                        onChange={(e) => setUploadFileValue(e.target.files?.[0] ?? null)}
                        disabled={uploadM.isPending}
                      />
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="dms-upload-expiry" className="text-xs text-text-2">Expiry date (optional)</Label>
                      <Input
                        id="dms-upload-expiry"
                        type="date"
                        value={uploadExpiry}
                        onChange={(e) => setUploadExpiry(e.target.value)}
                        disabled={uploadM.isPending}
                      />
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="dms-upload-notes" className="text-xs text-text-2">Notes (optional)</Label>
                      <textarea
                        id="dms-upload-notes"
                        className={[
                          "min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm",
                          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                        ].join(" ")}
                        value={uploadNotes}
                        onChange={(e) => setUploadNotes(e.target.value)}
                        placeholder="Add notes for HR or verifier..."
                        disabled={uploadM.isPending}
                      />
                    </div>
                  </div>
                  <SheetFooter>
                    <Button type="button" disabled={!canWriteDocs || !canWriteFiles || uploadM.isPending} onClick={() => uploadM.mutate()}>
                      {uploadM.isPending ? "Uploading..." : "Upload"}
                    </Button>
                  </SheetFooter>
                </SheetContent>
              </Sheet>
            </div>
          }
          meta={employeeQ.data ? <StatusChip status={employeeQ.data.employee.status} /> : null}
        />
      }
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
                  <select className={selectClassName} value={status} onChange={(e) => setStatus(e.target.value)}>
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
              description="Upload the first document for this employee."
              align="center"
              primaryAction={
                <Button type="button" disabled={!canWriteDocs || !canWriteFiles} onClick={() => setUploadOpen(true)}>
                  Upload doc
                </Button>
              }
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
        !employeeId ? (
          <EmptyState title="Select an employee" description="Choose an employee to view documents." />
        ) : employeeQ.isError ? (
          <ErrorState title="Could not load employee" error={employeeQ.error} onRetry={employeeQ.refetch} />
        ) : selected ? (
          <DocumentDetailCard
            document={selected}
            canReadFiles={canReadFiles}
            footer={
              <div className="space-y-4">
                <DSCard surface="panel" className="p-[var(--ds-space-16)]">
                  <div className="text-sm font-medium text-text-1">Actions</div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Sheet open={replaceOpen} onOpenChange={setReplaceOpen}>
                      <SheetTrigger asChild>
                        <Button type="button" variant="secondary" disabled={!canWriteDocs || !canWriteFiles}>
                          Replace document
                        </Button>
                      </SheetTrigger>
                      <SheetContent className="border-border-subtle bg-surface-2 backdrop-blur-xl">
                        <SheetHeader>
                          <SheetTitle>Replace document</SheetTitle>
                          <SheetDescription>Upload a new current version for this document.</SheetDescription>
                        </SheetHeader>
                        <div className="space-y-4 px-4">
                          <div className="space-y-1">
                            <Label htmlFor="dms-replace-file" className="text-xs text-text-2">File</Label>
                            <input
                              id="dms-replace-file"
                              ref={replaceInputRef}
                              type="file"
                              onChange={(e) => setReplaceFileValue(e.target.files?.[0] ?? null)}
                              disabled={replaceM.isPending}
                            />
                          </div>
                          <div className="space-y-1">
                            <Label htmlFor="dms-replace-notes" className="text-xs text-text-2">Notes (optional)</Label>
                            <textarea
                              id="dms-replace-notes"
                              className={[
                                "min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm",
                                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                              ].join(" ")}
                              value={replaceNotes}
                              onChange={(e) => setReplaceNotes(e.target.value)}
                              placeholder="Explain the replacement if needed..."
                              disabled={replaceM.isPending}
                            />
                          </div>
                        </div>
                        <SheetFooter>
                          <Button type="button" disabled={!canWriteDocs || !canWriteFiles || replaceM.isPending} onClick={() => replaceM.mutate()}>
                            {replaceM.isPending ? "Uploading..." : "Replace document"}
                          </Button>
                        </SheetFooter>
                      </SheetContent>
                    </Sheet>
                    <Button
                      type="button"
                      disabled={!canVerifyDocs || verifyM.isPending || Boolean(selected.verification_workflow_request_id)}
                      onClick={() => verifyM.mutate()}
                    >
                      {verifyM.isPending ? "Requesting..." : selected.verification_workflow_request_id ? "Verification requested" : "Request verification"}
                    </Button>
                  </div>
                </DSCard>
              </div>
            }
          />
        ) : docId ? (
          <ErrorState
            title="Document not available"
            error={new Error("This document is not in the current employee list. Clear filters or load more documents.")}
            details={
              <Button type="button" variant="secondary" onClick={() => setSelectedDoc(null)}>
                Clear selected document
              </Button>
            }
          />
        ) : (
          <EmptyState
            title="Select a document"
            description="Choose a document from the list to view current metadata and actions."
          />
        )
      }
    />
  );
}
