"use client";

/**
 * CalibrationCanvas.tsx
 *
 * Responsibilities:
 * - Render reference image scaled to fit container.
 * - Draw/edit polygons, masks, entry line, inside test point.
 * - Convert between stage coords (scaled) and original image coords.
 *
 * Saved points are ALWAYS in original image pixel coordinates.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { Stage, Layer, Line, Circle, Image as KonvaImage, Group } from "react-konva";
import type { KonvaEventObject } from "konva/lib/Node";

type Point = [number, number];
type Poly = { points: Point[]; closed: boolean };
type LineType = { p1?: Point; p2?: Point };

export type DrawMode =
  | "select"
  | "inside"
  | "outside"
  | "gate"
  | "mask"
  | "line"
  | "insidePoint";

type CalibrationState = {
  frameSize?: { w: number; h: number };
  inside: Poly;
  outside: Poly;
  gate: Poly;
  masks: Poly[];
  entryLine: LineType;
  insideTestPoint?: Point;
  neutralBandPx: number;
};

type Props = {
  image: HTMLImageElement | null;
  state: CalibrationState;
  onChange: (next: CalibrationState) => void;
  mode: DrawMode;
  activeMaskIndex: number;
  setActiveMaskIndex: (i: number) => void;
};

const FIRST_CLICK_CLOSE_PX = 12;

function dist(a: Point, b: Point): number {
  const dx = a[0] - b[0];
  const dy = a[1] - b[1];
  return Math.sqrt(dx * dx + dy * dy);
}

export function CalibrationCanvas({
  image,
  state,
  onChange,
  mode,
  activeMaskIndex,
  setActiveMaskIndex,
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [stageSize, setStageSize] = useState({ w: 800, h: 450 });

  // Update stage size on resize
  useEffect(() => {
    const resize = () => {
      if (!containerRef.current || !image) return;
      const w = containerRef.current.clientWidth;
      const scale = w / image.naturalWidth;
      setStageSize({ w, h: image.naturalHeight * scale });
    };
    resize();
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, [image]);

  // Coordinate conversion
  const scale = useMemo(() => {
    if (!image) return 1;
    return stageSize.w / image.naturalWidth;
  }, [image, stageSize.w]);

  const imgToStage = (p: Point): { x: number; y: number } => ({
    x: p[0] * scale,
    y: p[1] * scale,
  });
  const stageToImg = (x: number, y: number): Point => [x / scale, y / scale];

  const getPoly = (m: DrawMode) => {
    switch (m) {
      case "inside":
        return ["inside", state.inside] as const;
      case "outside":
        return ["outside", state.outside] as const;
      case "gate":
        return ["gate", state.gate] as const;
      case "mask": {
        const idx = activeMaskIndex;
        const poly = state.masks[idx] ?? { points: [], closed: false };
        return [`mask-${idx}`, poly] as const;
      }
      default:
        return null;
    }
  };

  const updatePoly = (key: string, poly: Poly) => {
    if (key === "inside" || key === "outside" || key === "gate") {
      onChange({ ...state, [key]: poly });
    } else if (key.startsWith("mask-")) {
      const idx = parseInt(key.split("-")[1], 10) || 0;
      const masks = [...state.masks];
      masks[idx] = poly;
      onChange({ ...state, masks });
      setActiveMaskIndex(idx);
    }
  };

  // Handle clicks for drawing
  const handleClick = (e: KonvaEventObject<MouseEvent>) => {
    if (!image) return;
    const pos = e.target.getStage()?.getPointerPosition();
    if (!pos) return;
    const imgPt = stageToImg(pos.x, pos.y);

    // Entry line
    if (mode === "line") {
      const next =
        state.entryLine.p1 && !state.entryLine.p2
          ? { p1: state.entryLine.p1, p2: imgPt }
          : { p1: imgPt, p2: undefined };
      onChange({ ...state, entryLine: next });
      return;
    }

    // Inside test point
    if (mode === "insidePoint") {
      onChange({ ...state, insideTestPoint: imgPt });
      return;
    }

    // Polygons
    const polyInfo = getPoly(mode);
    if (!polyInfo) return;
    const [key, poly] = polyInfo;

    // Close if clicking near first point
    if (
      poly.points.length >= 3 &&
      dist(poly.points[0], imgPt) <= FIRST_CLICK_CLOSE_PX
    ) {
      updatePoly(key, { ...poly, closed: true });
      return;
    }

    const newPts = [...poly.points, imgPt] as Point[];
    updatePoly(key, { points: newPts, closed: poly.closed });
  };

  const startNewMask = () => {
    const masks = [...state.masks, { points: [], closed: false }];
    onChange({ ...state, masks });
    setActiveMaskIndex(masks.length - 1);
    // Switch mode to mask to continue drawing
  };

  // Drag handlers (edit mode)
  const onDragVertex = (
    key: string,
    idx: number,
    pos: { x: number; y: number }
  ) => {
    const imgPt = stageToImg(pos.x, pos.y);
    const poly =
      key === "inside"
        ? state.inside
        : key === "outside"
        ? state.outside
        : key === "gate"
        ? state.gate
        : state.masks[parseInt(key.split("-")[1], 10)] ??
          ({ points: [], closed: false } as Poly);

    const newPts = [...poly.points];
    newPts[idx] = imgPt;
    updatePoly(key, { ...poly, points: newPts });
  };

  const onDragLinePoint =
    (which: "p1" | "p2") => (pos: { x: number; y: number }) => {
      const imgPt = stageToImg(pos.x, pos.y);
      onChange({
        ...state,
        entryLine: { ...state.entryLine, [which]: imgPt },
      });
    };

  const onDragInsidePoint = (pos: { x: number; y: number }) => {
    const imgPt = stageToImg(pos.x, pos.y);
    onChange({ ...state, insideTestPoint: imgPt });
  };

  const renderPoly = (key: string, poly: Poly, color: string) => {
    const pts = poly.points.flatMap((p) => {
      const s = imgToStage(p);
      return [s.x, s.y];
    });
    const closed = poly.closed || poly.points.length >= 3;
    return (
      <Line
        key={key}
        points={pts}
        closed={closed}
        stroke={color}
        strokeWidth={2}
        opacity={0.9}
        fill={closed ? `${color}33` : undefined}
      />
    );
  };

  const renderVertices = (key: string, poly: Poly, color: string) =>
    poly.points.map((p, idx) => {
      const s = imgToStage(p);
      return (
        <Circle
          key={`${key}-v-${idx}`}
          x={s.x}
          y={s.y}
          radius={5}
          fill={color}
          draggable={mode === "select"}
          onDragMove={(e) =>
            onDragVertex(key, idx, {
              x: e.target.x(),
              y: e.target.y(),
            })
          }
        />
      );
    });

  const imgWidth = image?.naturalWidth ?? 1;
  const imgHeight = image?.naturalHeight ?? 1;

  return (
    <div ref={containerRef} className="h-full w-full overflow-hidden">
      <Stage
        width={stageSize.w}
        height={stageSize.h}
        onMouseDown={handleClick}
        className="bg-gray-200"
      >
        <Layer>
          {image && (
            <KonvaImage
              image={image}
              width={stageSize.w}
              height={(imgHeight / imgWidth) * stageSize.w}
            />
          )}

          {renderPoly("inside", state.inside, "#16a34a")}
          {renderVertices("inside", state.inside, "#16a34a")}

          {renderPoly("outside", state.outside, "#2563eb")}
          {renderVertices("outside", state.outside, "#2563eb")}

          {renderPoly("gate", state.gate, "#d97706")}
          {renderVertices("gate", state.gate, "#d97706")}

          {state.masks.map((m, idx) => (
            <Group key={`mask-${idx}`}>
              {renderPoly(`mask-${idx}`, m, "#ef4444")}
              {renderVertices(`mask-${idx}`, m, "#ef4444")}
            </Group>
          ))}

          {/* Entry line */}
          {state.entryLine.p1 && state.entryLine.p2 && (
            <Line
              points={[
                ...(() => {
                  const a = imgToStage(state.entryLine.p1!);
                  const b = imgToStage(state.entryLine.p2!);
                  return [a.x, a.y, b.x, b.y];
                })(),
              ]}
              stroke="#000"
              strokeWidth={2}
            />
          )}

          {state.entryLine.p1 && (
            <Circle
              x={imgToStage(state.entryLine.p1).x}
              y={imgToStage(state.entryLine.p1).y}
              radius={6}
              fill="#000"
              draggable={mode === "select"}
              onDragMove={(e) =>
                onDragLinePoint("p1")({ x: e.target.x(), y: e.target.y() })
              }
            />
          )}
          {state.entryLine.p2 && (
            <Circle
              x={imgToStage(state.entryLine.p2).x}
              y={imgToStage(state.entryLine.p2).y}
              radius={6}
              fill="#000"
              draggable={mode === "select"}
              onDragMove={(e) =>
                onDragLinePoint("p2")({ x: e.target.x(), y: e.target.y() })
              }
            />
          )}

          {/* Inside test point */}
          {state.insideTestPoint && (
            <Circle
              x={imgToStage(state.insideTestPoint).x}
              y={imgToStage(state.insideTestPoint).y}
              radius={6}
              fill="#a855f7"
              draggable={mode === "select"}
              onDragMove={(e) =>
                onDragInsidePoint({ x: e.target.x(), y: e.target.y() })
              }
            />
          )}
        </Layer>
      </Stage>

      {/* Mask management helper */}
      <div className="flex items-center gap-2 bg-white px-3 py-2 text-xs">
        <button
          className="rounded border px-2 py-1 hover:bg-gray-50"
          onClick={startNewMask}
        >
          New Mask
        </button>
        <div className="flex items-center gap-2">
          <span className="text-gray-600">Active mask:</span>
          <select
            className="rounded border px-2 py-1"
            value={activeMaskIndex}
            onChange={(e) => setActiveMaskIndex(Number(e.target.value))}
          >
            {state.masks.map((_, idx) => (
              <option key={idx} value={idx}>
                Mask {idx + 1}
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}
