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

  const createEmployeeM = useMutation({
    mutationFn: async () => {
      if (!storeId) throw new Error("Select a store first (top-right picker).");
      if (!newName.trim()) throw new Error("Employee name is required.");
      if (!newCode.trim()) throw new Error("Employee code is required.");

      return apiJson<EmployeeOut>(`/api/v1/stores/${storeId}/employees`, {
        method: "POST",
        body: JSON.stringify({
          name: newName.trim(),
          employee_code: newCode.trim(),
        }),
      });
    },
    onSuccess: async () => {
      setNewName("");
      setNewCode("");
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
      <div className="rounded border bg-white p-4">
        <h1 className="text-xl font-semibold">Employees</h1>
        <p className="mt-2 text-sm text-gray-600">
          Select an organization + store in the header first.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Employees</h1>

      {/* Create employee */}
      <section className="rounded border bg-white p-4">
        <h2 className="text-lg font-medium">Create Employee</h2>

        <div className="mt-3 flex flex-wrap items-end gap-2">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500">Employee code</label>
            <input
              className="w-56 rounded border px-2 py-1"
              value={newCode}
              onChange={(e) => setNewCode(e.target.value)}
              placeholder="e.g. E001"
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500">Employee name</label>
            <input
              className="w-72 rounded border px-2 py-1"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="e.g. Rahul Sharma"
            />
          </div>

          <button
            className="rounded bg-black px-3 py-2 text-white disabled:opacity-50"
            disabled={createEmployeeM.isPending}
            onClick={() => createEmployeeM.mutate()}
          >
            {createEmployeeM.isPending ? "Creating…" : "Create"}
          </button>

          {createEmployeeM.isError && (
            <div className="text-sm text-red-600">
              {String(createEmployeeM.error)}
            </div>
          )}
        </div>
      </section>

      {/* List employees */}
      <section className="rounded border bg-white p-4">
        <h2 className="text-lg font-medium">Employee List</h2>

        {employeesQ.isLoading ? (
          <div className="mt-3 text-sm text-gray-600">Loading…</div>
        ) : employeesQ.isError ? (
          <div className="mt-3 text-sm text-red-600">
            {String(employeesQ.error)}
          </div>
        ) : employees.length === 0 ? (
          <div className="mt-3 text-sm text-gray-600">No employees yet.</div>
        ) : (
          <div className="mt-3 overflow-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="border-b">
                  <th className="py-2 text-left">Code</th>
                  <th className="py-2 text-left">Name</th>
                  <th className="py-2 text-left">Active</th>
                  <th className="py-2 text-left">Actions</th>
                </tr>
              </thead>

              <tbody>
                {employees.map((e) => (
                  <tr key={e.id} className="border-b">
                    <td className="py-2">{e.employee_code}</td>
                    <td className="py-2">{e.name}</td>
                    <td className="py-2">{e.is_active ? "Yes" : "No"}</td>
                    <td className="py-2">
                      <button
                        className="rounded border px-2 py-1 hover:bg-gray-50"
                        onClick={() => setTargetEmployeeId(e.id)}
                      >
                        Enroll faces
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Face enrollment */}
      <section className="rounded border bg-white p-4">
        <h2 className="text-lg font-medium">Enroll Face Templates</h2>

        <p className="mt-2 text-sm text-gray-600">
          Upload 5–20 clear face images per employee (front-facing, good light).
          This is required for the video pipeline to assign attendance.
        </p>

        <div className="mt-3 flex flex-wrap items-end gap-2">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500">Employee</label>
            <select
              className="w-96 rounded border px-2 py-1"
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

          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500">Face images</label>
            <input
              key={fileInputKey}
              type="file"
              multiple
              accept="image/*"
              onChange={(e) => setFaceFiles(Array.from(e.target.files ?? []))}
            />
            <div className="text-xs text-gray-500">
              Selected: {faceFiles.length}
            </div>
          </div>

          <button
            className="rounded bg-black px-3 py-2 text-white disabled:opacity-50"
            disabled={uploadFacesM.isPending}
            onClick={() => uploadFacesM.mutate()}
          >
            {uploadFacesM.isPending ? "Uploading…" : "Upload faces"}
          </button>

          {uploadFacesM.isError && (
            <div className="text-sm text-red-600">
              {String(uploadFacesM.error)}
            </div>
          )}
        </div>

        {lastFaceUpload && (
          <div className="mt-4 rounded border bg-gray-50 p-3 text-xs">
            <div className="font-medium mb-2">Last upload result</div>
            <pre className="overflow-auto">
              {JSON.stringify(lastFaceUpload, null, 2)}
            </pre>
          </div>
        )}
      </section>

      {/* Search by face (optional) */}
      <section className="rounded border bg-white p-4">
        <h2 className="text-lg font-medium">Search By Face (optional)</h2>

        <p className="mt-2 text-sm text-gray-600">
          Debug tool: upload a face image and see the closest employees
          (pgvector).
        </p>

        <div className="mt-3 flex flex-wrap items-end gap-2">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500">Query face</label>
            <input
              type="file"
              accept="image/*"
              onChange={(e) =>
                setQueryFace((e.target.files?.[0] ?? null) as File | null)
              }
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500">Limit</label>
            <input
              className="w-24 rounded border px-2 py-1"
              type="number"
              value={searchLimit}
              min={1}
              max={20}
              onChange={(e) => setSearchLimit(Number(e.target.value))}
            />
          </div>

          <button
            className="rounded bg-black px-3 py-2 text-white disabled:opacity-50"
            disabled={searchByFaceM.isPending}
            onClick={() => searchByFaceM.mutate()}
          >
            {searchByFaceM.isPending ? "Searching…" : "Search"}
          </button>

          {searchByFaceM.isError && (
            <div className="text-sm text-red-600">
              {String(searchByFaceM.error)}
            </div>
          )}
        </div>

        {searchByFaceM.data && (
          <div className="mt-3 overflow-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="border-b">
                  <th className="py-2 text-left">Employee</th>
                  <th className="py-2 text-left">Distance</th>
                  <th className="py-2 text-left">Confidence</th>
                </tr>
              </thead>
              <tbody>
                {searchByFaceM.data.map((m) => (
                  <tr key={m.employee_id} className="border-b">
                    <td className="py-2">
                      {m.employee_code} — {m.employee_name}
                    </td>
                    <td className="py-2">{m.cosine_distance.toFixed(4)}</td>
                    <td className="py-2">{m.confidence.toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
