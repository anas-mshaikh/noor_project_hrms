from __future__ import annotations

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

    Supported approaches:

    A) Polygons:
       - inside polygon
       - outside polygon
       classify_zone() uses these directly.

    B) Line + inside_test_point:
       - entry_line_p1, entry_line_p2
       - inside_test_point (a point you KNOW is inside)
       classify_zone() uses which side of the line you're on.
       The 'neutral_band_px' produces UNKNOWN near the line to reduce flicker.

    You can provide BOTH polygons and a line. In that case:
    - polygons decide the zone
    - line is mainly used by the event engine to validate direction

    gate (optional):
      A polygon around the actual doorway. If provided, the event engine only
      trusts line crossings that occur near this region.

    masks (optional):
      Any point inside a mask polygon is treated as UNKNOWN.
    """

    inside: Polygon | None = None
    outside: Polygon | None = None

    entry_line_p1: Point | None = None
    entry_line_p2: Point | None = None
    inside_test_point: Point | None = None

    neutral_band_px: float = 10.0

    gate: Polygon | None = None
    masks: Polygons = field(default_factory=list)

    @classmethod
    def from_calibration_json(cls, data: dict[str, Any]) -> "ZoneConfig":
        """
        Parse cameras.calibration_json.

        We accept a few aliases so your frontend can evolve without breaking the worker.

        Example payload:
        {
          "inside_polygon": [[0,0],[200,0],[200,300],[0,300]],
          "outside_polygon": [[-200,0],[0,0],[0,300],[-200,300]],
          "entry_line": {"p1":[0,0], "p2":[0,300]},
          "inside_test_point": [100,150],
          "neutral_band_px": 12,
          "gate_polygon": [[-50,0],[50,0],[50,300],[-50,300]],
          "mask_polygons": [
            [[500,500],[700,500],[700,700],[500,700]]
          ]
        }
        """
        inside = data.get("inside_polygon", data.get("inside"))
        outside = data.get("outside_polygon", data.get("outside"))
        gate = data.get("gate_polygon", data.get("gate"))
        masks = data.get("mask_polygons", data.get("masks"))

        entry_line = data.get("entry_line")
        p1 = p2 = None
        inside_test_point = data.get("inside_test_point")

        if entry_line is not None:
            # Accept either {"p1": [...], "p2": [...]} or [[...], [...]]
            if isinstance(entry_line, dict):
                p1 = _as_point(entry_line.get("p1"))
                p2 = _as_point(entry_line.get("p2"))
            else:
                pts = _as_polygon(entry_line)
                if len(pts) != 2:
                    raise ValueError("entry_line must have exactly 2 points")
                p1, p2 = pts[0], pts[1]

        neutral_band_px = float(data.get("neutral_band_px", 10.0))

        return cls(
            inside=_as_polygon(inside) or None,
            outside=_as_polygon(outside) or None,
            entry_line_p1=p1,
            entry_line_p2=p2,
            inside_test_point=_as_point(inside_test_point)
            if inside_test_point
            else None,
            neutral_band_px=neutral_band_px,
            gate=_as_polygon(gate) or None,
            masks=_as_polygons(masks),
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
