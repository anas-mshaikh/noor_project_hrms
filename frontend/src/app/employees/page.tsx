"use client";

/**
 * /employees
 *
 * MVP goal for this page:
 * - Create employees for the selected store
 * - Upload multiple face images per employee (templates) so the worker can identify them
 * - (Optional) Search by face to verify pgvector+InsightFace is working
 *
 * Backend endpoints used:
 * - GET  /api/v1/stores/{store_id}/employees
 * - POST /api/v1/stores/{store_id}/employees
 * - POST /api/v1/employees/{employee_id}/faces              (multipart: files[])
 * - POST /api/v1/stores/{store_id}/employees/search/by-face (multipart: file)
 */

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiForm, apiJson } from "@/lib/api";
import { useSelection } from "@/lib/selection";
import type { EmployeeOut, FaceCreatedOut } from "@/lib/types";
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";

// Local type (so you don't have to edit lib/types.ts right now)
type FaceSearchMatchOut = {
  employee_id: string;
  employee_code: string;
  employee_name: string;
  cosine_distance: number;
  confidence: number;
};

export default function EmployeesPage() {
  const qc = useQueryClient();

  // Store comes from the top picker (Zustand persisted state)
  const storeId = useSelection((s) => s.storeId);

  // ----------------------------
  // 1) List employees
  // ----------------------------
  const employeesQ = useQuery({
    queryKey: ["employees", storeId],
    enabled: Boolean(storeId),
    queryFn: () =>
      apiJson<EmployeeOut[]>(`/api/v1/stores/${storeId}/employees`),
  });

  const employees = useMemo(() => employeesQ.data ?? [], [employeesQ.data]);

  // ----------------------------
  // 2) Create employee (name + employee_code)
  // ----------------------------
  const [newName, setNewName] = useState("");
  const [newCode, setNewCode] = useState("");
  const [newDept, setNewDept] = useState("");

  const createEmployeeM = useMutation({
    mutationFn: async () => {
      if (!storeId) throw new Error("Select a store first (top-right picker).");
      if (!newName.trim()) throw new Error("Employee name is required.");
      if (!newCode.trim()) throw new Error("Employee code is required.");
      const department = newDept.trim() || "Unknown";

      return apiJson<EmployeeOut>(`/api/v1/stores/${storeId}/employees`, {
        method: "POST",
        body: JSON.stringify({
          name: newName.trim(),
          employee_code: newCode.trim(),
          department,
        }),
      });
    },
    onSuccess: async () => {
      setNewName("");
      setNewCode("");
      setNewDept("");
      await qc.invalidateQueries({ queryKey: ["employees", storeId] });
    },
  });

  // ----------------------------
  // 3) Upload face templates for an employee
  // ----------------------------
  const [targetEmployeeId, setTargetEmployeeId] = useState<string>("");
  const [faceFiles, setFaceFiles] = useState<File[]>([]);
  const [lastFaceUpload, setLastFaceUpload] = useState<FaceCreatedOut[] | null>(
    null
  );

  // Key trick: resetting key clears the <input type="file" /> UI after upload
  const [fileInputKey, setFileInputKey] = useState(0);

  const uploadFacesM = useMutation({
    mutationFn: async () => {
      if (!targetEmployeeId)
        throw new Error("Select an employee to enroll faces.");
      if (faceFiles.length === 0)
        throw new Error("Select 1..N face images first.");

      const form = new FormData();

      // IMPORTANT: backend expects list[UploadFile] param named `files`
      for (const f of faceFiles) {
        form.append("files", f, f.name);
      }

      return apiForm<FaceCreatedOut[]>(
        `/api/v1/employees/${targetEmployeeId}/faces`,
        form,
        { method: "POST" }
      );
    },
    onSuccess: (rows) => {
      // Keep the response visible so you can see snapshot_path + model_version
      setLastFaceUpload(rows);

      // Clear selection so user can't accidentally re-upload same files
      setFaceFiles([]);
      setFileInputKey((k) => k + 1);
    },
  });

  // ----------------------------
  // 4) Optional: Search by face (debug tool)
  // ----------------------------
  const [queryFace, setQueryFace] = useState<File | null>(null);
  const [searchLimit, setSearchLimit] = useState(5);

  const searchByFaceM = useMutation({
    mutationFn: async () => {
      if (!storeId) throw new Error("Select a store first (top-right picker).");
      if (!queryFace) throw new Error("Select a face image to search.");

      const form = new FormData();

      // IMPORTANT: backend expects UploadFile param named `file`
      form.append("file", queryFace, queryFace.name);

      const limit = Math.max(1, Math.min(20, Number(searchLimit) || 5));
      return apiForm<FaceSearchMatchOut[]>(
        `/api/v1/stores/${storeId}/employees/search/by-face?limit=${limit}`,
        form,
        { method: "POST" }
      );
    },
  });

  const employeeOptions = useMemo(() => {
    return employees.map((e) => ({
      id: e.id,
      label: `${e.employee_code} — ${e.name}`,
    }));
  }, [employees]);

  // If store isn't selected, we can't do anything meaningful here.
  if (!storeId) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Employees</CardTitle>
          <CardDescription>
            Select an organization + store in the header first.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Employees</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Create employees and enroll face templates.
        </p>
      </div>

      {/* Create employee */}
      <Card>
        <CardHeader>
          <CardTitle>Create Employee</CardTitle>
          <CardDescription>
            Employee code must be unique per store.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">
                Employee code
              </Label>
              <Input
                value={newCode}
                onChange={(e) => setNewCode(e.target.value)}
                placeholder="e.g. E001"
              />
            </div>

            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">Department</Label>
              <Input
                value={newDept}
                onChange={(e) => setNewDept(e.target.value)}
                placeholder="e.g. Grocery"
              />
            </div>

            <div className="space-y-1 sm:col-span-2">
              <Label className="text-xs text-muted-foreground">
                Employee name
              </Label>
              <Input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="e.g. Rahul Sharma"
              />
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              disabled={createEmployeeM.isPending}
              onClick={() => createEmployeeM.mutate()}
            >
              {createEmployeeM.isPending ? "Creating…" : "Create"}
            </Button>

            {createEmployeeM.isError && (
              <div className="text-sm text-destructive">
                {String(createEmployeeM.error)}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* List employees */}
      <Card>
        <CardHeader>
          <CardTitle>Employee List</CardTitle>
        </CardHeader>
        <CardContent>
          {employeesQ.isLoading ? (
            <div className="text-sm text-muted-foreground">Loading…</div>
          ) : employeesQ.isError ? (
            <div className="text-sm text-destructive">
              {String(employeesQ.error)}
            </div>
          ) : employees.length === 0 ? (
            <div className="text-sm text-muted-foreground">
              No employees yet.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Code</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Department</TableHead>
                  <TableHead>Active</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {employees.map((e) => (
                  <TableRow key={e.id}>
                    <TableCell className="font-mono text-xs">
                      {e.employee_code}
                    </TableCell>
                    <TableCell className="font-medium">{e.name}</TableCell>
                    <TableCell>{e.department}</TableCell>
                    <TableCell>
                      {e.is_active ? (
                        <Badge variant="secondary">Yes</Badge>
                      ) : (
                        <Badge variant="outline">No</Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => setTargetEmployeeId(e.id)}
                      >
                        Enroll faces
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Face enrollment */}
      <Card>
        <CardHeader>
          <CardTitle>Enroll Face Templates</CardTitle>
          <CardDescription>
            Upload 5–20 clear face images per employee (front-facing, good
            light).
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">Employee</Label>
              <select
                className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                value={targetEmployeeId}
                onChange={(e) => setTargetEmployeeId(e.target.value)}
              >
                <option value="">Select employee…</option>
                {employeeOptions.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">Face images</Label>
              <Input
                key={fileInputKey}
                type="file"
                multiple
                accept="image/*"
                onChange={(e) => setFaceFiles(Array.from(e.target.files ?? []))}
              />
              <div className="text-xs text-muted-foreground">
                Selected: {faceFiles.length}
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              disabled={uploadFacesM.isPending}
              onClick={() => uploadFacesM.mutate()}
            >
              {uploadFacesM.isPending ? "Uploading…" : "Upload faces"}
            </Button>

            {uploadFacesM.isError && (
              <div className="text-sm text-destructive">
                {String(uploadFacesM.error)}
              </div>
            )}
          </div>

          {lastFaceUpload && (
            <pre className="overflow-auto rounded-lg bg-muted/30 p-3 text-xs">
              {JSON.stringify(lastFaceUpload, null, 2)}
            </pre>
          )}
        </CardContent>
      </Card>

      {/* Search by face (optional) */}
      <Card>
        <CardHeader>
          <CardTitle>Search By Face (optional)</CardTitle>
          <CardDescription>
            Debug tool: upload a face image and see the closest employees.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="space-y-1 sm:col-span-2">
              <Label className="text-xs text-muted-foreground">Query face</Label>
              <Input
                type="file"
                accept="image/*"
                onChange={(e) => setQueryFace(e.target.files?.[0] ?? null)}
              />
            </div>

            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">Limit</Label>
              <Input
                type="number"
                value={searchLimit}
                min={1}
                max={20}
                onChange={(e) => setSearchLimit(Number(e.target.value))}
              />
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              disabled={searchByFaceM.isPending}
              onClick={() => searchByFaceM.mutate()}
            >
              {searchByFaceM.isPending ? "Searching…" : "Search"}
            </Button>

            {searchByFaceM.isError && (
              <div className="text-sm text-destructive">
                {String(searchByFaceM.error)}
              </div>
            )}
          </div>

          {searchByFaceM.data && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Employee</TableHead>
                  <TableHead>Distance</TableHead>
                  <TableHead>Confidence</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {searchByFaceM.data.map((m) => (
                  <TableRow key={m.employee_id}>
                    <TableCell>
                      {m.employee_code} — {m.employee_name}
                    </TableCell>
                    <TableCell className="tabular-nums">
                      {m.cosine_distance.toFixed(4)}
                    </TableCell>
                    <TableCell className="tabular-nums">
                      {m.confidence.toFixed(4)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
