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
import type { EmployeeOut, FaceCreatedOut, MobileAccountOut } from "@/lib/types";
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

// Local type (so you don't have to edit lib/types.ts right now)
type FaceSearchMatchOut = {
  employee_id: string;
  employee_code: string;
  employee_name: string;
  cosine_distance: number;
  confidence: number;
};

type AdminMe = { is_admin: boolean };

type MobileProvisionOut = {
  firebase_uid: string;
  employee_id: string;
  employee_code: string;
  active: boolean;
  generated_password?: string | null;
};

export default function EmployeesPage() {
  const qc = useQueryClient();

  // Store comes from the top picker (Zustand persisted state)
  const storeId = useSelection((s) => s.storeId);

  // ----------------------------
  // Admin gate (dev-only)
  // ----------------------------
  //
  // The mobile provisioning endpoints are admin-only on the backend (guarded by ADMIN_MODE).
  // In the dashboard we reuse the same cookie-based dev gate as /admin/import:
  // - /api/admin/login sets an httpOnly cookie
  // - /api/admin/me returns {is_admin: boolean}
  //
  // This keeps the "mobile provisioning controls" hidden unless you're signed in as admin.
  const adminMeQ = useQuery({
    queryKey: ["adminMe"],
    queryFn: async () => {
      const res = await fetch("/api/admin/me", { cache: "no-store" });
      if (!res.ok) throw new Error(await res.text());
      return (await res.json()) as AdminMe;
    },
    refetchOnWindowFocus: false,
  });

  const isAdmin = Boolean(adminMeQ.data?.is_admin);

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
  // 1b) Mobile accounts (admin-only)
  // ----------------------------
  //
  // We list store-scoped mobile_accounts so we can show status per employee
  // and enable "Provision / Revoke / Resync" actions.
  const mobileAccountsQ = useQuery({
    queryKey: ["mobileAccounts", storeId],
    enabled: Boolean(storeId && isAdmin),
    queryFn: () =>
      apiJson<MobileAccountOut[]>(`/api/v1/stores/${storeId}/mobile/accounts`),
    refetchOnWindowFocus: false,
  });

  const mobileByEmployeeId = useMemo(() => {
    const map = new Map<string, MobileAccountOut>();
    for (const row of mobileAccountsQ.data ?? []) map.set(row.employee_id, row);
    return map;
  }, [mobileAccountsQ.data]);

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

  // ----------------------------
  // 5) Mobile access provisioning (Firebase Auth + Firestore users/{uid})
  // ----------------------------
  //
  // We keep this intentionally simple:
  // - Provision: creates/reenables Firebase Auth user and writes users/{uid} doc (backend)
  // - Revoke: disables user and marks mapping inactive (backend)
  // - Resync: re-upserts users/{uid} from Postgres source-of-truth (backend)
  //
  // The mobile app’s bootstrap:
  //   Firebase login -> uid -> Firestore users/{uid} -> org_id/store_id/employee_code -> read months docs
  const [mobileDialogEmployee, setMobileDialogEmployee] =
    useState<EmployeeOut | null>(null);
  const [mobileEmail, setMobileEmail] = useState("");
  const [mobileRole, setMobileRole] = useState<"employee" | "admin">("employee");
  const [mobileTempPassword, setMobileTempPassword] = useState("");
  const [mobileGeneratedPassword, setMobileGeneratedPassword] = useState<
    string | null
  >(null);

  const provisionMobileM = useMutation({
    mutationFn: async () => {
      if (!storeId) throw new Error("Select a store first.");
      if (!mobileDialogEmployee) throw new Error("Select an employee first.");
      if (!mobileEmail.trim())
        throw new Error("Email is required for MVP provisioning.");

      return apiJson<MobileProvisionOut>(
        `/api/v1/stores/${storeId}/employees/${mobileDialogEmployee.id}/mobile/provision`,
        {
          method: "POST",
          body: JSON.stringify({
            email: mobileEmail.trim(),
            role: mobileRole,
            // If blank, omit and allow backend to auto-generate (new users only).
            temp_password: mobileTempPassword.trim() || undefined,
          }),
        }
      );
    },
    onSuccess: async (res) => {
      setMobileGeneratedPassword(res.generated_password ?? null);
      await qc.invalidateQueries({ queryKey: ["mobileAccounts", storeId] });
    },
  });

  const revokeMobileM = useMutation({
    mutationFn: async (employeeId: string) => {
      return apiJson<{ firebase_uid: string; active: boolean }>(
        `/api/v1/employees/${employeeId}/mobile/revoke`,
        { method: "POST" }
      );
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["mobileAccounts", storeId] });
    },
  });

  const resyncMobileM = useMutation({
    mutationFn: async (firebaseUid: string) => {
      return apiJson<{ firebase_uid: string; resynced: boolean }>(
        `/api/v1/mobile/resync/${firebaseUid}`,
        { method: "POST" }
      );
    },
  });

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
          <CardDescription>
            {isAdmin ? (
              <>
                Mobile provisioning is enabled. Use “Provision mobile” to create a Firebase login
                and write the Firestore bootstrap doc at `users/{`{"uid"}`}`.
              </>
            ) : (
              <>
                Mobile provisioning is admin-only. Sign in once on{" "}
                <a className="underline" href="/admin/import">
                  /admin/import
                </a>{" "}
                to unlock mobile actions here.
              </>
            )}
          </CardDescription>
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
                  <TableHead>Mobile</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {employees.map((e) => {
                  const acc = isAdmin ? (mobileByEmployeeId.get(e.id) ?? null) : null;

                  return (
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

                      {/* Mobile access status (admin-only) */}
                      <TableCell>
                        {!isAdmin ? (
                          <Badge variant="outline">Admin required</Badge>
                        ) : mobileAccountsQ.isLoading ? (
                          <span className="text-xs text-muted-foreground">
                            Loading…
                          </span>
                        ) : acc ? (
                          <div className="space-y-1">
                            <div className="flex items-center gap-2">
                              {acc.active ? (
                                <Badge variant="secondary">Active</Badge>
                              ) : (
                                <Badge variant="outline">Revoked</Badge>
                              )}
                              <span className="text-xs text-muted-foreground">
                                {acc.role}
                              </span>
                            </div>
                            <div className="font-mono text-[11px] text-muted-foreground">
                              uid: {acc.firebase_uid}
                            </div>
                          </div>
                        ) : (
                          <span className="text-xs text-muted-foreground">
                            Not provisioned
                          </span>
                        )}
                      </TableCell>

                      <TableCell>
                        <div className="flex flex-wrap items-center gap-2">
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            onClick={() => setTargetEmployeeId(e.id)}
                          >
                            Enroll faces
                          </Button>

                          {/* Mobile access actions (admin-only) */}
                          {isAdmin ? (
                            acc?.active ? (
                              <>
                                <Button
                                  type="button"
                                  variant="outline"
                                  size="sm"
                                  onClick={() => revokeMobileM.mutate(e.id)}
                                  disabled={revokeMobileM.isPending}
                                >
                                  {revokeMobileM.isPending
                                    ? "Revoking…"
                                    : "Revoke mobile"}
                                </Button>
                                <Button
                                  type="button"
                                  variant="outline"
                                  size="sm"
                                  onClick={() =>
                                    resyncMobileM.mutate(acc.firebase_uid)
                                  }
                                  disabled={resyncMobileM.isPending}
                                >
                                  {resyncMobileM.isPending
                                    ? "Resyncing…"
                                    : "Resync"}
                                </Button>
                              </>
                            ) : (
                              <Dialog
                                open={mobileDialogEmployee?.id === e.id}
                                onOpenChange={(open) => {
                                  if (!open) {
                                    setMobileDialogEmployee(null);
                                    setMobileEmail("");
                                    setMobileTempPassword("");
                                    setMobileRole("employee");
                                    setMobileGeneratedPassword(null);
                                    provisionMobileM.reset();
                                  }
                                }}
                              >
                                <DialogTrigger asChild>
                                  <Button
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    onClick={() => {
                                      setMobileDialogEmployee(e);
                                      setMobileGeneratedPassword(null);
                                      provisionMobileM.reset();
                                    }}
                                  >
                                    {acc ? "Re-enable mobile" : "Provision mobile"}
                                  </Button>
                                </DialogTrigger>
                                <DialogContent>
                                  <DialogHeader>
                                    <DialogTitle>Provision Mobile Access</DialogTitle>
                                    <DialogDescription>
                                      Creates (or re-enables) a Firebase Auth user and writes the
                                      Firestore bootstrap doc at `users/{`{"uid"}`}`.
                                    </DialogDescription>
                                  </DialogHeader>

                                  <div className="space-y-4">
                                    <div className="space-y-1">
                                      <Label className="text-xs text-muted-foreground">
                                        Employee
                                      </Label>
                                      <div className="text-sm font-medium">
                                        {e.employee_code} — {e.name}
                                      </div>
                                    </div>

                                    <div className="grid gap-3 sm:grid-cols-2">
                                      <div className="space-y-1">
                                        <Label className="text-xs text-muted-foreground">
                                          Email
                                        </Label>
                                        <Input
                                          value={mobileEmail}
                                          onChange={(ev) =>
                                            setMobileEmail(ev.target.value)
                                          }
                                          placeholder="e.g. rahul@example.com"
                                        />
                                      </div>

                                      <div className="space-y-1">
                                        <Label className="text-xs text-muted-foreground">
                                          Role
                                        </Label>
                                        <select
                                          className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                                          value={mobileRole}
                                          onChange={(ev) =>
                                            setMobileRole(
                                              ev.target.value === "admin"
                                                ? "admin"
                                                : "employee"
                                            )
                                          }
                                        >
                                          <option value="employee">employee</option>
                                          <option value="admin">admin</option>
                                        </select>
                                      </div>
                                    </div>

                                    <div className="space-y-1">
                                      <Label className="text-xs text-muted-foreground">
                                        Temp password (optional)
                                      </Label>
                                      <Input
                                        value={mobileTempPassword}
                                        onChange={(ev) =>
                                          setMobileTempPassword(ev.target.value)
                                        }
                                        placeholder="If empty, backend generates one (new users only)"
                                      />
                                      <div className="text-xs text-muted-foreground">
                                        Tip: for re-enabling existing users, set a password here to
                                        reset it.
                                      </div>
                                    </div>

                                    {mobileGeneratedPassword ? (
                                      <div className="rounded-md border p-3">
                                        <div className="text-xs font-medium text-muted-foreground">
                                          Generated password
                                        </div>
                                        <div className="mt-1 font-mono text-sm">
                                          {mobileGeneratedPassword}
                                        </div>
                                      </div>
                                    ) : null}

                                    {provisionMobileM.error ? (
                                      <div className="text-sm text-destructive">
                                        {String(provisionMobileM.error)}
                                      </div>
                                    ) : null}
                                  </div>

                                  <DialogFooter>
                                    <Button
                                      type="button"
                                      onClick={() => provisionMobileM.mutate()}
                                      disabled={provisionMobileM.isPending}
                                    >
                                      {provisionMobileM.isPending
                                        ? "Provisioning…"
                                        : "Provision"}
                                    </Button>
                                  </DialogFooter>
                                </DialogContent>
                              </Dialog>
                            )
                          ) : null}
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
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
