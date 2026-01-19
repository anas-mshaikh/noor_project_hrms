"use client";

/**
 * /admin/import
 *
 * Phase 2 Admin Import:
 * - Upload XLSX (POS + Attendance sheets)
 * - Backend validates/parses and writes to Postgres
 * - Optional publish step triggers Firebase sync (if enabled on backend)
 *
 * This page is protected by a minimal dev-only admin gate:
 * - ADMIN_PASSWORD (Next.js env)
 * - httpOnly cookie set by /api/admin/login
 */

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiForm, apiJson } from "@/lib/api";
import { useSelection } from "@/lib/selection";
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

type AdminMe = { is_admin: boolean };

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
  const qc = useQueryClient();

  const meQ = useQuery({
    queryKey: ["adminMe"],
    queryFn: async () => {
      const res = await fetch("/api/admin/me", { cache: "no-store" });
      if (!res.ok) throw new Error(await res.text());
      return (await res.json()) as AdminMe;
    },
    refetchOnWindowFocus: false,
  });

  // ----------------------------
  // Login
  // ----------------------------
  const [password, setPassword] = useState("");

  const loginM = useMutation({
    mutationFn: async () => {
      const res = await fetch("/api/admin/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      const text = await res.text();
      if (!res.ok) throw new Error(text);
      return text;
    },
    onSuccess: async () => {
      setPassword("");
      await qc.invalidateQueries({ queryKey: ["adminMe"] });
    },
  });

  const logoutM = useMutation({
    mutationFn: async () => {
      const res = await fetch("/api/admin/logout", { method: "POST" });
      const text = await res.text();
      if (!res.ok) throw new Error(text);
      return text;
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["adminMe"] });
    },
  });

  const isAdmin = Boolean(meQ.data?.is_admin);

  // ----------------------------
  // Import
  // ----------------------------
  const selection = useSelection();
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
      if (!xlsxFile) throw new Error("Select an .xlsx file first.");

      const form = new FormData();
      form.append("file", xlsxFile, xlsxFile.name);
      if (monthKey.trim()) form.append("month_key", monthKey.trim());
      if (uploadedBy.trim()) form.append("uploaded_by", uploadedBy.trim());
      if (selection.storeId) form.append("store_id", selection.storeId);

      return apiForm<ImportResponse>("/api/v1/imports", form, { method: "POST" });
    },
    onSuccess: (res) => {
      setLastImport(res);
      setLastPublish(null);
    },
  });

  const publishM = useMutation({
    mutationFn: async () => {
      const ds = lastImport?.dataset_id;
      if (!ds) throw new Error("Upload a dataset first.");
      return apiJson<PublishResponse>(`/api/v1/imports/${ds}/publish`, { method: "POST" });
    },
    onSuccess: (res) => setLastPublish(res),
  });

  if (meQ.isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Admin Import</CardTitle>
          <CardDescription>Checking admin session…</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  if (!isAdmin) {
    return (
      <div className="max-w-xl space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>Admin Login</CardTitle>
            <CardDescription>
              Enter the dev admin password to access imports.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="adminPassword">Admin password</Label>
              <Input
                id="adminPassword"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
              />
            </div>

            <div className="flex items-center gap-2">
              <Button onClick={() => loginM.mutate()} disabled={loginM.isPending}>
                {loginM.isPending ? "Signing in…" : "Sign in"}
              </Button>
              {loginM.error ? (
                <div className="text-sm text-destructive">
                  {String(loginM.error)}
                </div>
              ) : null}
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Admin Import</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Upload a monthly XLSX (POS + Attendance). Postgres is the source of truth; publish optionally syncs to Firebase.
          </p>
        </div>
        <Button variant="outline" onClick={() => logoutM.mutate()} disabled={logoutM.isPending}>
          Sign out
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Upload XLSX</CardTitle>
          <CardDescription>
            The importer scans the first 30 rows to find headers, stops at TOTAL or blank rows.
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
                placeholder="e.g. Store Manager"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="xlsx">Excel file (.xlsx)</Label>
              <Input
                id="xlsx"
                type="file"
                accept=".xlsx"
                onChange={(e) => setXlsxFile(e.target.files?.[0] ?? null)}
              />
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button onClick={() => uploadM.mutate()} disabled={uploadM.isPending}>
              {uploadM.isPending ? "Uploading…" : "Upload & Validate"}
            </Button>
            {uploadM.error ? (
              <div className="text-sm text-destructive">{String(uploadM.error)}</div>
            ) : null}
          </div>

          {lastImport ? (
            <div className="space-y-3 rounded-md border p-3">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="font-medium">dataset_id:</span>
                <code className="rounded bg-muted px-1 py-0.5">{lastImport.dataset_id}</code>
                <Badge variant="secondary">{lastImport.status}</Badge>
                <Badge variant="outline">{lastImport.sync_status}</Badge>
              </div>

              <div className="grid gap-2 text-sm md:grid-cols-3">
                <div>
                  <div className="text-muted-foreground">Employees</div>
                  <div className="font-medium">{lastImport.counts.employees}</div>
                </div>
                <div>
                  <div className="text-muted-foreground">POS rows</div>
                  <div className="font-medium">{lastImport.counts.pos_rows}</div>
                </div>
                <div>
                  <div className="text-muted-foreground">Attendance rows</div>
                  <div className="font-medium">{lastImport.counts.attendance_rows}</div>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Button
                  onClick={() => publishM.mutate()}
                  disabled={publishM.isPending || lastImport.status !== "READY"}
                >
                  {publishM.isPending ? "Publishing…" : "Publish"}
                </Button>
                {publishM.error ? (
                  <div className="text-sm text-destructive">{String(publishM.error)}</div>
                ) : null}
                {lastPublish ? (
                  <div className="text-sm text-muted-foreground">
                    Published {lastPublish.month_key} • sync:{" "}
                    <span className="font-medium">{lastPublish.sync_status}</span>
                  </div>
                ) : null}
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>

      {/* Preview */}
      {lastImport ? (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Preview: Top Sales</CardTitle>
              <CardDescription>Top 10 by net sales (from POS sheet).</CardDescription>
            </CardHeader>
            <CardContent>
              {lastImport.preview.topSales.length === 0 ? (
                <div className="text-sm text-muted-foreground">No preview rows.</div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Employee</TableHead>
                      <TableHead className="text-right">Net Sales</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {lastImport.preview.topSales.map((r) => (
                      <TableRow key={r.employee_code}>
                        <TableCell>
                          <div className="font-medium">{r.name}</div>
                          <div className="text-xs text-muted-foreground">{r.employee_code}</div>
                        </TableCell>
                        <TableCell className="text-right">
                          {typeof r.net_sales === "number" ? r.net_sales.toFixed(2) : "—"}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>

          {lastImport.preview.errors.length > 0 ? (
            <Card>
              <CardHeader>
                <CardTitle>Validation Errors</CardTitle>
                <CardDescription>
                  Row-level issues found during parsing (best-effort; minor issues don’t stop the import).
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {lastImport.preview.errors.map((e, idx) => (
                    <div key={`${e.sheet}-${e.row}-${idx}`} className="rounded border p-2 text-sm">
                      <div className="font-medium">
                        {e.sheet} • row {e.row}
                      </div>
                      <div className="text-muted-foreground">{e.message}</div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
