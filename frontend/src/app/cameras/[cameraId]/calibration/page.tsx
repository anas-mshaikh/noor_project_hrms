"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";

import { apiJson } from "@/lib/api";

type UUID = string;
type Point = [number, number];

type Poly = { points: Point[]; closed: boolean };
type Line = { p1?: Point; p2?: Point };

type RawCal = Record<string, unknown>;
type RawPoint = [number, number];
type RawLine = { p1?: RawPoint; p2?: RawPoint };
type RawCalibJson = RawCal & {
  frame_size?: { w?: number; h?: number };
  inside_polygon?: RawPoint[];
  outside_polygon?: RawPoint[];
  gate_polygon?: RawPoint[];
  mask_polygons?: RawPoint[][];
  entry_line?: RawLine;
  inside_test_point?: RawPoint;
  neutral_band_px?: number;
};

type CalibrationState = {
  frameSize?: { w: number; h: number };
  inside: Poly;
  outside: Poly;
  gate: Poly;
  masks: Poly[];
  entryLine: Line;
  insideTestPoint?: Point;
  neutralBandPx: number;
};

type CameraOut = {
  id: UUID;
  name: string;
  calibration_json: any | null;
};

const emptyPoly: Poly = { points: [], closed: false };

// normalize helpers
function normalizePoly(raw?: unknown): Poly {
  const pts: Point[] = Array.isArray(raw)
    ? raw
        .filter(
          (q): q is RawPoint =>
            Array.isArray(q) &&
            q.length === 2 &&
            !isNaN(Number(q[0])) &&
            !isNaN(Number(q[1]))
        )
        .map((q) => [Number(q[0]), Number(q[1])])
    : [];
  return { points: pts, closed: pts.length >= 3 };
}

function normalizeState(
  raw: RawCalibJson | null | undefined
): CalibrationState {
  return {
    frameSize:
      raw?.frame_size && raw.frame_size.w && raw.frame_size.h
        ? { w: Number(raw.frame_size.w), h: Number(raw.frame_size.h) }
        : undefined,
    inside: normalizePoly(raw?.inside_polygon),
    outside: normalizePoly(raw?.outside_polygon),
    gate: normalizePoly(raw?.gate_polygon),
    masks: Array.isArray(raw?.mask_polygons)
      ? raw!.mask_polygons.map(normalizePoly)
      : [],
    entryLine: {
      p1:
        raw?.entry_line?.p1 && raw.entry_line.p1.length === 2
          ? [Number(raw.entry_line.p1[0]), Number(raw.entry_line.p1[1])]
          : undefined,
      p2:
        raw?.entry_line?.p2 && raw.entry_line.p2.length === 2
          ? [Number(raw.entry_line.p2[0]), Number(raw.entry_line.p2[1])]
          : undefined,
    },
    insideTestPoint:
      raw?.inside_test_point && raw.inside_test_point.length === 2
        ? [Number(raw.inside_test_point[0]), Number(raw.inside_test_point[1])]
        : undefined,
    neutralBandPx: Number(raw?.neutral_band_px ?? 12),
  };
}

function buildPayload(state: CalibrationState) {
  const polyOrNull = (p: Poly) => (p.points.length >= 3 ? p.points : undefined);
  const masks =
    state.masks
      .map((m) => (m.points.length >= 3 ? m.points : null))
      .filter(Boolean) ?? [];

  const entry_line =
    state.entryLine.p1 && state.entryLine.p2
      ? { p1: state.entryLine.p1, p2: state.entryLine.p2 }
      : undefined;

  return {
    frame_size: state.frameSize,
    inside_polygon: polyOrNull(state.inside),
    outside_polygon: polyOrNull(state.outside),
    gate_polygon: polyOrNull(state.gate),
    mask_polygons: masks.length ? masks : undefined,
    entry_line,
    inside_test_point: state.insideTestPoint,
    neutral_band_px: Math.max(0, Number(state.neutralBandPx) || 0),
  };
}

function validate(state: CalibrationState): string[] {
  const errs: string[] = [];
  const line = state.entryLine;
  if (line.p1 && line.p2) {
    if (line.p1[0] === line.p2[0] && line.p1[1] === line.p2[1]) {
      errs.push("Entry line points cannot be identical");
    }
    if (!state.insideTestPoint) {
      errs.push("inside_test_point is required when entry_line is set");
    }
  }
  if (state.neutralBandPx < 0) errs.push("neutral_band_px must be >= 0");
  return errs;
}

import { CalibrationCanvas, DrawMode } from "@/components/CalibrationCanvas";

export default function CalibrationPage() {
  const params = useParams();
  const cameraId = Array.isArray(params?.cameraId)
    ? params?.cameraId[0]
    : (params?.cameraId as string | undefined);

  const [imageObj, setImageObj] = useState<HTMLImageElement | null>(null);
  const [state, setState] = useState<CalibrationState>({
    frameSize: undefined,
    inside: { ...emptyPoly },
    outside: { ...emptyPoly },
    gate: { ...emptyPoly },
    masks: [],
    entryLine: {},
    insideTestPoint: undefined,
    neutralBandPx: 12,
  });
  const [mode, setMode] = useState<DrawMode>("select");
  const [activeMaskIndex, setActiveMaskIndex] = useState<number>(0);
  const [showJson, setShowJson] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const cameraQ = useQuery({
    queryKey: ["camera", cameraId],
    enabled: Boolean(cameraId),
    queryFn: () => apiJson<CameraOut>(`/api/v1/cameras/${cameraId}`),
    onSuccess: (cam) => {
      if (cam.calibration_json) {
        setState(normalizeState(cam.calibration_json));
      }
    },
  });

  const loadImage = (file: File) => {
    const img = new Image();
    img.onload = () => {
      setImageObj(img);
      setState((s) => ({
        ...s,
        frameSize: s.frameSize ?? {
          w: img.naturalWidth,
          h: img.naturalHeight,
        },
      }));
    };
    img.src = URL.createObjectURL(file);
  };

  const saveM = useMutation({
    mutationFn: async () => {
      if (!cameraId) throw new Error("Missing cameraId");
      const errs = validate(state);
      if (errs.length) throw new Error(errs.join("; "));
      if (!state.frameSize) throw new Error("Upload a reference image first");
      const payload = buildPayload(state);
      return apiJson(`/api/v1/cameras/${cameraId}/calibration`, {
        method: "PUT",
        body: JSON.stringify({ calibration_json: payload }),
      });
    },
    onSuccess: () => setMessage("Calibration saved"),
    onError: (e) => setMessage(String(e)),
  });

  const clearPoly = (key: "inside" | "outside" | "gate") => {
    setState((s) => ({ ...s, [key]: { ...emptyPoly } }));
  };
  const clearMasks = () => setState((s) => ({ ...s, masks: [] }));
  const clearLine = () =>
    setState((s) => ({ ...s, entryLine: {}, insideTestPoint: undefined }));
  const clearAll = () =>
    setState((s) => ({
      ...s,
      inside: { ...emptyPoly },
      outside: { ...emptyPoly },
      gate: { ...emptyPoly },
      masks: [],
      entryLine: {},
      insideTestPoint: undefined,
    }));

  if (!cameraId) {
    return (
      <div className="p-4">
        <h1 className="text-xl font-semibold">Calibration</h1>
        <p className="mt-2 text-red-600">cameraId missing in URL</p>
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-80px)] flex-col">
      {/* Top bar */}
      <div className="flex items-center justify-between border-b bg-white px-4 py-3">
        <div>
          <div className="text-sm text-gray-500">Camera</div>
          <div className="text-lg font-semibold">
            {cameraQ.data?.name ?? "Loading..."}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            className="rounded border px-3 py-2 text-sm hover:bg-gray-50"
            onClick={() => setShowJson((v) => !v)}
          >
            {showJson ? "Hide JSON" : "Show JSON"}
          </button>
          <button
            className="rounded bg-black px-4 py-2 text-sm text-white disabled:opacity-50"
            disabled={saveM.isPending}
            onClick={() => saveM.mutate()}
          >
            {saveM.isPending ? "Saving…" : "Save"}
          </button>
        </div>
      </div>

      {/* Main layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left panel */}
        <div className="w-72 shrink-0 border-r bg-white p-4 text-sm space-y-3">
          <div className="font-medium">Tools</div>
          <div className="grid grid-cols-1 gap-2">
            {(
              [
                ["select", "Edit/Move"],
                ["inside", "Draw Inside"],
                ["outside", "Draw Outside"],
                ["gate", "Draw Gate"],
                ["mask", "Draw Mask"],
                ["line", "Entry Line"],
                ["insidePoint", "Inside Test Point"],
              ] as [DrawMode, string][]
            ).map(([m, label]) => (
              <button
                key={m}
                className={`rounded border px-2 py-1 text-left ${
                  mode === m ? "border-black bg-gray-100" : "hover:bg-gray-50"
                }`}
                onClick={() => setMode(m)}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="pt-2">
            <div className="text-xs text-gray-600">Neutral band (px)</div>
            <input
              type="number"
              className="w-full rounded border px-2 py-1"
              value={state.neutralBandPx}
              onChange={(e) =>
                setState((s) => ({
                  ...s,
                  neutralBandPx: Math.max(0, Number(e.target.value) || 0),
                }))
              }
            />
          </div>

          <div className="space-y-1 pt-2">
            <div className="text-xs text-gray-600">Clear</div>
            <div className="grid grid-cols-1 gap-1">
              <button
                className="rounded border px-2 py-1 hover:bg-gray-50"
                onClick={() => clearPoly("inside")}
              >
                Clear Inside
              </button>
              <button
                className="rounded border px-2 py-1 hover:bg-gray-50"
                onClick={() => clearPoly("outside")}
              >
                Clear Outside
              </button>
              <button
                className="rounded border px-2 py-1 hover:bg-gray-50"
                onClick={() => clearPoly("gate")}
              >
                Clear Gate
              </button>
              <button
                className="rounded border px-2 py-1 hover:bg-gray-50"
                onClick={() => clearMasks()}
              >
                Clear Masks
              </button>
              <button
                className="rounded border px-2 py-1 hover:bg-gray-50"
                onClick={() => clearLine()}
              >
                Clear Line/Test Point
              </button>
              <button
                className="rounded border px-2 py-1 hover:bg-gray-50"
                onClick={() => clearAll()}
              >
                Clear All
              </button>
            </div>
          </div>

          <div className="pt-2 text-xs text-gray-600">
            Gate polygon limits where entry/exit line crossings are trusted
            (door region). Optional but recommended.
          </div>

          {message && (
            <div className="rounded border border-gray-200 bg-gray-50 p-2 text-xs">
              {message}
            </div>
          )}

          {validate(state).length > 0 && (
            <div className="rounded border border-red-200 bg-red-50 p-2 text-xs text-red-700">
              {validate(state).map((e) => (
                <div key={e}>• {e}</div>
              ))}
            </div>
          )}
        </div>

        {/* Canvas panel */}
        <div className="flex-1 overflow-hidden bg-gray-50">
          <div className="flex items-center justify-between px-4 py-2 text-sm">
            <div className="flex items-center gap-2">
              <label className="rounded border px-2 py-1 hover:bg-white cursor-pointer">
                Upload reference image
                <input
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) loadImage(f);
                  }}
                />
              </label>
              <div className="text-xs text-gray-600">
                {state.frameSize
                  ? `Frame: ${state.frameSize.w}x${state.frameSize.h}`
                  : "No frame loaded"}
              </div>
            </div>
          </div>

          <CalibrationCanvas
            image={imageObj}
            state={state}
            onChange={(next) => setState(next)}
            mode={mode}
            activeMaskIndex={activeMaskIndex}
            setActiveMaskIndex={setActiveMaskIndex}
          />
        </div>

        {/* JSON panel */}
        {showJson && (
          <div className="w-96 shrink-0 border-l bg-white p-4 text-xs overflow-auto">
            <div className="flex items-center justify-between">
              <div className="font-medium">Calibration JSON</div>
              <button
                className="rounded border px-2 py-1 hover:bg-gray-50"
                onClick={() =>
                  navigator.clipboard.writeText(
                    JSON.stringify(buildPayload(state), null, 2)
                  )
                }
              >
                Copy
              </button>
            </div>
            <pre className="mt-2 whitespace-pre-wrap">
              {JSON.stringify(buildPayload(state), null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
