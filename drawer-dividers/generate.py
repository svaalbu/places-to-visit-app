#!/usr/bin/env python3
"""Honeycomb drawer dividers for a Bambu Lab P2S, PLA only.

The grid is an original half-lap design inspired by light, fast-printing
drawer dividers: open honeycomb walls, pieces that fit a 256 mm bed, and
joints you can press together by hand. It is sized for a drawer whose clear
inside is 745 mm wide, 310 mm deep, and 140 mm high.

Walls lie flat on the bed. Rails run left to right and have slots from the
top. Struts run front to back and have slots from the bottom. Where a wall
is longer than the bed, a dovetail and a drop-in pin join the pieces.

Edit the block under "Drawer and grid" and run:

    python3 generate.py
"""

from __future__ import annotations

import json
import math
import zipfile
from collections import Counter
from pathlib import Path
from xml.sax.saxutils import escape

import cadquery as cq

ROOT = Path(__file__).resolve().parent
STL_DIR = ROOT / "stl"
PLATE_DIR = ROOT / "plates"
PREVIEW_DIR = ROOT / "preview"

# --- Drawer and grid -------------------------------------------------------
# Clear inside of the drawer, millimetres.
DRAWER_W = 745.0
DRAWER_D = 310.0
DRAWER_H = 140.0
# Cells across the width, and cells from front to back.
COLS = 4
ROWS = 2
# How far the plastic stops short of each drawer wall.
SIDE_CLEAR = 1.0
# Standing height of the dividers. The drawer is 140 mm, so 20 mm stays
# clear for grabbing things and for the drawer front.
WALL_H = 120.0
WALL_T = 3.2

# --- Joints, tuned for PLA on a 0.4 mm nozzle -----------------------------
SLOT_CLEAR = 0.60
SLOT_EXTRA_DEPTH = 0.40
SLOT_MOUTH = 4.0
SLOT_MOUTH_WIDEN = 1.4
DOVETAIL_DEPTH = 12.0
DOVETAIL_NECK = 22.0
DOVETAIL_TIP = 36.0
# Width added to the socket. The socket is shorter than a true offset, so
# this has to be generous or the dovetail tip fouls the sloped wall.
DOVETAIL_CLEAR = 1.20
DOVETAIL_DEPTH_CLEAR = 0.55
BUTT_GAP = 0.30
PIN_SLOT_W = 6.4
PIN_SLOT_D = 28.0
PIN_W = 5.70
PIN_DROP = 24.5
# 15 layers at 0.20 mm, so the pin sits just inside the 3.2 mm wall.
PIN_T = 3.0
FINGER_W = 28.0
FINGER_D = 12.0
TICK_W = 3.6
TICK_D = 3.4
TICK_GAP = 2.6

# --- Honeycomb -------------------------------------------------------------
HEX_R = 7.4
HEX_RIB = 3.5
HEX_BORDER = 8.0
FEATURE_MARGIN = 6.5

# --- Bed -------------------------------------------------------------------
BED = 256.0
MAX_LEN = 214.0
MIN_LEN = 72.0
# Joints stay this far from a slot center so a solid bridge remains
# between the dovetail and the half-lap.
CUT_KEEPOUT = 32.0
PLATE_MARGIN = 6.0
PLATE_GAP = 4.0

PLA_DENSITY = 1.24  # g/cm^3
PLA_COLOR = "#C4B8A5"


def centers_for(span: float, count: int, thickness: float) -> tuple[list[float], float]:
    """Evenly space `count` walls so every gap, including both ends, matches."""
    gaps = count + 1
    clear = (span - count * thickness) / gaps
    pitch = clear + thickness
    first = clear + thickness / 2.0
    return [first + i * pitch for i in range(count)], clear


def plan_cuts(
    length: float,
    obstacles: list[float],
    keepout: float,
    max_len: float,
    min_len: float,
) -> list[float]:
    """Split [0, length] into pieces that fit the bed and miss the slots."""
    count = max(1, math.ceil((length - 1e-6) / max_len))
    if count == 1:
        return [0.0, length]
    last_error = "could not split the wall"
    for extra in range(0, 4):
        try:
            return _plan_cuts(length, obstacles, keepout, max_len, min_len, count + extra)
        except RuntimeError as exc:
            last_error = str(exc)
    raise SystemExit(last_error)


def _plan_cuts(
    length: float,
    obstacles: list[float],
    keepout: float,
    max_len: float,
    min_len: float,
    count: int,
) -> list[float]:
    def safe(x: float, lo: float, hi: float) -> bool:
        if x < lo - 1e-6 or x > hi + 1e-6:
            return False
        return all(abs(x - obstacle) >= keepout - 1e-6 for obstacle in obstacles)

    cuts = [0.0]
    for index, target in enumerate(length * k / count for k in range(1, count)):
        remaining = count - (index + 1)
        lo = max(cuts[-1] + min_len, length - remaining * max_len)
        hi = min(cuts[-1] + max_len, length - remaining * min_len)
        if lo > hi + 1e-6:
            raise RuntimeError(f"No room to split a {length:.1f} mm wall")
        best = None
        best_dist = 1e9
        steps = int(round((hi - lo) / 0.25))
        for step in range(steps + 1):
            x = lo + step * 0.25
            if not safe(x, lo, hi):
                continue
            dist = abs(x - target)
            # Prefer a cut that keeps neighbouring pieces similar.
            balance = abs((x - cuts[-1]) - (length / count)) * 0.15
            score = dist + balance
            if score < best_dist:
                best_dist = score
                best = x
        if best is None:
            raise RuntimeError(
                f"Cannot place a joint near {target:.1f} mm without hitting a slot"
            )
        cuts.append(best)
    cuts.append(length)
    for start, end in zip(cuts, cuts[1:]):
        piece = end - start
        if piece > max_len + 0.2 or piece < min_len - 0.2:
            raise RuntimeError(f"Split produced a {piece:.1f} mm piece")
        for obstacle in obstacles:
            if start + 1e-6 < obstacle < end - 1e-6:
                continue
            if abs(obstacle - start) < 1e-6 or abs(obstacle - end) < 1e-6:
                raise RuntimeError("A slot landed on a joint")
    return cuts


def hexagon(cx: float, cy: float, radius: float) -> list[tuple[float, float]]:
    """Pointy-top hexagon, center to vertex = radius."""
    return [
        (
            cx + radius * math.cos(math.radians(90 + 60 * i)),
            cy + radius * math.sin(math.radians(90 + 60 * i)),
        )
        for i in range(6)
    ]


def hex_centers(length: float, height: float) -> list[tuple[float, float]]:
    dx = math.sqrt(3) * HEX_R + HEX_RIB
    dy = 1.5 * HEX_R + HEX_RIB * math.sqrt(3) / 2.0
    centers = []
    row = 0
    y = HEX_BORDER + HEX_R
    while y <= height - HEX_BORDER - HEX_R * 0.2:
        offset = 0.0 if row % 2 == 0 else dx / 2.0
        x = HEX_BORDER + HEX_R + offset
        while x <= length - HEX_BORDER - HEX_R * 0.2:
            centers.append((x, y))
            x += dx
        row += 1
        y += dy
    return centers


def overlaps_rect(
    pts: list[tuple[float, float]], rect: tuple[float, float, float, float]
) -> bool:
    left, bottom, right, top = rect
    for x, y in pts:
        if left <= x <= right and bottom <= y <= top:
            return True
    return False


def inside_rect(
    pts: list[tuple[float, float]], rect: tuple[float, float, float, float]
) -> bool:
    left, bottom, right, top = rect
    return all(left <= x <= right and bottom <= y <= top for x, y in pts)


def prism(pts: list[tuple[float, float]], z0: float = 0.0, height: float = WALL_T):
    solid = cq.Workplane("XY").polyline(pts).close().extrude(height)
    if abs(z0) > 1e-9:
        solid = solid.translate((0, 0, z0))
    return solid


def cutter(pts: list[tuple[float, float]]):
    return prism(pts, z0=-0.6, height=WALL_T + 1.2)


def fuse(parts: list):
    acc = parts[0]
    for part in parts[1:]:
        acc = acc.union(part)
    return acc


def carve(body, holes: list):
    if not holes:
        return body
    tool = holes[0]
    for hole in holes[1:]:
        tool = tool.union(hole)
    return body.cut(tool)


class Piece:
    def __init__(
        self,
        name: str,
        kind: str,
        start: float,
        end: float,
        slots: list[float],
        female: bool,
        male: bool,
        pips: int,
        notch: float | None,
        copies: int,
    ) -> None:
        self.name = name
        self.kind = kind
        self.start = start
        self.end = end
        self.slots = slots
        self.female = female
        self.male = male
        self.pips = pips
        self.notch = notch
        self.copies = copies
        self.shape = None
        self.mesh = None
        self.footprint = (0.0, 0.0)

    @property
    def length(self) -> float:
        return self.end - self.start


def slot_polygon(center: float, width: float, open_top: bool) -> list[tuple[float, float]]:
    half = width / 2.0
    depth = WALL_H / 2.0 + SLOT_EXTRA_DEPTH
    if open_top:
        mouth = WALL_H
        end = WALL_H - depth
        return [
            (center - half - SLOT_MOUTH_WIDEN, mouth + 0.8),
            (center + half + SLOT_MOUTH_WIDEN, mouth + 0.8),
            (center + half, mouth - SLOT_MOUTH),
            (center + half, end),
            (center - half, end),
            (center - half, mouth - SLOT_MOUTH),
        ]
    end = depth
    return [
        (center - half - SLOT_MOUTH_WIDEN, -0.8),
        (center + half + SLOT_MOUTH_WIDEN, -0.8),
        (center + half, SLOT_MOUTH),
        (center + half, end),
        (center - half, end),
        (center - half, SLOT_MOUTH),
    ]


def dovetail_polygon(neck_x: float, direction: int, neck: float, tip: float, depth: float):
    """Trapezoid. direction +1 grows toward +x, -1 grows toward -x."""
    mid = WALL_H / 2.0
    tip_x = neck_x + direction * depth
    return [
        (neck_x, mid - neck / 2.0),
        (tip_x, mid - tip / 2.0),
        (tip_x, mid + tip / 2.0),
        (neck_x, mid + neck / 2.0),
    ]


def build_piece(piece: Piece) -> cq.Workplane:
    length = piece.length
    u0 = BUTT_GAP / 2.0 if piece.female else 0.0
    u1 = length - BUTT_GAP / 2.0 if piece.male else length
    parts = [prism([(u0, 0.0), (u1, 0.0), (u1, WALL_H), (u0, WALL_H)])]
    holes = []

    if piece.male:
        parts.append(
            prism(
                dovetail_polygon(
                    u1 - 0.25,
                    +1,
                    DOVETAIL_NECK,
                    DOVETAIL_TIP,
                    DOVETAIL_DEPTH + 0.25,
                )
            )
        )
    if piece.female:
        pockets = DOVETAIL_DEPTH - BUTT_GAP + DOVETAIL_DEPTH_CLEAR
        holes.append(
            cutter(
                dovetail_polygon(
                    u0 - 0.4,
                    +1,
                    DOVETAIL_NECK + DOVETAIL_CLEAR,
                    DOVETAIL_TIP + DOVETAIL_CLEAR,
                    pockets + 0.4,
                )
            )
        )

    open_top = piece.kind == "rail"
    slot_w = WALL_T + SLOT_CLEAR
    for slot in piece.slots:
        local = slot - piece.start
        holes.append(cutter(slot_polygon(local, slot_w, open_top)))

    # Pin groove is split across the joint. Gravity keeps the pin in it.
    if piece.male:
        holes.append(
            cutter(
                [
                    (length - PIN_SLOT_W / 2.0, WALL_H - PIN_SLOT_D),
                    (length + 0.4, WALL_H - PIN_SLOT_D),
                    (length + 0.4, WALL_H + 0.6),
                    (length - PIN_SLOT_W / 2.0, WALL_H + 0.6),
                ]
            )
        )
    if piece.female:
        holes.append(
            cutter(
                [
                    (-0.4, WALL_H - PIN_SLOT_D),
                    (PIN_SLOT_W / 2.0, WALL_H - PIN_SLOT_D),
                    (PIN_SLOT_W / 2.0, WALL_H + 0.6),
                    (-0.4, WALL_H + 0.6),
                ]
            )
        )

    if piece.notch is not None:
        cx = piece.notch - piece.start
        holes.append(
            cutter(
                [
                    (cx - FINGER_W / 2.0, WALL_H - FINGER_D),
                    (cx + FINGER_W / 2.0, WALL_H - FINGER_D),
                    (cx + FINGER_W / 2.0, WALL_H + 0.8),
                    (cx - FINGER_W / 2.0, WALL_H + 0.8),
                ]
            )
        )

    # Count ticks from the left. They replace raised bumps so the part
    # stays exactly WALL_H tall and two of them fit on one plate.
    tick_x = 14.0
    for _ in range(piece.pips):
        holes.append(
            cutter(
                [
                    (tick_x, WALL_H - TICK_D),
                    (tick_x + TICK_W, WALL_H - TICK_D),
                    (tick_x + TICK_W, WALL_H + 0.6),
                    (tick_x, WALL_H + 0.6),
                ]
            )
        )
        tick_x += TICK_W + TICK_GAP

    keepouts = []
    for slot in piece.slots:
        local = slot - piece.start
        keepouts.append(
            (
                local - slot_w / 2.0 - FEATURE_MARGIN,
                -FEATURE_MARGIN,
                local + slot_w / 2.0 + FEATURE_MARGIN,
                WALL_H + FEATURE_MARGIN,
            )
        )
    if piece.male:
        keepouts.append(
            (
                u1 - FEATURE_MARGIN,
                WALL_H / 2.0 - DOVETAIL_TIP / 2.0 - FEATURE_MARGIN,
                length + DOVETAIL_DEPTH + 2.0,
                WALL_H / 2.0 + DOVETAIL_TIP / 2.0 + FEATURE_MARGIN,
            )
        )
        keepouts.append(
            (length - PIN_SLOT_W / 2.0 - FEATURE_MARGIN, WALL_H - PIN_SLOT_D - FEATURE_MARGIN, length + 2.0, WALL_H + 2.0)
        )
    if piece.female:
        keepouts.append(
            (
                -2.0,
                WALL_H / 2.0 - DOVETAIL_TIP / 2.0 - FEATURE_MARGIN,
                u0 + DOVETAIL_DEPTH + FEATURE_MARGIN,
                WALL_H / 2.0 + DOVETAIL_TIP / 2.0 + FEATURE_MARGIN,
            )
        )
        keepouts.append(
            (-2.0, WALL_H - PIN_SLOT_D - FEATURE_MARGIN, PIN_SLOT_W / 2.0 + FEATURE_MARGIN, WALL_H + 2.0)
        )
    if piece.notch is not None:
        cx = piece.notch - piece.start
        keepouts.append(
            (
                cx - FINGER_W / 2.0 - FEATURE_MARGIN,
                WALL_H - FINGER_D - FEATURE_MARGIN,
                cx + FINGER_W / 2.0 + FEATURE_MARGIN,
                WALL_H + 2.0,
            )
        )
    tick_x = 14.0
    for _ in range(piece.pips):
        keepouts.append((tick_x - 2.5, WALL_H - TICK_D - 4.0, tick_x + TICK_W + 2.5, WALL_H + 2.0))
        tick_x += TICK_W + TICK_GAP

    safe = (u0 + HEX_BORDER, HEX_BORDER, u1 - HEX_BORDER, WALL_H - HEX_BORDER)
    for cx, cy in hex_centers(length + DOVETAIL_DEPTH, WALL_H):
        pts = hexagon(cx, cy, HEX_R)
        if not inside_rect(pts, safe):
            continue
        if any(overlaps_rect(pts, rect) for rect in keepouts):
            continue
        holes.append(cutter(pts))

    return carve(fuse(parts), holes)


def build_pin() -> cq.Workplane:
    """Rectangular pin. Printed on its side: the long drop is X, thickness is Z."""
    lead = 1.3
    body = prism(
        [
            (lead, 0.0),
            (PIN_DROP, 0.0),
            (PIN_DROP, PIN_W),
            (lead, PIN_W),
        ],
        height=PIN_T,
    )
    nose = prism(
        [
            (0.0, 0.55),
            (lead, 0.0),
            (lead, PIN_W),
            (0.0, PIN_W - 0.55),
        ],
        height=PIN_T,
    )
    return body.union(nose)


def build_test_pair() -> tuple[cq.Workplane, cq.Workplane]:
    """One crossing, same slot fit as the real grid, short enough to print first."""
    length = 96.0
    mid = length / 2.0

    def plain(open_top: bool) -> cq.Workplane:
        body = prism([(0.0, 0.0), (length, 0.0), (length, WALL_H), (0.0, WALL_H)])
        hole = cutter(slot_polygon(mid, WALL_T + SLOT_CLEAR, open_top))
        safe = (HEX_BORDER, HEX_BORDER, length - HEX_BORDER, WALL_H - HEX_BORDER)
        keep = (
            mid - (WALL_T + SLOT_CLEAR) / 2.0 - FEATURE_MARGIN,
            -5.0,
            mid + (WALL_T + SLOT_CLEAR) / 2.0 + FEATURE_MARGIN,
            WALL_H + 5.0,
        )
        holes = [hole]
        for cx, cy in hex_centers(length, WALL_H):
            pts = hexagon(cx, cy, HEX_R)
            if inside_rect(pts, safe) and not overlaps_rect(pts, keep):
                holes.append(cutter(pts))
        return carve(body, holes)

    return plain(True), plain(False)


def tessellate(shape: cq.Workplane) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]:
    verts, tris = shape.val().tessellate(0.08, 0.12)
    raw = [(float(v.x), float(v.y), float(v.z)) for v in verts]
    # Tessellation does not reuse vertex indices, so weld before the
    # closed-mesh check. 0.001 mm is far below anything a 0.4 mm nozzle prints.
    scale = 1000.0
    index_of: dict[tuple[int, int, int], int] = {}
    points: list[tuple[float, float, float]] = []
    remap: list[int] = []
    for x, y, z in raw:
        key = (round(x * scale), round(y * scale), round(z * scale))
        index = index_of.get(key)
        if index is None:
            index = len(points)
            index_of[key] = index
            points.append((x, y, z))
        remap.append(index)
    faces = []
    for a, b, c in tris:
        aa, bb, cc = remap[int(a)], remap[int(b)], remap[int(c)]
        if len({aa, bb, cc}) == 3:
            faces.append((aa, bb, cc))
    return points, faces


def boundary_edges(tris: list[tuple[int, int, int]]) -> int:
    edges: Counter[tuple[int, int]] = Counter()
    for a, b, c in tris:
        for edge in ((a, b), (b, c), (c, a)):
            edges[tuple(sorted(edge))] += 1
    return sum(1 for count in edges.values() if count != 2)


def normalize_mesh(verts, tris):
    min_x = min(v[0] for v in verts)
    min_y = min(v[1] for v in verts)
    min_z = min(v[2] for v in verts)
    moved = [(x - min_x, y - min_y, z - min_z) for x, y, z in verts]
    max_x = max(v[0] for v in moved)
    max_y = max(v[1] for v in moved)
    max_z = max(v[2] for v in moved)
    return moved, tris, (max_x, max_y, max_z)


def write_stl(path: Path, verts, tris) -> None:
    import struct

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(b"\0" * 80)
        handle.write(struct.pack("<I", len(tris)))
        for a, b, c in tris:
            ax, ay, az = verts[a]
            bx, by, bz = verts[b]
            cx, cy, cz = verts[c]
            ux, uy, uz = bx - ax, by - ay, bz - az
            vx, vy, vz = cx - ax, cy - ay, cz - az
            nx = uy * vz - uz * vy
            ny = uz * vx - ux * vz
            nz = ux * vy - uy * vx
            norm = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
            handle.write(
                struct.pack(
                    "<12fH",
                    nx / norm,
                    ny / norm,
                    nz / norm,
                    ax,
                    ay,
                    az,
                    bx,
                    by,
                    bz,
                    cx,
                    cy,
                    cz,
                    0,
                )
            )


def volume_of(shape: cq.Workplane) -> float:
    return float(shape.val().Volume())


def shape_gap(a: cq.Workplane, b: cq.Workplane) -> float:
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape

    measure = BRepExtrema_DistShapeShape(a.val().wrapped, b.val().wrapped)
    measure.Perform()
    return float(measure.Value())


def intersection_volume(a: cq.Workplane, b: cq.Workplane) -> float:
    try:
        hit = a.intersect(b)
        solid = hit.val()
        if solid is None:
            return 0.0
        return max(0.0, float(solid.Volume()))
    except Exception:
        return 0.0


def place_rail(shape: cq.Workplane, x0: float, y_center: float) -> cq.Workplane:
    # Local X length -> world X, local Y height -> world Z, thickness -> Y.
    moved = shape.rotate((0, 0, 0), (1, 0, 0), 90)
    return moved.translate((x0, y_center + WALL_T / 2.0, 0))


def place_strut(shape: cq.Workplane, x_center: float, y0: float) -> cq.Workplane:
    moved = shape.rotate((0, 0, 0), (1, 0, 0), 90)
    moved = moved.rotate((0, 0, 0), (0, 0, 1), 90)
    return moved.translate((x_center - WALL_T / 2.0, y0, 0))


def bbox(shape: cq.Workplane):
    box = shape.val().BoundingBox()
    return box.xmin, box.xmax, box.ymin, box.ymax, box.zmin, box.zmax


def notch_for(start: float, end: float, slots: list[float], candidates: list[float]) -> float | None:
    """Pick a finger-notch center that sits fully on this piece, clear of slots."""
    margin = FINGER_W / 2.0 + 16.0
    blocked = []
    for slot in slots:
        blocked.append((slot - WALL_T, slot + WALL_T))
    # Keep the notch off the dovetail ends as well.
    blocked.append((start - 50.0, start + 24.0))
    blocked.append((end - 24.0, end + 50.0))

    def clear(center: float) -> bool:
        if center - margin < start or center + margin > end:
            return False
        half = FINGER_W / 2.0 + FEATURE_MARGIN
        return all(center + half < lo or center - half > hi for lo, hi in blocked)

    for center in candidates:
        if clear(center):
            return center
    # Fall back to the middle of the piece when the middle is open.
    middle = (start + end) / 2.0
    if clear(middle):
        return middle
    return None


def pack(items: list[dict]) -> list[list[dict]]:
    """Shelf-pack footprints onto 256 mm plates. Each item is used once."""
    usable = BED - 2 * PLATE_MARGIN
    pending = sorted(items, key=lambda item: max(item["w"], item["h"]), reverse=True)
    plates = []
    while pending:
        placed = []
        x = 0.0
        y = 0.0
        row_h = 0.0
        skipped = []
        for item in pending:
            fits = None
            for rotated in (False, True):
                w = item["h"] if rotated else item["w"]
                h = item["w"] if rotated else item["h"]
                if w > usable + 1e-6 or h > usable + 1e-6:
                    continue
                if x + w <= usable + 0.3 and y + h <= usable + 0.3:
                    fits = (x, y, w, h, rotated)
                    break
                new_y = y + row_h + PLATE_GAP if x > 0 else y
                if x > 0 and new_y + h <= usable + 0.3 and w <= usable + 0.3:
                    fits = (0.0, new_y, w, h, rotated)
                    break
            if fits is None:
                skipped.append(item)
                continue
            px, py, w, h, rotated = fits
            placed.append({**item, "px": px, "py": py, "pw": w, "ph": h, "rotated": rotated})
            if py > y + 1e-6:
                x = 0.0
                y = py
                row_h = 0.0
            x = px + w + PLATE_GAP
            row_h = max(row_h, h)
        if not placed:
            name = pending[0]["name"]
            raise SystemExit(f"{name} does not fit on a {BED:.0f} mm plate")
        plates.append(placed)
        pending = skipped
    return plates


def rotate_mesh_z(verts, turns: int):
    """90-degree turns about Z, then shift back to the positive quadrant."""
    points = verts
    for _ in range(turns % 4):
        points = [(-y, x, z) for x, y, z in points]
    min_x = min(p[0] for p in points)
    min_y = min(p[1] for p in points)
    min_z = min(p[2] for p in points)
    return [(x - min_x, y - min_y, z - min_z) for x, y, z in points]


def project_settings() -> dict:
    filaments = ["Bambu PLA Basic @BBL P2S"]
    return {
        "name": "project_settings",
        "printer_model": "Bambu Lab P2S",
        "printer_variant": "0.4",
        "nozzle_diameter": ["0.4"],
        "printer_settings_id": "Bambu Lab P2S 0.4 nozzle",
        "print_settings_id": "0.20mm Standard @BBL P2S",
        "filament_settings_id": filaments,
        "filament_colour": [PLA_COLOR],
        "filament_type": ["PLA"],
        "filament_diameter": ["1.75"],
        "filament_self_index": ["1"],
        "filament_extruder_variant": ["Direct Drive Standard"],
        "extruder_variant_list": [
            "Direct Drive Standard,Direct Drive High Flow,Direct Drive E3D High Flow"
        ],
        "inherits_group": [
            "0.20mm Standard @BBL P2S",
            *filaments,
            "Bambu Lab P2S 0.4 nozzle",
        ],
        "different_settings_to_system": ["", "filament_colour", ""],
    }


def plate_columns(count: int) -> int:
    """Match Bambu Studio's plate grid: columns are round(sqrt(count)), rounded up."""
    value = math.sqrt(count)
    rounded = math.floor(value + 0.5)
    if value > rounded:
        return int(rounded) + 1
    return max(1, int(rounded))


def plate_origin(index: int, count: int) -> tuple[float, float]:
    """World offset of a plate. Studio lays plates on a grid with a 20% gap."""
    cols = plate_columns(count)
    stride = BED * 1.2
    col = index % cols
    row = index // cols
    return col * stride, -row * stride


def write_3mf(path: Path, plates: list[dict], title: str) -> None:
    def mesh_xml(verts, tris) -> str:
        v_lines = [f'<vertex x="{x:.4f}" y="{y:.4f}" z="{z:.4f}"/>' for x, y, z in verts]
        t_lines = [f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in tris]
        return (
            "<mesh>"
            f"<vertices>{''.join(v_lines)}</vertices>"
            f"<triangles>{''.join(t_lines)}</triangles>"
            "</mesh>"
        )

    object_xml = []
    build_items = []
    model_objects = []
    plate_xml = []
    assemble_items = []
    object_id = 1
    plate_count = len(plates)
    if plate_count < 1:
        raise SystemExit("No plates to write")
    for plate_index, plate in enumerate(plates):
        origin_x, origin_y = plate_origin(plate_index, plate_count)
        instances = []
        for obj in plate["objects"]:
            verts, tris = obj["mesh"]
            if boundary_edges(tris) != 0:
                raise SystemExit(f"{obj['name']} mesh is not closed")
            object_xml.append(
                f'<object id="{object_id}" name="{escape(obj["name"])}" type="model">'
                f"{mesh_xml(verts, tris)}</object>"
            )
            # The P2S bed origin is the front-left corner. Later plates sit on
            # Studio's grid: each step is 1.2 bed widths, and rows go down in Y.
            x = obj["x"] + origin_x
            y = obj["y"] + origin_y
            transform = f"1 0 0 0 1 0 0 0 1 {x:.4f} {y:.4f} 0"
            build_items.append(
                f'<item objectid="{object_id}" transform="{transform}" printable="1"/>'
            )
            model_objects.append(
                f'''  <object id="{object_id}">
    <metadata key="name" value="{escape(obj["name"])}"/>
    <metadata key="extruder" value="1"/>
    <part id="{object_id}" subtype="normal_part">
      <metadata key="name" value="{escape(obj["name"])}"/>
      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>
      <mesh_stat face_count="{len(tris)}" edges_fixed="0" degenerate_facets="0" facets_removed="0" facets_reversed="0" backwards_edges="0"/>
    </part>
  </object>'''
            )
            instances.append(
                f'''    <model_instance>
      <metadata key="object_id" value="{object_id}"/>
      <metadata key="instance_id" value="0"/>
      <metadata key="identify_id" value="{object_id}"/>
    </model_instance>'''
            )
            assemble_items.append(
                f'<assemble_item object_id="{object_id}" instance_id="0" '
                f'transform="{transform}" offset="0 0 0"/>'
            )
            object_id += 1
        plate_xml.append(
            f'''  <plate>
    <metadata key="plater_id" value="{plate_index + 1}"/>
    <metadata key="plater_name" value="{escape(plate["name"])}"/>
    <metadata key="locked" value="false"/>
{chr(10).join(instances)}
  </plate>'''
        )

    model = f'''<?xml version="1.0" encoding="UTF-8"?>
<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">
  <metadata name="Application">BambuStudio-01.10.02.75</metadata>
  <metadata name="BambuStudio:3mfVersion">1</metadata>
  <metadata name="Title">{escape(title)}</metadata>
  <resources>
    {''.join(object_xml)}
  </resources>
  <build>
    {''.join(build_items)}
  </build>
</model>
'''
    model_settings = f'''<?xml version="1.0" encoding="UTF-8"?>
<config>
{chr(10).join(model_objects)}
{chr(10).join(plate_xml)}
  <assemble>
    {''.join(assemble_items)}
  </assemble>
</config>
'''
    content_types = '''<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
  <Default Extension="config" ContentType="text/xml"/>
</Types>
'''
    rels = '''<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>
'''
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("3D/3dmodel.model", model)
        zf.writestr("Metadata/project_settings.config", json.dumps(project_settings(), indent=2))
        zf.writestr("Metadata/model_settings.config", model_settings)


def _check_project(path: Path, plate_count: int) -> None:
    """The project is one file, and each plate owns a distinct set of parts."""
    import xml.etree.ElementTree as ET

    with zipfile.ZipFile(path) as archive:
        settings = ET.fromstring(archive.read("Metadata/model_settings.config"))
        model = ET.fromstring(archive.read("3D/3dmodel.model"))
    ns = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
    plates = settings.findall("plate")
    if len(plates) != plate_count:
        raise SystemExit(f"Project has {len(plates)} plates, expected {plate_count}")
    assigned = []
    for plate in plates:
        ids = [
            node.attrib["value"]
            for node in plate.findall("model_instance/metadata")
            if node.attrib.get("key") == "object_id"
        ]
        if not ids:
            raise SystemExit("A plate has no parts")
        assigned.extend(ids)
    if len(assigned) != len(set(assigned)):
        raise SystemExit("A part is on more than one plate")
    build_ids = [
        item.attrib["objectid"] for item in model.findall("m:build/m:item", ns)
    ]
    if sorted(build_ids, key=int) != sorted(assigned, key=int):
        raise SystemExit("Plate assignment does not match the model")
    positions = {}
    for item in model.findall("m:build/m:item", ns):
        numbers = [float(part) for part in item.attrib["transform"].split()]
        positions[item.attrib["objectid"]] = (numbers[9], numbers[10])
    # Each part's corner must land on its own plate. The bed origin is the
    # front-left corner, and the next row of plates is below the first.
    for plate_index, plate in enumerate(plates):
        origin_x, origin_y = plate_origin(plate_index, plate_count)
        ids = [
            node.attrib["value"]
            for node in plate.findall("model_instance/metadata")
            if node.attrib.get("key") == "object_id"
        ]
        for object_id in ids:
            x, y = positions[object_id]
            if not (origin_x <= x <= origin_x + BED and origin_y <= y <= origin_y + BED):
                raise SystemExit(
                    f"Part {object_id} at {x:.1f},{y:.1f} is off plate {plate_index + 1}"
                )
    print(f"  {path.name}: {plate_count} plates, {len(assigned)} parts")


def render_layout(path: Path, strut_centers: list[float], rail_centers: list[float], clear_w: float, clear_d: float) -> None:
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch, Rectangle

    fig, ax = plt.subplots(figsize=(12.4, 6.6), dpi=140)
    fig.patch.set_facecolor("#f6f4ef")
    ax.set_facecolor("#f6f4ef")
    ax.set_aspect("equal")
    ax.axis("off")

    ox, oy = 70, 78
    scale = 0.82
    dw, dd = DRAWER_W * scale, DRAWER_D * scale

    ax.add_patch(
        FancyBboxPatch(
            (ox - 8, oy - 8),
            dw + 16,
            dd + 16,
            boxstyle="round,pad=0,rounding_size=10",
            facecolor="#e4e0d8",
            edgecolor="#b7b1a6",
            linewidth=1.2,
        )
    )
    ax.add_patch(
        Rectangle((ox, oy), dw, dd, facecolor="#fbfaf7", edgecolor="#3d3a36", linewidth=1.6)
    )

    def wx(x: float) -> float:
        return ox + x * scale

    def wy(y: float) -> float:
        return oy + y * scale

    for center in rail_centers:
        ax.add_patch(
            Rectangle(
                (wx(SIDE_CLEAR), wy(center - WALL_T / 2.0)),
                (DRAWER_W - 2 * SIDE_CLEAR) * scale,
                WALL_T * scale,
                facecolor="#c4b8a5",
                edgecolor="#5c564e",
                linewidth=0.6,
            )
        )
    for center in strut_centers:
        ax.add_patch(
            Rectangle(
                (wx(center - WALL_T / 2.0), wy(SIDE_CLEAR)),
                WALL_T * scale,
                (DRAWER_D - 2 * SIDE_CLEAR) * scale,
                facecolor="#b7c0b4",
                edgecolor="#5c564e",
                linewidth=0.6,
            )
        )

    ax.annotate(
        "",
        xy=(ox + dw, oy - 28),
        xytext=(ox, oy - 28),
        arrowprops=dict(arrowstyle="<->", color="#3d3a36", lw=1.1),
    )
    ax.text(
        ox + dw / 2,
        oy - 44,
        f"width  {DRAWER_W:.0f} mm",
        ha="center",
        va="center",
        fontsize=11,
        color="#3d3a36",
    )
    ax.annotate(
        "",
        xy=(ox + dw + 28, oy + dd),
        xytext=(ox + dw + 28, oy),
        arrowprops=dict(arrowstyle="<->", color="#3d3a36", lw=1.1),
    )
    ax.text(
        ox + dw + 46,
        oy + dd / 2,
        f"depth  {DRAWER_D:.0f} mm",
        ha="left",
        va="center",
        fontsize=11,
        color="#3d3a36",
        rotation=90,
    )
    ax.set_xlim(20, ox + dw + 120)
    ax.set_ylim(0, oy + dd + 78)
    ax.text(
        ox,
        oy + dd + 46,
        "Drawer dividers",
        ha="left",
        va="center",
        fontsize=18,
        color="#2c2926",
    )
    ax.text(
        ox,
        oy + dd + 22,
        f"{COLS} × {ROWS} compartments   ·   about {clear_w:.0f} × {clear_d:.0f} mm each   ·   walls {WALL_H:.0f} mm tall",
        ha="left",
        va="center",
        fontsize=11,
        color="#5c564e",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def render_parts(path: Path, pieces: list[Piece]) -> None:
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection

    cols = 3
    rows = math.ceil(len(pieces) / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(12.6, 3.6 * rows), dpi=130)
    fig.patch.set_facecolor("#f6f4ef")
    flat_axes = list(axes.ravel()) if rows > 1 else list(axes)
    for ax in flat_axes:
        ax.set_facecolor("#f6f4ef")
        ax.axis("off")
    for ax, piece in zip(flat_axes, pieces):
        verts, tris = piece.mesh
        polys = []
        for a, b, c in tris:
            p0, p1, p2 = verts[a], verts[b], verts[c]
            nz = (p1[0] - p0[0]) * (p2[1] - p0[1]) - (p1[1] - p0[1]) * (p2[0] - p0[0])
            if nz > 0.4:
                polys.append([(p0[0], p0[1]), (p1[0], p1[1]), (p2[0], p2[1])])
        color = "#c4b8a5" if piece.kind == "rail" else "#b7c0b4"
        ax.add_collection(PolyCollection(polys, facecolor=color, edgecolor="none", linewidths=0))
        w, h, _ = piece.footprint
        ax.set_xlim(-8, w + 8)
        ax.set_ylim(-10, h + 16)
        ax.set_aspect("equal")
        kind = "left-right rail" if piece.kind == "rail" else "front-back strut"
        ax.set_title(
            f"{piece.name}   ×{piece.copies}\n{kind}   {w:.0f} × {h:.0f} mm",
            fontsize=10,
            color="#2c2926",
            loc="left",
        )
    fig.suptitle(
        "Print these flat. The small cuts on the top edge are the assembly order.",
        fontsize=13,
        color="#2c2926",
        x=0.02,
        ha="left",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def render_iso(path: Path, solids: list[tuple[cq.Workplane, str]]) -> None:
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    fig = plt.figure(figsize=(11.2, 7.2), dpi=130)
    fig.patch.set_facecolor("#f6f4ef")
    ax = fig.add_subplot(111, projection="3d")
    ax.set_facecolor("#f6f4ef")
    colors = {"rail": "#c4b8a5", "strut": "#aeb8ab", "pin": "#8d8478"}
    for shape, kind in solids:
        verts, tris = tessellate(shape)
        polys = [[verts[i] for i in tri] for tri in tris]
        ax.add_collection3d(
            Poly3DCollection(
                polys,
                facecolor=colors[kind],
                edgecolor="none",
                linewidths=0,
            )
        )
    # Drawer outline, sitting under the grid.
    z = 0
    rect = [
        (0, 0, z),
        (DRAWER_W, 0, z),
        (DRAWER_W, DRAWER_D, z),
        (0, DRAWER_D, z),
        (0, 0, z),
    ]
    xs, ys, zs = zip(*rect)
    ax.plot(xs, ys, zs, color="#3d3a36", linewidth=1.1)
    ax.view_init(elev=28, azim=-58)
    ax.set_box_aspect((DRAWER_W, DRAWER_D, 220))
    ax.set_xlim(0, DRAWER_W)
    ax.set_ylim(0, DRAWER_D)
    ax.set_zlim(0, 200)
    ax.set_axis_off()
    ax.set_title(
        "Assembled grid inside the drawer outline",
        fontsize=13,
        color="#2c2926",
        loc="left",
        pad=8,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def write_readme(info: dict) -> None:
    plate_lines = []
    for plate in info["plates"]:
        names = ", ".join(plate["items"])
        plate_lines.append(f"- **{plate['name']}** — {names}")
    bom = "\n".join(
        f"| {row['name']} | {row['copies']} | {row['size']} | {row['grams']:.0f} g |"
        for row in info["bom"]
    )
    text = f"""# Drawer dividers

A PLA grid for a drawer that measures **{DRAWER_W:.0f} × {DRAWER_D:.0f} × {DRAWER_H:.0f} mm** inside (width × depth × height). Printed on a Bambu Lab P2S.

The layout is **{COLS} compartments across and {ROWS} front to back**. Each opening is about **{info['clear_w']:.0f} × {info['clear_d']:.0f} mm**. The walls are **{WALL_H:.0f} mm** tall, which leaves {DRAWER_H - WALL_H:.0f} mm of the drawer height free so you can grab what is inside.

![Layout](preview/layout_top.png)

The walls are honeycomb so they stay stiff without using a full sheet of plastic. Long walls are split into pieces that fit the 256 mm bed. Rails (left to right) drop onto struts (front to back) with half-lap slots. Pieces in a straight line lock with a dovetail and a small pin.

![Parts](preview/parts.png)

## What to print

About **{info['grams']:.0f} g of PLA** for the whole grid, plus a short test plate. One spool is enough.

| Part | Copies | Size on the bed | PLA each |
| --- | ---: | --- | ---: |
{bom}
| Pin | {info['pins']} | {info['pin_size']} | {info['pin_grams']:.1f} g |

Small cuts in the top edge are the assembly order: one cut on the first piece, then two, then three, counting up. Rails go left to right in letter order. Struts go front to back, A in front of B. Print **3 of each strut**.

## Plates

Open **`drawer_dividers.3mf`** in Bambu Studio. Every part is already on its own plate, and the file uses the **0.20 mm Standard** PLA profile for a 0.4 mm nozzle.

{chr(10).join(plate_lines)}

Print **Test fit** first. The two long bars should slide together to half height and sit flush. The dovetail should press together through the thickness, and the pin should drop in from the top with firm finger pressure. If a joint is too tight to assemble, stop and do not print the rest — the fit needs a little more clearance.

## Slicer settings

- Printer: Bambu Lab P2S, 0.4 mm nozzle
- Material: PLA. Use the Bambu PLA preset (or your PLA's temperatures).
- Layer height: **0.20 mm**. The wall is 3.2 mm thick, which is exactly 16 layers. Do not switch to 0.24 mm; the thickness would no longer match the slots.
- Walls: 3. Infill: 100%. The honeycomb is already in the model, and the wall is only 3.2 mm thick.
- Supports: off. Brim: off. The parts lie flat and have a large first layer.
- Leave the parts in the orientation they load. The honeycomb face is the top.

## Assembly

1. Join the rail left to right in letter order (A, then B, then C, and so on). Press each dovetail together sideways, then drop a pin into the hole at the top of the joint. The pin sits a few millimetres below the top.
2. Join each strut front to back the same way. You need three struts.
3. Lay the rail down with the slots facing up.
4. Slide the three struts down onto the rail, slots facing down, until the tops are level. The wide mouth on each slot is the lead-in.
5. Drop the grid into the drawer. It is 1 mm short of each wall so it goes in without forcing.

The drawer walls are the outer sides of the compartments. The printed grid is the cross in the middle.

![Assembled](preview/assembly.png)

## If you want a different grid

The numbers at the top of `generate.py` are the drawer size, the compartment counts, and the wall height. Change them and run `python3 generate.py`. Keep `WALL_H` at 110 mm or more so the pin stays clear of the dovetail, and keep each piece under about 220 mm so the dovetail still fits the bed.

This is an original layout for these drawer measurements. The honeycomb-and-split-wall idea follows the same practical approach as the customizable IKEA BROR divider on MakerWorld: light walls, little filament, and pieces you can adjust to the drawer you actually have.
"""
    (ROOT / "README.md").write_text(text, encoding="utf-8")


def main() -> None:
    if COLS < 2 or ROWS < 2:
        raise SystemExit("Need at least 2 by 2 compartments")
    if WALL_H < 110 or WALL_H > DRAWER_H - 8:
        raise SystemExit("Wall height should stay between 110 mm and 8 mm under the drawer top")

    strut_centers, clear_w = centers_for(DRAWER_W, COLS - 1, WALL_T)
    rail_centers, clear_d = centers_for(DRAWER_D, ROWS - 1, WALL_T)
    print(
        f"Compartments {clear_w:.1f} x {clear_d:.1f} mm, "
        f"{len(rail_centers)} rail and {len(strut_centers)} struts"
    )

    rail_x0 = SIDE_CLEAR
    rail_length = DRAWER_W - 2 * SIDE_CLEAR
    strut_y0 = SIDE_CLEAR
    strut_length = DRAWER_D - 2 * SIDE_CLEAR

    # Slots store absolute positions along each wall's run.
    rail_slots = strut_centers[:]
    strut_slots = rail_centers[:]
    rail_local_slots = [slot - rail_x0 for slot in rail_slots]
    strut_local_slots = [slot - strut_y0 for slot in strut_slots]

    rail_cuts = plan_cuts(rail_length, rail_local_slots, CUT_KEEPOUT, MAX_LEN, MIN_LEN)
    strut_cuts = plan_cuts(strut_length, strut_local_slots, CUT_KEEPOUT, MAX_LEN, MIN_LEN)
    print(f"Rail pieces: {[round(b - a, 1) for a, b in zip(rail_cuts, rail_cuts[1:])]}")
    print(f"Strut pieces: {[round(b - a, 1) for a, b in zip(strut_cuts, strut_cuts[1:])]}")

    cell_centers_x = []
    edges = [0.0]
    for center in strut_centers:
        edges.append(center - WALL_T / 2.0)
        edges.append(center + WALL_T / 2.0)
    edges.append(DRAWER_W)
    for left, right in zip(edges[0::2], edges[1::2]):
        cell_centers_x.append((left + right) / 2.0)
    cell_centers_y = []
    edges = [0.0]
    for center in rail_centers:
        edges.append(center - WALL_T / 2.0)
        edges.append(center + WALL_T / 2.0)
    edges.append(DRAWER_D)
    for front, back in zip(edges[0::2], edges[1::2]):
        cell_centers_y.append((front + back) / 2.0)

    pieces: list[Piece] = []
    letters = "ABCDEFGH"
    for index, (a, b) in enumerate(zip(rail_cuts, rail_cuts[1:])):
        start, end = rail_x0 + a, rail_x0 + b
        slots = [slot for slot in rail_slots if start + 1.0 < slot < end - 1.0]
        notch = notch_for(start, end, slots, cell_centers_x)
        pieces.append(
            Piece(
                name=f"Rail {letters[index]}",
                kind="rail",
                start=start,
                end=end,
                slots=slots,
                female=index > 0,
                male=index < len(rail_cuts) - 2,
                pips=index + 1,
                notch=notch,
                copies=1,
            )
        )
    for index, (a, b) in enumerate(zip(strut_cuts, strut_cuts[1:])):
        start, end = strut_y0 + a, strut_y0 + b
        slots = [slot for slot in strut_slots if start + 1.0 < slot < end - 1.0]
        notch = notch_for(start, end, slots, cell_centers_y)
        pieces.append(
            Piece(
                name=f"Strut {letters[index]}",
                kind="strut",
                start=start,
                end=end,
                slots=slots,
                female=index > 0,
                male=index < len(strut_cuts) - 2,
                pips=index + 1,
                notch=notch,
                copies=len(strut_centers),
            )
        )

    print("Building pieces...")
    stl_paths = {}
    grams = {}
    STL_DIR.mkdir(parents=True, exist_ok=True)
    for stale in STL_DIR.glob("*.stl"):
        stale.unlink()
    for piece in pieces:
        print(f"  {piece.name}: {piece.length:.1f} mm, slots {len(piece.slots)}")
        piece.shape = build_piece(piece)
        verts, tris = tessellate(piece.shape)
        open_edges = boundary_edges(tris)
        if open_edges:
            raise SystemExit(f"{piece.name} mesh has {open_edges} open edges")
        verts, tris, footprint = normalize_mesh(verts, tris)
        if footprint[0] > BED - 8 or footprint[1] > BED - 8 or footprint[2] > 8:
            raise SystemExit(f"{piece.name} footprint {footprint} does not fit the P2S")
        piece.mesh = (verts, tris)
        piece.footprint = footprint
        filename = piece.name.lower().replace(" ", "_") + ".stl"
        path = STL_DIR / filename
        write_stl(path, verts, tris)
        stl_paths[piece.name] = path
        grams[piece.name] = volume_of(piece.shape) / 1000.0 * PLA_DENSITY
        print(f"    {footprint[0]:.1f} x {footprint[1]:.1f} x {footprint[2]:.1f} mm, {grams[piece.name]:.1f} g")

    pin = build_pin()
    pin_verts, pin_tris = tessellate(pin)
    if boundary_edges(pin_tris):
        raise SystemExit("Pin mesh is open")
    pin_verts, pin_tris, pin_foot = normalize_mesh(pin_verts, pin_tris)
    write_stl(STL_DIR / "pin.stl", pin_verts, pin_tris)
    pin_grams = volume_of(pin) / 1000.0 * PLA_DENSITY
    joint_count = (len(rail_cuts) - 2) * len(rail_centers) + (len(strut_cuts) - 2) * len(strut_centers)
    print(f"  pin {pin_foot[0]:.1f} x {pin_foot[1]:.1f} mm, {pin_grams:.2f} g, need {joint_count}")

    print("Checking that joints clear...")
    for index in range(len(rail_cuts) - 2):
        left = pieces[index]
        right = pieces[index + 1]
        world_left = place_rail(left.shape, left.start, rail_centers[0])
        world_right = place_rail(right.shape, right.start, rail_centers[0])
        clash = intersection_volume(world_left, world_right)
        gap = shape_gap(world_left, world_right)
        print(f"  {left.name} / {right.name} overlap {clash:.2f} mm^3, gap {gap:.2f} mm")
        if clash > 8:
            raise SystemExit(f"{left.name} intersects {right.name}")
        if not 0.22 <= gap <= 0.70:
            raise SystemExit(f"{left.name} dovetail gap {gap:.2f} mm will not assemble in PLA")
    strut_pieces = [piece for piece in pieces if piece.kind == "strut"]
    rail_pieces = [piece for piece in pieces if piece.kind == "rail"]
    for index in range(len(strut_pieces) - 1):
        front = strut_pieces[index]
        back = strut_pieces[index + 1]
        world_front = place_strut(front.shape, strut_centers[0], front.start)
        world_back = place_strut(back.shape, strut_centers[0], back.start)
        clash = intersection_volume(world_front, world_back)
        gap = shape_gap(world_front, world_back)
        print(f"  {front.name} / {back.name} overlap {clash:.2f} mm^3, gap {gap:.2f} mm")
        if clash > 8:
            raise SystemExit(f"{front.name} intersects {back.name}")
        if not 0.22 <= gap <= 0.70:
            raise SystemExit(f"{front.name} dovetail gap {gap:.2f} mm will not assemble in PLA")

    # Every strut crosses every rail. Check one strut against the whole rail,
    # which is enough: the slot spacing is the same on every strut.
    sample_strut_parts = []
    for piece in strut_pieces:
        sample_strut_parts.append(place_strut(piece.shape, strut_centers[0], piece.start))
    for piece in rail_pieces:
        rail_world = place_rail(piece.shape, piece.start, rail_centers[0])
        for strut_world in sample_strut_parts:
            clash = intersection_volume(rail_world, strut_world)
            if clash > 8:
                raise SystemExit(f"{piece.name} intersects a strut by {clash:.1f} mm^3")
            # Only the piece that owns the crossing is close enough to measure.
            gap = shape_gap(rail_world, strut_world)
            if gap < 5.0 and not 0.22 <= gap <= 0.45:
                raise SystemExit(f"{piece.name} slot gap is {gap:.2f} mm")
        print(f"  {piece.name} clears the sample strut")

    # The placed rail should sit on the drawer floor and reach the intended span.
    rail_worlds = [place_rail(piece.shape, piece.start, rail_centers[0]) for piece in rail_pieces]
    for shape in rail_worlds:
        y0, y1 = bbox(shape)[2], bbox(shape)[3]
        if abs((y0 + y1) / 2.0 - rail_centers[0]) > 0.3:
            raise SystemExit("A rail piece is not on the rail centerline")
    xs0 = min(bbox(shape)[0] for shape in rail_worlds)
    xs1 = max(bbox(shape)[1] for shape in rail_worlds)
    zs1 = max(bbox(shape)[5] for shape in rail_worlds)
    print(f"  rail spans x {xs0:.1f} to {xs1:.1f}, top z {zs1:.1f}")
    if abs(xs0 - SIDE_CLEAR) > 1.5 or abs(xs1 - (DRAWER_W - SIDE_CLEAR)) > 1.5:
        raise SystemExit("Rail length does not match the drawer width")
    if abs(zs1 - WALL_H) > 0.4:
        raise SystemExit(f"Rail height is {zs1:.2f}, expected {WALL_H:.0f}")

    print("Test coupon...")
    test_rail, test_strut = build_test_pair()
    clash = intersection_volume(
        place_rail(test_rail, 0, 48),
        place_strut(test_strut, 48, 0),
    )
    print(f"  test cross overlap {clash:.2f} mm^3, gap {shape_gap(place_rail(test_rail, 0, 48), place_strut(test_strut, 48, 0)):.2f} mm")
    if clash > 8:
        raise SystemExit("Test cross intersects")
    joint_a = build_piece(Piece("Joint A", "rail", 0, 70, [], False, True, 1, None, 1))
    joint_b = build_piece(Piece("Joint B", "rail", 70, 140, [], True, False, 2, None, 1))
    joint_gap = shape_gap(place_rail(joint_a, 0, 0), place_rail(joint_b, 70, 0))
    print(f"  test dovetail gap {joint_gap:.2f} mm")
    if not 0.22 <= joint_gap <= 0.70:
        raise SystemExit("Test dovetail gap is wrong")
    coupons = []
    for name, shape in (
        ("Test rail", test_rail),
        ("Test strut", test_strut),
        ("Test joint A", joint_a),
        ("Test joint B", joint_b),
    ):
        verts, tris = tessellate(shape)
        if boundary_edges(tris):
            raise SystemExit(f"{name} mesh is open")
        verts, tris, foot = normalize_mesh(verts, tris)
        if foot[0] > BED - 8 or foot[1] > BED - 8:
            raise SystemExit(f"{name} does not fit the bed")
        write_stl(STL_DIR / (name.lower().replace(" ", "_") + ".stl"), verts, tris)
        coupons.append({"name": name, "mesh": (verts, tris), "w": foot[0], "h": foot[1]})
        print(f"  {name} {foot[0]:.1f} x {foot[1]:.1f} mm")

    print("Packing plates...")
    if PLATE_DIR.exists():
        for stale in PLATE_DIR.glob("*.3mf"):
            stale.unlink()
    prod_items = []
    for piece in pieces:
        for copy in range(piece.copies):
            label = piece.name if piece.copies == 1 else f"{piece.name} #{copy + 1}"
            prod_items.append(
                {
                    "name": label,
                    "mesh": piece.mesh,
                    "w": piece.footprint[0],
                    "h": piece.footprint[1],
                }
            )
    for index in range(joint_count):
        prod_items.append(
            {
                "name": f"Pin {index + 1}",
                "mesh": (pin_verts, pin_tris),
                "w": pin_foot[0],
                "h": pin_foot[1],
            }
        )
    test_items = coupons + [
        {"name": "Test pin", "mesh": (pin_verts, pin_tris), "w": pin_foot[0], "h": pin_foot[1]}
    ]
    test_plates = pack(test_items)
    prod_plates = pack(prod_items)
    if len(test_plates) != 1:
        raise SystemExit("Test coupon should fit on one plate")

    packed = [("Test fit", test_plates[0])]
    for index, plate in enumerate(prod_plates, start=2):
        packed.append((f"Plate {index}", plate))

    plates_3mf = []
    plate_info = []
    for name, plate_items in packed:
        objects = []
        for item in plate_items:
            mesh = item["mesh"]
            if item["rotated"]:
                mesh = (rotate_mesh_z(mesh[0], 1), mesh[1])
            x = PLATE_MARGIN + item["px"]
            y = PLATE_MARGIN + item["py"]
            if x < 4 or y < 4 or x + item["pw"] > BED - 4 or y + item["ph"] > BED - 4:
                raise SystemExit(f"{item['name']} lands outside the P2S bed")
            objects.append({"name": item["name"], "mesh": mesh, "x": x, "y": y})
        plates_3mf.append({"name": name, "objects": objects})
        plate_info.append({"name": name, "items": [item["name"] for item in plate_items]})
        print(f"  {name}: {', '.join(item['name'] for item in plate_items)}")

    project = ROOT / "drawer_dividers.3mf"
    write_3mf(project, plates_3mf, "Drawer dividers")
    _check_project(project, len(plates_3mf))

    total_grams = pin_grams * joint_count
    bom = []
    for piece in pieces:
        total_grams += grams[piece.name] * piece.copies
        bom.append(
            {
                "name": piece.name,
                "copies": piece.copies,
                "size": f"{piece.footprint[0]:.0f} × {piece.footprint[1]:.0f} × {piece.footprint[2]:.1f} mm",
                "grams": grams[piece.name],
            }
        )

    print("Rendering previews...")
    render_layout(
        PREVIEW_DIR / "layout_top.png",
        strut_centers,
        rail_centers,
        clear_w,
        clear_d,
    )
    render_parts(PREVIEW_DIR / "parts.png", pieces)
    iso_solids = []
    for piece in rail_pieces:
        iso_solids.append((place_rail(piece.shape, piece.start, rail_centers[0]), "rail"))
    for center in strut_centers:
        for piece in strut_pieces:
            iso_solids.append((place_strut(piece.shape, center, piece.start), "strut"))
    render_iso(PREVIEW_DIR / "assembly.png", iso_solids)

    info = {
        "clear_w": clear_w,
        "clear_d": clear_d,
        "grams": total_grams,
        "bom": bom,
        "pins": joint_count,
        "pin_size": f"{pin_foot[0]:.0f} × {pin_foot[1]:.0f} × {pin_foot[2]:.1f} mm",
        "pin_grams": pin_grams,
        "plates": plate_info,
        "rail_cuts": rail_cuts,
        "strut_cuts": strut_cuts,
        "strut_centers": strut_centers,
        "rail_centers": rail_centers,
    }
    (ROOT / "build_info.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    write_readme(info)
    print(f"Done. About {total_grams:.0f} g of PLA, {len(plate_info)} plates.")


if __name__ == "__main__":
    main()
