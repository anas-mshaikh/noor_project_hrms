"use client";

/**
 * /admin/import
 *
 * Phase 2 Admin Import (branch-scoped):
 * - Upload XLSX (POS + Attendance sheets)
 * - Backend validates/parses and writes to Postgres
 * - Optional publish triggers Firebase sync (if enabled on backend)
 *
 * Backend endpoints used:
 * - POST /api/v1/branches/{branch_id}/imports
 * - POST /api/v1/branches/{branch_id}/imports/{dataset_id}/publish
 */

import { useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { apiForm, apiJson } from "@/lib/api";
import { useSelection } from "@/lib/selection";
import { StorePicker } from "@/components/StorePicker";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";

type ImportErrorOut = { sheet: string; row: number; message: string };
type ImportTopSaleOut = { employee_code: string; name: string; net_sales: number | null };
type ImportResponse = {
  dataset_id: string;
  month_key: string;
  status: string;
  sync_status: string;
  counts: { employees: number; pos_rows: number; attendance_rows: number };
  preview: { topSales: ImportTopSaleOut[]; errors: ImportErrorOut[] };
};

type PublishResponse = {
  month_key: string;
  published_dataset_id: string;
  sync_status: string;
};

export default function AdminImportPage() {
  const branchId = useSelection((s) => s.branchId);

  const defaultMonthKey = useMemo(() => {
    // YYYY-MM (local browser time)
    return new Date().toISOString().slice(0, 7);
  }, []);

  const [monthKey, setMonthKey] = useState(defaultMonthKey);
  const [uploadedBy, setUploadedBy] = useState("");
  const [xlsxFile, setXlsxFile] = useState<File | null>(null);
  const [lastImport, setLastImport] = useState<ImportResponse | null>(null);
  const [lastPublish, setLastPublish] = useState<PublishResponse | null>(null);

  const uploadM = useMutation({
    mutationFn: async () => {
      if (!branchId) throw new Error("Select a branch first.");
      if (!xlsxFile) throw new Error("Select an .xlsx file first.");

      const form = new FormData();
      form.append("file", xlsxFile, xlsxFile.name);
      if (monthKey.trim()) form.append("month_key", monthKey.trim());
      if (uploadedBy.trim()) form.append("uploaded_by", uploadedBy.trim());

      return apiForm<ImportResponse>(`/api/v1/branches/${branchId}/imports`, form, { method: "POST" });
    },
    onSuccess: (res) => {
      setLastImport(res);
      setLastPublish(null);
    },
  });

  const publishM = useMutation({
    mutationFn: async () => {
      if (!branchId) throw new Error("Select a branch first.");
      const ds = lastImport?.dataset_id;
      if (!ds) throw new Error("Upload a dataset first.");
      return apiJson<PublishResponse>(`/api/v1/branches/${branchId}/imports/${ds}/publish`, { method: "POST" });
    },
    onSuccess: (res) => setLastPublish(res),
  });

  if (!branchId) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Admin Import</CardTitle>
          <CardDescription>Select a branch first.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-3">
            <StorePicker />
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Admin Import</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Upload a monthly XLSX (POS + Attendance). Postgres is the source of truth; publish optionally syncs to Firebase.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Upload XLSX</CardTitle>
          <CardDescription>
            The importer scans the first 30 rows to find headers and stops at TOTAL/blank rows.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-3">
            <div className="space-y-2">
              <Label htmlFor="monthKey">Month key (YYYY-MM)</Label>
              <Input id="monthKey" value={monthKey} onChange={(e) => setMonthKey(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="uploadedBy">Uploaded by (optional)</Label>
              <Input
                id="uploadedBy"
                value={uploadedBy}
                onChange={(e) => setUploadedBy(e.target.value)}
                placeholder="admin@company.com"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="xlsxFile">XLSX file</Label>
              <Input
                id="xlsxFile"
                type="file"
                accept=".xlsx"
                onChange={(e) => setXlsxFile(e.target.files?.[0] ?? null)}
              />
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button onClick={() => uploadM.mutate()} disabled={uploadM.isPending}>
              {uploadM.isPending ? "Uploading…" : "Upload"}
            </Button>
            {uploadM.isError ? (
              <div className="text-sm text-destructive">
                {uploadM.error instanceof Error ? uploadM.error.message : String(uploadM.error)}
              </div>
            ) : null}
          </div>
        </CardContent>
      </Card>

      {lastImport ? (
        <Card>
          <CardHeader>
            <CardTitle>Last Import</CardTitle>
            <CardDescription>dataset_id: {lastImport.dataset_id}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-2">
              <Badge variant="secondary">{lastImport.status}</Badge>
              <Badge variant="outline">sync: {lastImport.sync_status}</Badge>
              <Badge variant="outline">month: {lastImport.month_key}</Badge>
            </div>

            <div className="grid gap-3 md:grid-cols-3">
              <Card className="border-white/10 bg-white/[0.02]">
                <CardContent className="p-4">
                  <div className="text-xs text-muted-foreground">Employees</div>
                  <div className="mt-1 text-xl font-semibold">{lastImport.counts.employees}</div>
                </CardContent>
              </Card>
              <Card className="border-white/10 bg-white/[0.02]">
                <CardContent className="p-4">
                  <div className="text-xs text-muted-foreground">POS rows</div>
                  <div className="mt-1 text-xl font-semibold">{lastImport.counts.pos_rows}</div>
                </CardContent>
              </Card>
              <Card className="border-white/10 bg-white/[0.02]">
                <CardContent className="p-4">
                  <div className="text-xs text-muted-foreground">Attendance rows</div>
                  <div className="mt-1 text-xl font-semibold">{lastImport.counts.attendance_rows}</div>
                </CardContent>
              </Card>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="outline"
                onClick={() => publishM.mutate()}
                disabled={publishM.isPending}
              >
                {publishM.isPending ? "Publishing…" : "Publish"}
              </Button>
              {publishM.isError ? (
                <div className="text-sm text-destructive">
                  {publishM.error instanceof Error ? publishM.error.message : String(publishM.error)}
                </div>
              ) : null}
              {lastPublish ? (
                <div className="text-sm text-muted-foreground">
                  published_dataset_id:{" "}
                  <span className="font-mono text-xs">{lastPublish.published_dataset_id}</span>
                </div>
              ) : null}
            </div>

            {(lastImport.preview.errors ?? []).length ? (
              <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-2">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Sheet</TableHead>
                      <TableHead>Row</TableHead>
                      <TableHead>Error</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {lastImport.preview.errors.slice(0, 20).map((e, idx) => (
                      <TableRow key={idx}>
                        <TableCell className="font-mono text-xs">{e.sheet}</TableCell>
                        <TableCell className="font-mono text-xs">{e.row}</TableCell>
                        <TableCell className="text-sm">{e.message}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            ) : (
              <div className="text-sm text-muted-foreground">No validation errors reported.</div>
            )}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

