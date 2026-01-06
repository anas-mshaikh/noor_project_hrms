"""
zones.py

This file turns *camera calibration* into two practical operations:

1) classify_zone(point) -> Zone (INSIDE/OUTSIDE/UNKNOWN)
2) oriented_line_sign(point) -> +1 (inside side) / -1 (outside side) / None (neutral)

Why point-based?

Your detector/tracker gives you a bbox. For door logic, the most reliable
single point is usually the "foot point" (bottom-center of the bbox),
because that's what actually crosses the door threshold.

The event engine (event_engine.py) debounces these raw classifications and
emits ENTRY/EXIT events (observed or inferred).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from math import hypot
from typing import Any


# TODO: Research on Frigate's zone implementation
Point = tuple[float, float]
Polygon = list[Point]
Polygons = list[Polygon]


class Zone(str, Enum):
    INSIDE = "inside"
    OUTSIDE = "outside"
    UNKNOWN = "unknown"


def _as_point(value: Any) -> Point:
    """
    Convert JSON [x, y] into a (float, float) tuple.
    Keeping this strict helps catch calibration bugs early.
    """
    if (
        not isinstance(value, (list, tuple))
        or len(value) != 2
        or not isinstance(value[0], (int, float))
        or not isinstance(value[1], (int, float))
    ):
        raise ValueError(f"Invalid point: {value!r}")
    return (float(value[0]), float(value[1]))


def _as_polygon(value: Any) -> Polygon:
    """
    Convert JSON [[x,y], ...] into a list[tuple[float,float]].
    Returns [] for None.
    """
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"Invalid polygon: {value!r}")
    return [_as_point(p) for p in value]


def _as_polygons(value: Any) -> Polygons:
    """
    Convert JSON [[[x,y], ...], [[x,y], ...], ...] into list of polygons.
    Returns [] for None.
    """
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"Invalid polygons: {value!r}")
    return [_as_polygon(poly) for poly in value]


@dataclass(frozen=True)
class ZoneConfig:
    """
    Door/zone calibration config.

    What the worker needs:
    - INSIDE / OUTSIDE zone classification (for entry/exit)
    - Optional oriented door line (stronger evidence + direction)
    - Door ROI polygon (for motion gating + optional detection crop)
    - Optional masks (ignored zones)

    Recommended JSON schema (frontend should send these keys):

      coord_space: "normalized" | "pixel"        # default "pixel"
      frame_width, frame_height                  # optional ref size for pixel scaling
      frame_size: {"w": number, "h": number}     # alias for frame_width/frame_height

      door_roi_polygon: [[x,y], ...]
      inside_zone_polygon: [[x,y], ...]
      outside_zone_polygon: [[x,y], ...]
      ignore_mask_polygons: [ [[x,y],...], ... ]

      entry_line: [[x,y],[x,y]] OR {"p1":[x,y],"p2":[x,y]}
      inside_test_point: [x,y]
      neutral_band_px: float                     # UNKNOWN band near line

    Backwards-compatible aliases (so you don't break older calibration payloads):
      inside_polygon / inside
      outside_polygon / outside
      gate_polygon / gate
      mask_polygons / masks
    """

    # ----------------------------
    # Zone polygons (preferred)
    # ----------------------------
    inside: Polygon | None = None
    outside: Polygon | None = None

    # ----------------------------
    # Door ROI (used for motion gating)
    # ----------------------------
    door_roi: Polygon | None = None

    # ----------------------------
    # Optional door line
    # ----------------------------
    entry_line_p1: Point | None = None
    entry_line_p2: Point | None = None
    inside_test_point: Point | None = None
    neutral_band_px: float = 10.0

    # Optional: a smaller polygon around the doorway to validate crossings.
    # If you don't provide gate, we will default gate = door_roi (when door_roi exists).
    gate: Polygon | None = None

    # Any point inside a mask is treated as UNKNOWN.
    masks: Polygons = field(default_factory=list)

    @classmethod
    def from_calibration_json(
        cls,
        data: dict[str, Any],
        *,
        target_width: int | None = None,
        target_height: int | None = None,
    ) -> "ZoneConfig":
        """
        Parse cameras.calibration_json and (optionally) SCALE it to actual video size.

        Scaling rules:
        - coord_space="normalized": points are 0..1 and we scale by target_width/target_height
        - coord_space="pixel": points are in a reference frame; if frame_width/frame_height are present,
          we scale to target_width/target_height
        """
        coord_space = str(data.get("coord_space", "pixel")).lower()

        # Reference frame size (only used for coord_space="pixel" scaling)
        ref_w = data.get("frame_width")
        ref_h = data.get("frame_height")

        # Backwards-compatible alias used by the frontend calibration tool.
        # Example: {"frame_size": {"w": 1920, "h": 1080}}
        # We keep this here so old saved calibrations keep working.
        if (ref_w is None or ref_h is None) and isinstance(data.get("frame_size"), dict):
            fs = data["frame_size"]
            ref_w = ref_w or fs.get("w") or fs.get("width")
            ref_h = ref_h or fs.get("h") or fs.get("height")

        # New schema keys + backwards-compatible aliases
        door_roi_raw = data.get(
            "door_roi_polygon", data.get("door_roi", data.get("roi_polygon"))
        )

        inside_raw = data.get(
            "inside_zone_polygon",
            data.get("inside_polygon", data.get("inside")),
        )
        outside_raw = data.get(
            "outside_zone_polygon",
            data.get("outside_polygon", data.get("outside")),
        )
        gate_raw = data.get("gate_polygon", data.get("gate"))

        masks_raw = data.get(
            "ignore_mask_polygons",
            data.get("mask_polygons", data.get("masks")),
        )

        #  Door line can be {"p1": [...], "p2": [...]} OR [[...], [...]]
        entry_line = data.get("entry_line")
        p1 = p2 = None

        if entry_line is not None:
            if isinstance(entry_line, dict):
                p1 = _as_point(entry_line.get("p1"))
                p2 = _as_point(entry_line.get("p2"))
            else:
                pts = _as_polygon(entry_line)
                if len(pts) != 2:
                    raise ValueError("entry_line must have exactly 2 points")
                p1, p2 = pts[0], pts[1]

        inside_test_point_raw = data.get("inside_test_point")

        # Neutral band is a pixel distance to the line (UNKNOWN near the line).
        neutral_band_px = float(data.get("neutral_band_px", 10.0))

        # NOTE Optional: if frontend uses normalized coordinates, it can also provide neutral_band_norm.
        # Example: neutral_band_norm=0.01 => 1% of max(frame_dim)
        neutral_band_norm = data.get("neutral_band_norm")
        if neutral_band_norm is not None:
            if target_width is None or target_height is None:
                raise ValueError(
                    "neutral_band_norm requires target_width/target_height"
                )
            neutral_band_px = float(neutral_band_norm) * max(
                float(target_width), float(target_height)
            )

        # ----------------------------
        # Decide scaling factors
        # ----------------------------
        sx = sy = 1.0

        if coord_space == "normalized":
            # Points are 0..1 => scale to actual pixels
            if target_width is None or target_height is None:
                raise ValueError(
                    "coord_space=normalized requires target_width/target_height"
                )
            sx = float(target_width)
            sy = float(target_height)

        elif coord_space == "pixel":
            # Points are pixels in ref frame => scale to actual video size if possible
            if ref_w and ref_h and target_width and target_height:
                sx = float(target_width) / float(ref_w)
                sy = float(target_height) / float(ref_h)

                # Neutral band is also in pixels, so scale it with the frame
                neutral_band_px *= (sx + sy) / 2.0

        else:
            raise ValueError("coord_space must be 'pixel' or 'normalized'")

        def scale_point(p: Point | None) -> Point | None:
            if p is None:
                return None
            return (p[0] * sx, p[1] * sy)

        def scale_poly(poly: Polygon | None) -> Polygon | None:
            if not poly:
                return None
            return [(x * sx, y * sy) for (x, y) in poly]

        def scale_polys(polys: Polygons) -> Polygons:
            out: Polygons = []
            for poly in polys:
                if len(poly) < 3:
                    continue
                out.append([(x * sx, y * sy) for (x, y) in poly])
            return out

        door_roi = scale_poly(_as_polygon(door_roi_raw) or None)
        inside = scale_poly(_as_polygon(inside_raw) or None)
        outside = scale_poly(_as_polygon(outside_raw) or None)
        gate = scale_poly(_as_polygon(gate_raw) or None)
        masks = scale_polys(_as_polygons(masks_raw))

        # Practical default: if gate not provided, reuse door ROI as gate.
        if gate is None and door_roi is not None:
            gate = door_roi

        return cls(
            inside=inside,
            outside=outside,
            door_roi=door_roi,
            entry_line_p1=scale_point(p1),
            entry_line_p2=scale_point(p2),
            inside_test_point=scale_point(_as_point(inside_test_point_raw))
            if inside_test_point_raw
            else None,
            neutral_band_px=float(neutral_band_px),
            gate=gate,
            masks=masks,
        )


def _cross(ax: float, ay: float, bx: float, by: float) -> float:
    # 2D cross product (ax,ay) x (bx,by)
    return ax * by - ay * bx


def _point_on_segment(
    p: Point,
    a: Point,
    b: Point,
    *,
    eps: float = 1e-9,
) -> bool:
    """
    True if point p is on segment a->b (with epsilon tolerance).
    Used so point_in_polygon treats boundary as inside.
    """
    px, py = p
    ax, ay = a
    bx, by = b

    # Colinearity check: cross((b-a),(p-a)) ~= 0
    if abs(_cross(bx - ax, by - ay, px - ax, py - ay)) > eps:
        return False

    # Bounding box check
    if (min(ax, bx) - eps) <= px <= (max(ax, bx) + eps) and (
        min(ay, by) - eps
    ) <= py <= (max(ay, by) + eps):
        return True

    return False


def point_in_polygon(point: Point, polygon: Polygon) -> bool:
    """
    Ray-casting point-in-polygon test.

    - Returns True for points strictly inside OR on the boundary.
    - Returns False for invalid polygons (< 3 points).
    """
    if len(polygon) < 3:
        return False

    # Boundary = inside (helps avoid flicker when a point rides the line)
    for i in range(len(polygon)):
        if _point_on_segment(point, polygon[i], polygon[(i + 1) % len(polygon)]):
            return True

    x, y = point
    inside = False

    j = len(polygon) - 1
    for i in range(len(polygon)):
        xi, yi = polygon[i]
        xj, yj = polygon[j]

        # Does edge (j -> i) cross the horizontal ray to the right of (x,y)?
        intersects = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / (yj - yi) + xi
        )
        if intersects:
            inside = not inside

        j = i

    return inside


def _in_any_polygon(point: Point, polygons: Polygons) -> bool:
    return any(point_in_polygon(point, poly) for poly in polygons if len(poly) >= 3)


def signed_distance_to_line(point: Point, p1: Point, p2: Point) -> float:
    """
    Signed perpendicular distance from point to the infinite line through p1->p2.

    - Magnitude is the distance in pixels.
    - Sign is positive on the "left" side of the vector p1->p2.
    """
    x0, y0 = point
    x1, y1 = p1
    x2, y2 = p2

    dx = x2 - x1
    dy = y2 - y1
    denom = hypot(dx, dy)
    if denom == 0:
        # Degenerate line; treat as "no distance"
        return 0.0

    # (p2-p1) x (p - p1) divided by |p2-p1|
    return _cross(dx, dy, x0 - x1, y0 - y1) / denom


def oriented_line_sign(point: Point, cfg: ZoneConfig) -> int | None:
    """
    Returns:
    - +1 if point is on the INSIDE side of the door line
    - -1 if point is on the OUTSIDE side of the door line
    - None if:
        - line isn't configured
        - inside_test_point isn't configured
        - point is within neutral_band_px of the line
        - inside_test_point is invalid (on the line)

    NOTE: This is the primitive used for directional crossing (entry vs exit).
    """
    if (
        cfg.entry_line_p1 is None
        or cfg.entry_line_p2 is None
        or cfg.inside_test_point is None
    ):
        return None

    inside_dist = signed_distance_to_line(
        cfg.inside_test_point, cfg.entry_line_p1, cfg.entry_line_p2
    )
    # If your inside_test_point is on the line, we can't orient the line.
    if abs(inside_dist) < 1e-6:
        return None

    d = signed_distance_to_line(point, cfg.entry_line_p1, cfg.entry_line_p2)
    if abs(d) <= cfg.neutral_band_px:
        return None

    # Same sign as inside_dist => inside side
    return 1 if (d * inside_dist) > 0 else -1


def is_in_gate(point: Point, cfg: ZoneConfig) -> bool:
    """
    Gate is optional. If not provided, we treat everything as "in gate".
    """
    if cfg.gate is None or len(cfg.gate) < 3:
        return True
    return point_in_polygon(point, cfg.gate)


def classify_zone(point: Point, cfg: ZoneConfig) -> Zone:
    """
    Classify a point into INSIDE/OUTSIDE/UNKNOWN.

    Priority:
    1) Masks -> UNKNOWN (ignore)
    2) Inside polygon -> INSIDE
    3) Outside polygon -> OUTSIDE
    4) Fallback to door line side if configured
    5) UNKNOWN
    """
    if _in_any_polygon(point, cfg.masks):
        return Zone.UNKNOWN

    if cfg.inside and point_in_polygon(point, cfg.inside):
        return Zone.INSIDE

    if cfg.outside and point_in_polygon(point, cfg.outside):
        return Zone.OUTSIDE

    # If polygons don't classify it, fallback to line side (if available).
    sign = oriented_line_sign(point, cfg)
    if sign == 1:
        return Zone.INSIDE
    if sign == -1:
        return Zone.OUTSIDE

    return Zone.UNKNOWN


def validate_zone_config(cfg: ZoneConfig) -> tuple[list[str], list[str]]:
    """
    Returns (errors, warnings).

    Errors => job should fail (calibration unusable).
    Warnings => job can run, but results may be unreliable.
    """
    errors: list[str] = []
    warnings: list[str] = []

    has_polygons = bool(cfg.inside) or bool(cfg.outside)
    has_line_any = (cfg.entry_line_p1 is not None) or (cfg.entry_line_p2 is not None)
    has_line_full = (
        cfg.entry_line_p1 is not None
        and cfg.entry_line_p2 is not None
        and cfg.inside_test_point is not None
    )

    if not has_polygons and not has_line_full:
        errors.append(
            "Calibration must include inside/outside polygons OR entry_line + inside_test_point"
        )

    # Line validity checks
    if has_line_any and (cfg.entry_line_p1 is None or cfg.entry_line_p2 is None):
        errors.append("entry_line must include both p1 and p2")

    if cfg.entry_line_p1 and cfg.entry_line_p2:
        if cfg.entry_line_p1 == cfg.entry_line_p2:
            errors.append("entry_line p1 and p2 cannot be identical")
        if cfg.inside_test_point is None:
            warnings.append(
                "inside_test_point missing: door line orientation disabled (line crossing won't work)"
            )
        else:
            d = signed_distance_to_line(
                cfg.inside_test_point, cfg.entry_line_p1, cfg.entry_line_p2
            )
            if abs(d) < 1e-6:
                errors.append(
                    "inside_test_point lies on entry_line (cannot orient inside/outside side)"
                )

    # Helpful warnings (not fatal)
    if (
        cfg.inside
        and cfg.inside_test_point
        and not point_in_polygon(cfg.inside_test_point, cfg.inside)
    ):
        warnings.append(
            "inside_test_point is NOT inside inside_polygon (check calibration)"
        )

    return errors, warnings
