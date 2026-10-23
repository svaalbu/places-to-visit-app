#!/usr/bin/env python3
"""Lattice shoe shelf for a cabinet opening of 210 x 380 x 390 mm.

The shelf is original geometry: a diamond lattice deck, a stiffening frame,
and corner legs. It is sized to the inside of the cabinet and split into
identical halves so each piece fits a Bambu Lab P2S (256 mm cube).

Two print heights are generated from the same deck:

* 3 shoe rows — print the short half four times and stack two shelves.
  Each row has about 125 mm of clear height.
* 2 shoe rows — print the tall half twice. Each row has about 191 mm.

No supports. The flat grid goes on the build plate and the legs point up.
"""

from __future__ import annotations

import json
import math
import zipfile
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

HERE = Path(__file__).resolve().parent
STL_DIR = HERE / "stl"
PREVIEW_DIR = HERE / "preview"

# Interior of the cabinet, millimetres.
OPENING_W = 210.0
OPENING_D = 380.0
OPENING_H = 390.0

SIDE_CLEAR = 2.0
END_CLEAR = 4.0

DECK_T = 8.0
RAIL = 10.0
BEAM = 8.0
LEG = 18.0
LEG_WALL = 3.2
CAP = 9.0

# Box joint along the centre seam. Even teeth on this half, odd teeth on the
# mate, so two copies rotated 180 degrees lock together.
FINGER_PITCH = 14.0
FINGER_COUNT = 14
FINGER_SIDE_CLEAR = 0.30
FINGER_TIP_INSET = 0.55
FINGER_LENGTH = 11.6
SLOT_DEPTH = 12.2
JOINT_BAND = 16.0

# Diagonal ribs. Spacing is the perpendicular distance between rib centrelines.
RIB = 2.4
RIB_SPACING = 12.0

PIN_D = 5.6
PIN_LENGTH = 12.0
SOCKET_D = 6.0
SOCKET_DEPTH = 6.5
SOCKET_MOUTH_D = 7.6
SOCKET_MOUTH = 1.1
HOLE_D = 6.8
HOLE_DEPTH = 6.2
HOLE_MOUTH_D = 8.6
HOLE_MOUTH = 1.3

BED = 256.0
PIN_COUNT = 8


def leg_height(shelves: int) -> float:
    """Clear height under each deck, with the same clear height above the top."""
    raw = (OPENING_H - shelves * DECK_T) / (shelves + 1)
    return round(raw * 5.0) / 5.0  # nearest 0.2 mm, one layer at 0.20 mm


def box(x0, y0, z0, x1, y1, z1) -> trimesh.Trimesh:
    mesh = trimesh.creation.box(extents=(x1 - x0, y1 - y0, z1 - z0))
    mesh.apply_translation(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
    return mesh


def cylinder(radius, z0, z1, x, y, sections=40) -> trimesh.Trimesh:
    mesh = trimesh.creation.cylinder(radius=radius, height=z1 - z0, sections=sections)
    mesh.apply_translation((x, y, (z0 + z1) / 2))
    return mesh


def clip_polygon(subject, window):
    """Sutherland–Hodgman. Window is counter-clockwise."""

    def inside(p, a, b):
        return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) >= -1e-8

    def hit(p, q, a, b):
        r = (q[0] - p[0], q[1] - p[1])
        s = (b[0] - a[0], b[1] - a[1])
        rxs = r[0] * s[1] - r[1] * s[0]
        if abs(rxs) < 1e-12:
            return p
        t = ((a[0] - p[0]) * s[1] - (a[1] - p[1]) * s[0]) / rxs
        return (p[0] + t * r[0], p[1] + t * r[1])

    output = list(subject)
    for i in range(len(window)):
        a = window[i]
        b = window[(i + 1) % len(window)]
        if not output:
            break
        incoming = output
        output = []
        prev = incoming[-1]
        for cur in incoming:
            if inside(cur, a, b):
                if not inside(prev, a, b):
                    output.append(hit(prev, cur, a, b))
                output.append(cur)
            elif inside(prev, a, b):
                output.append(hit(prev, cur, a, b))
            prev = cur
    return output


def shelf_width() -> float:
    return OPENING_W - 2 * SIDE_CLEAR


def half_depth() -> float:
    return (OPENING_D - 2 * END_CLEAR) / 2


def finger_cells():
    span = FINGER_COUNT * FINGER_PITCH
    x0 = -span / 2
    cells = []
    for i in range(FINGER_COUNT):
        cells.append((x0 + i * FINGER_PITCH, x0 + (i + 1) * FINGER_PITCH, i % 2 == 0))
    return cells


def leg_sites():
    """Leg footprints on this half. The mate supplies the other centre leg."""
    w = shelf_width()
    d = half_depth()
    return {
        "outer_left": (-w / 2, -w / 2 + LEG, d - LEG, d),
        "outer_right": (w / 2 - LEG, w / 2, d - LEG, d),
        "joint_left": (-w / 2, -w / 2 + LEG, 0.0, LEG),
    }


def pad_sites():
    """Solid landing pads, larger than the feet on the inner sides."""
    w = shelf_width()
    d = half_depth()
    extra = 8.0
    return [
        (-w / 2, -w / 2 + LEG + extra, d - LEG - extra, d),
        (w / 2 - LEG - extra, w / 2, d - LEG - extra, d),
        # Stay out of the first gap tooth, which starts just inboard of the leg.
        (-w / 2, -w / 2 + LEG, 0.0, LEG + extra),
    ]


def beam_spans():
    d = half_depth()
    y0 = JOINT_BAND + 18.0
    y1 = d - RAIL - 18.0
    centers = [y0, (y0 + y1) / 2, y1]
    return [(c - BEAM / 2, c + BEAM / 2) for c in centers]


def rect(x0, y0, x1, y1) -> Polygon:
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def deck_polygon() -> Polygon:
    """Flat pattern of one half. Openings are holes; the seam teeth are solid."""
    w = shelf_width()
    d = half_depth()
    parts = [
        rect(-w / 2, 0, -w / 2 + RAIL, d),
        rect(w / 2 - RAIL, 0, w / 2, d),
        rect(-w / 2, d - RAIL, w / 2, d),
        rect(-w / 2, 0, w / 2, JOINT_BAND),
        rect(-BEAM / 2, JOINT_BAND - 2, BEAM / 2, d - RAIL + 2),
    ]
    for y0, y1 in beam_spans():
        parts.append(rect(-w / 2, y0, w / 2, y1))
    for x0, x1, y0, y1 in pad_sites():
        parts.append(rect(x0, y0, x1, y1))
    for x0, x1, even in finger_cells():
        if not even:
            continue
        inset = FINGER_SIDE_CLEAR
        root0, root1 = x0 + inset, x1 - inset
        parts.append(
            Polygon(
                [
                    (root0, 1.2),
                    (root1, 1.2),
                    (root1 - FINGER_TIP_INSET, -FINGER_LENGTH),
                    (root0 + FINGER_TIP_INSET, -FINGER_LENGTH),
                ]
            )
        )

    # Ribs overlap the frame by about 2 mm so the grid is one piece.
    window = [
        (-w / 2 + RAIL - 2.2, JOINT_BAND - 2.2),
        (w / 2 - RAIL + 2.2, JOINT_BAND - 2.2),
        (w / 2 - RAIL + 2.2, d - RAIL + 2.2),
        (-w / 2 + RAIL - 2.2, d - RAIL + 2.2),
    ]
    corners = np.array(window)
    length = w + d + 40
    for angle in (math.pi / 4, -math.pi / 4):
        direction = np.array([math.cos(angle), math.sin(angle)])
        perp = np.array([-math.sin(angle), math.cos(angle)])
        projections = corners @ perp
        start = math.floor(float(projections.min()) / RIB_SPACING) - 1
        stop = math.ceil(float(projections.max()) / RIB_SPACING) + 1
        for i in range(start, stop + 1):
            center = perp * (i * RIB_SPACING)
            corners_rib = [
                center - direction * (length / 2) - perp * (RIB / 2),
                center + direction * (length / 2) - perp * (RIB / 2),
                center + direction * (length / 2) + perp * (RIB / 2),
                center - direction * (length / 2) + perp * (RIB / 2),
            ]
            clipped = clip_polygon([tuple(p) for p in corners_rib], window)
            if len(clipped) >= 3:
                parts.append(Polygon(clipped))

    pattern = unary_union(parts)
    for x0, x1, even in finger_cells():
        if even:
            continue
        pattern = pattern.difference(rect(x0, -0.4, x1, SLOT_DEPTH))
    if pattern.geom_type != "Polygon":
        pattern = max(pattern.geoms, key=lambda item: item.area)
    return pattern


def hole_cutters():
    """Blind pin holes opening on the bed face, which is the shoe surface in use."""
    cutters = []
    for x0, x1, y0, y1 in leg_sites().values():
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        cutters.append(cylinder(HOLE_MOUTH_D / 2, -0.4, HOLE_MOUTH, cx, cy))
        cutters.append(cylinder(HOLE_D / 2, -0.4, HOLE_DEPTH, cx, cy))
    return cutters


def make_leg(x0, x1, y0, y1, height) -> trimesh.Trimesh:
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    outer = box(x0, y0, DECK_T - 0.05, x1, y1, DECK_T + height)
    inner = LEG - 2 * LEG_WALL
    void_top = DECK_T + height - CAP
    void = box(
        cx - inner / 2,
        cy - inner / 2,
        DECK_T - 0.2,
        cx + inner / 2,
        cy + inner / 2,
        void_top,
    )
    mouth_top = DECK_T + height + 0.4
    mouth = cylinder(SOCKET_MOUTH_D / 2, mouth_top - SOCKET_MOUTH, mouth_top, cx, cy)
    socket = cylinder(
        SOCKET_D / 2,
        mouth_top - SOCKET_MOUTH - SOCKET_DEPTH,
        mouth_top,
        cx,
        cy,
    )
    return trimesh.boolean.difference([outer, void, mouth, socket], engine="manifold")


def unite(meshes: list[trimesh.Trimesh]) -> trimesh.Trimesh:
    fused = trimesh.boolean.union(meshes, engine="manifold")
    fused.merge_vertices()
    fused.fix_normals()
    return fused


def build_deck() -> trimesh.Trimesh:
    pattern = deck_polygon()
    outline = trimesh.creation.extrude_polygon(Polygon(pattern.exterior), DECK_T)
    if outline.volume < 0:
        outline.invert()
    cutters = []
    skipped = 0
    for ring in pattern.interiors:
        hole = Polygon(ring)
        if hole.area < 2.0:
            skipped += 1
            continue
        prism = trimesh.creation.extrude_polygon(hole, DECK_T + 1.2)
        prism.apply_translation((0, 0, -0.6))
        if prism.volume < 0:
            prism.invert()
        cutters.append(prism)
    print(f"cutting {len(cutters)} lattice openings, skipped {skipped} slivers")
    deck = trimesh.boolean.difference([outline, *cutters, *hole_cutters()], engine="manifold")
    deck.merge_vertices()
    deck.fix_normals()
    return deck


def build_half(deck: trimesh.Trimesh, height: float) -> trimesh.Trimesh:
    legs = [make_leg(*site, height) for site in leg_sites().values()]
    half = unite([deck, *legs])
    half.merge_vertices()
    half.fix_normals()
    return half


def build_pins() -> trimesh.Trimesh:
    pins = [cylinder(PIN_D / 2, 0.0, PIN_LENGTH, i * 14.0, 0.0, sections=28) for i in range(PIN_COUNT)]
    return trimesh.util.concatenate(pins)


def prepare_print(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """Move the grid onto the origin so the file drops onto the bed."""
    out = mesh.copy()
    out.apply_translation(-out.bounds[0])
    return out


def rotated_mate(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    mate = mesh.copy()
    mate.apply_transform(trimesh.transformations.rotation_matrix(math.pi, [0, 0, 1]))
    return mate


def to_use(mesh: trimesh.Trimesh, height: float) -> trimesh.Trimesh:
    """Flip off the printer so the legs point down and the grid is on top."""
    out = mesh.copy()
    out.apply_transform(trimesh.transformations.rotation_matrix(math.pi, [1, 0, 0]))
    out.apply_translation((0, 0, DECK_T + height))
    return out


def assemble_shelf(half: trimesh.Trimesh, height: float) -> trimesh.Trimesh:
    pair = unite([half, rotated_mate(half)])
    return to_use(pair, height)


def assert_printable(mesh: trimesh.Trimesh, name: str) -> None:
    size = mesh.extents
    if size.max() > BED - 6:
        raise SystemExit(f"{name} is {size} mm and does not fit a {BED:.0f} mm bed")
    if not mesh.is_watertight:
        raise SystemExit(f"{name} is not watertight")
    if mesh.volume <= 0:
        raise SystemExit(f"{name} has no volume")


def check_fit(half: trimesh.Trimesh, height: float, shelves: int) -> dict:
    mate = rotated_mate(half)
    for x0, x1, even in finger_cells():
        cx = (x0 + x1) / 2
        if even:
            if not half.contains([(cx, -FINGER_LENGTH * 0.5, DECK_T * 0.5)])[0]:
                raise SystemExit(f"tooth at x={cx:.1f} does not cross the seam")
        else:
            in_slot = (cx, SLOT_DEPTH * 0.5, DECK_T * 0.5)
            if half.contains([in_slot])[0] or not mate.contains([in_slot])[0]:
                raise SystemExit(f"mate tooth does not fill the slot at x={cx:.1f}")
    overlap = trimesh.boolean.intersection([half, mate], engine="manifold")
    overlap_v = float(overlap.volume) if overlap is not None else 0.0
    if overlap_v > 5.0:
        raise SystemExit(f"halves intersect by {overlap_v:.1f} mm³ — the joint will not close")

    shelf = assemble_shelf(half, height)
    size = shelf.extents
    if size[0] > OPENING_W - 1 or size[1] > OPENING_D - 1:
        raise SystemExit(f"assembled shelf {size} does not fit the opening")

    top = shelves * (height + DECK_T)
    above = OPENING_H - top
    report = {
        "opening_mm": [OPENING_W, OPENING_D, OPENING_H],
        "shelf_width_mm": round(float(size[0]), 2),
        "shelf_depth_mm": round(float(size[1]), 2),
        "leg_height_mm": height,
        "deck_thickness_mm": DECK_T,
        "shelves": shelves,
        "shoe_rows": shelves + 1,
        "clearance_under_deck_mm": height,
        "clearance_above_top_mm": round(above, 2),
        "top_surface_mm": round(top, 2),
        "half_print_mm": [round(v, 2) for v in prepare_print(half).extents],
        "half_volume_cm3": round(half.volume / 1000.0, 1),
        "joint_overlap_mm3": round(overlap_v, 3),
        "watertight": bool(half.is_watertight),
    }
    if min(height, above) < 110:
        raise SystemExit(f"clearance is too small: {report}")
    return report


def rasterize(meshes, path, az=-58, el=26, width=1280, height=900, margin=0.08, lines=None, view=None):
    """Orthographic z-buffer. meshes is a list of (Trimesh, rgb tuple)."""
    if view is None:
        rot_z = trimesh.transformations.rotation_matrix(math.radians(az), [0, 0, 1])[:3, :3]
        rot_x = trimesh.transformations.rotation_matrix(math.radians(el), [1, 0, 0])[:3, :3]
        view = rot_x @ rot_z
    view = np.asarray(view, dtype=float)
    light = np.array([0.35, 0.45, 0.82])
    light = light / np.linalg.norm(light)

    centers = [m.bounds.mean(axis=0) for m, _ in meshes]
    origin = np.average(centers, axis=0)
    projected = []
    all_xy = []
    for mesh, color in meshes:
        verts = (mesh.vertices - origin) @ view.T
        faces = mesh.faces
        normals = mesh.face_normals @ view.T
        projected.append((verts, faces, normals, np.asarray(color, dtype=float)))
        all_xy.append(verts[:, :2])
    if lines:
        for a, b, _rgb in lines:
            for point in (a, b):
                all_xy.append(((np.asarray(point, dtype=float) - origin) @ view.T)[:2].reshape(1, 2))
    pts = np.vstack(all_xy)
    min_xy = pts.min(axis=0)
    max_xy = pts.max(axis=0)
    span = np.maximum(max_xy - min_xy, 1.0)
    scale = min(width * (1 - 2 * margin) / span[0], height * (1 - 2 * margin) / span[1])
    offset = np.array([width, height]) / 2 - (min_xy + max_xy) / 2 * scale
    offset[1] = height - offset[1]

    buf = np.ones((height, width, 3), dtype=np.float32)
    buf[:] = (0.945, 0.933, 0.914)
    depth = np.full((height, width), -1e18, dtype=np.float32)

    for verts, faces, normals, color in projected:
        screen = np.empty_like(verts)
        screen[:, 0] = verts[:, 0] * scale + offset[0]
        screen[:, 1] = -verts[:, 1] * scale + offset[1]
        screen[:, 2] = verts[:, 2]
        for index, face in enumerate(faces):
            normal = normals[index]
            if normal[2] <= 0:
                continue
            tri = screen[face]
            shade = 0.38 + 0.62 * max(0.0, float(np.dot(normal, light)))
            rgb = np.clip(color * shade, 0, 1)
            _fill(buf, depth, tri, rgb)
    if lines:
        for a, b, rgb in lines:
            pa = (np.asarray(a) - origin) @ view.T
            pb = (np.asarray(b) - origin) @ view.T
            sa = (pa[0] * scale + offset[0], -pa[1] * scale + offset[1], pa[2])
            sb = (pb[0] * scale + offset[0], -pb[1] * scale + offset[1], pb[2])
            _line(buf, depth, sa, sb, np.asarray(rgb))
    image = Image.fromarray((buf * 255).astype(np.uint8), "RGB")
    image.save(path, quality=95)
    print(f"wrote {path}")


def _fill(buf, depth, tri, rgb):
    h, w, _ = buf.shape
    minx = max(int(np.floor(tri[:, 0].min())), 0)
    maxx = min(int(np.ceil(tri[:, 0].max())), w - 1)
    miny = max(int(np.floor(tri[:, 1].min())), 0)
    maxy = min(int(np.ceil(tri[:, 1].max())), h - 1)
    if minx >= maxx or miny >= maxy:
        return
    xs = np.arange(minx, maxx + 1)
    ys = np.arange(miny, maxy + 1)
    grid_x, grid_y = np.meshgrid(xs, ys)
    p0, p1, p2 = tri
    den = (p1[1] - p2[1]) * (p0[0] - p2[0]) + (p2[0] - p1[0]) * (p0[1] - p2[1])
    if abs(den) < 1e-8:
        return
    w0 = ((p1[1] - p2[1]) * (grid_x - p2[0]) + (p2[0] - p1[0]) * (grid_y - p2[1])) / den
    w1 = ((p2[1] - p0[1]) * (grid_x - p2[0]) + (p0[0] - p2[0]) * (grid_y - p2[1])) / den
    w2 = 1 - w0 - w1
    mask = (w0 >= -0.002) & (w1 >= -0.002) & (w2 >= -0.002)
    if not np.any(mask):
        return
    z = w0 * p0[2] + w1 * p1[2] + w2 * p2[2]
    view = depth[miny : maxy + 1, minx : maxx + 1]
    update = mask & (z > view)
    view[update] = z[update]
    pix = buf[miny : maxy + 1, minx : maxx + 1]
    pix[update] = rgb


def _line(buf, depth, a, b, rgb):
    length = max(abs(b[0] - a[0]), abs(b[1] - a[1]))
    steps = int(length) + 1
    h, w, _ = buf.shape
    for i in range(steps + 1):
        t = i / max(steps, 1)
        x = int(a[0] + (b[0] - a[0]) * t)
        y = int(a[1] + (b[1] - a[1]) * t)
        z = a[2] + (b[2] - a[2]) * t
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                xx, yy = x + dx, y + dy
                if 0 <= xx < w and 0 <= yy < h and z >= depth[yy, xx] - 1.5:
                    buf[yy, xx] = rgb * 0.85 + buf[yy, xx] * 0.15


def cabinet_lines():
    w, d, h = OPENING_W, OPENING_D, OPENING_H
    x0, x1 = -w / 2, w / 2
    y0, y1 = -d / 2, d / 2
    corners = []
    for x in (x0, x1):
        for y in (y0, y1):
            for z in (0, h):
                corners.append((x, y, z))
    edges = []
    pts = [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (0.0, h)]
    for i, a in enumerate(pts):
        for b in pts[i + 1 :]:
            shared = sum(abs(a[k] - b[k]) < 1e-6 for k in range(3))
            if shared == 2:
                edges.append((a, b, (0.45, 0.36, 0.28)))
    return edges


def font(size):
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def draw_schematic(path, short_h, tall_h):
    image = Image.new("RGB", (1400, 780), (246, 244, 241))
    draw = ImageDraw.Draw(image)
    title = font(28)
    body = font(18)
    small = font(15)
    draw.text((40, 28), "Cabinet opening  210 wide  ×  380 deep  ×  390 tall", fill=(40, 36, 32), font=title)
    draw.text(
        (40, 68),
        "The printed grid is 206 × 372 mm, with 2 mm spare on each side and 4 mm at the front and back.",
        fill=(70, 64, 58),
        font=body,
    )

    def panel(origin, height, label, clearances):
        ox, oy = origin
        scale = 1.15
        cw, ch = 210 * scale, 390 * scale
        draw.rounded_rectangle([ox, oy, ox + cw, oy + ch], radius=8, outline=(90, 72, 54), width=8, fill=(232, 224, 214))
        z_cursor = 0.0
        colors = [(236, 236, 232), (228, 232, 236), (236, 232, 228)]
        for i, (kind, value) in enumerate(clearances):
            y0 = oy + ch - (z_cursor + value) * scale
            y1 = oy + ch - z_cursor * scale
            if kind == "gap":
                draw.rectangle([ox + 10, y0, ox + cw - 10, y1], fill=colors[i % 3])
                draw.text((ox + 18, (y0 + y1) / 2 - 10), f"{value:.0f} mm", fill=(60, 60, 60), font=small)
            else:
                draw.rectangle([ox + 8, y0, ox + cw - 8, y1], fill=(80, 80, 78))
            z_cursor += value
        draw.text((ox, oy - 28), label, fill=(40, 36, 32), font=body)

    panel(
        (60, 150),
        short_h,
        "Three rows  —  print the short half × 4",
        [
            ("gap", short_h),
            ("deck", DECK_T),
            ("gap", short_h),
            ("deck", DECK_T),
            ("gap", OPENING_H - 2 * (short_h + DECK_T)),
        ],
    )
    panel(
        (460, 150),
        tall_h,
        "Two rows  —  print the tall half × 2",
        [
            ("gap", tall_h),
            ("deck", DECK_T),
            ("gap", OPENING_H - (tall_h + DECK_T)),
        ],
    )
    draw.text(
        (860, 170),
        "Each shelf is two identical halves.\n"
        "Turn one around 180° and the teeth\n"
        "along the centre lock together.\n\n"
        "Glue that seam. The legs stay free\n"
        "so a shelf lifts out of the cabinet.\n\n"
        "The upper shelf stands on the lower\n"
        "grid. Six pins keep it from sliding.\n\n"
        "A pair of shoes sits side by side,\n"
        "heels toward the opening.",
        fill=(50, 46, 42),
        font=body,
    )
    image.save(path)
    print(f"wrote {path}")


def write_3mf(path: Path, objects: list[tuple[str, trimesh.Trimesh, tuple[float, float]]]):
    """Bambu Studio project for a P2S with a 0.4 mm nozzle and PLA."""
    chunks = []
    model_objects = []
    assemble = []
    build_items = []
    for index, (name, mesh, (px, py)) in enumerate(objects, start=1):
        vertices = []
        for x, y, z in mesh.vertices:
            vertices.append(f'<vertex x="{x:.4f}" y="{y:.4f}" z="{z:.4f}"/>')
        triangles = []
        for a, b, c in mesh.faces:
            triangles.append(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>')
        chunks.append(
            f'<object id="{index}" name="{name}" type="model"><mesh><vertices>'
            + "".join(vertices)
            + "</vertices><triangles>"
            + "".join(triangles)
            + "</triangles></mesh></object>"
        )
        faces = len(mesh.faces)
        model_objects.append(
            f"""  <object id="{index}">
    <metadata key="name" value="{name}"/>
    <metadata key="extruder" value="1"/>
    <part id="{index}" subtype="normal_part">
      <metadata key="name" value="{name}"/>
      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>
      <mesh_stat face_count="{faces}" edges_fixed="0" degenerate_facets="0" facets_removed="0" facets_reversed="0" backwards_edges="0"/>
    </part>
  </object>"""
        )
        transform = f"1 0 0 0 1 0 0 0 1 {px:.4f} {py:.4f} 0.0000"
        build_items.append(f'<item objectid="{index}" transform="{transform}" printable="1"/>')
        assemble.append(
            f'<assemble_item object_id="{index}" instance_id="0" transform="{transform}" offset="0 0 0"/>'
        )

    model = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<model unit="millimeter" xml:lang="en-US" '
        'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">\n'
        '  <metadata name="Application">BambuStudio-01.10.02.75</metadata>\n'
        '  <metadata name="BambuStudio:3mfVersion">1</metadata>\n'
        f"  <metadata name=\"Title\">{path.stem}</metadata>\n"
        "  <resources>\n"
        + "\n".join(chunks)
        + "\n  </resources>\n  <build>\n"
        + "".join(build_items)
        + "\n  </build>\n</model>\n"
    )
    settings = {
        "name": "project_settings",
        "printer_model": "Bambu Lab P2S",
        "printer_variant": "0.4",
        "nozzle_diameter": ["0.4"],
        "printer_settings_id": "Bambu Lab P2S 0.4 nozzle",
        "print_settings_id": "0.20mm Standard @BBL P2S",
        "filament_settings_id": ["Bambu PLA Basic @BBL P2S"],
        "filament_colour": ["#F2F2F2"],
        "filament_type": ["PLA"],
        "filament_diameter": ["1.75"],
        "filament_self_index": ["1"],
        "filament_extruder_variant": ["Direct Drive Standard"],
        "extruder_variant_list": ["Direct Drive Standard,Direct Drive High Flow,Direct Drive E3D High Flow"],
        "inherits_group": [
            "0.20mm Standard @BBL P2S",
            "Bambu PLA Basic @BBL P2S",
            "Bambu Lab P2S 0.4 nozzle",
        ],
        "different_settings_to_system": ["", "filament_colour", ""],
    }
    model_settings = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<config>\n'
        + "\n".join(model_objects)
        + '\n  <plate>\n    <metadata key="plater_id" value="1"/>\n'
        '    <metadata key="plater_name" value=""/>\n'
        '    <metadata key="locked" value="false"/>\n'
        + "\n".join(
            f'    <model_instance>\n      <metadata key="object_id" value="{i}"/>\n'
            f'      <metadata key="instance_id" value="0"/>\n'
            f'      <metadata key="identify_id" value="{i}"/>\n    </model_instance>'
            for i in range(1, len(objects) + 1)
        )
        + "\n  </plate>\n  <assemble>\n"
        + "".join(assemble)
        + "\n  </assemble>\n</config>\n"
    )
    content_types = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
  <Default Extension="config" ContentType="text/xml"/>
</Types>
"""
    rels = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("3D/3dmodel.model", model)
        archive.writestr("Metadata/project_settings.config", json.dumps(settings, indent=2))
        archive.writestr("Metadata/model_settings.config", model_settings)
    print(f"wrote {path}")


def on_bed(mesh: trimesh.Trimesh, x: float, y: float) -> None:
    x1 = x + float(mesh.extents[0])
    y1 = y + float(mesh.extents[1])
    if x < 0 or y < 0 or x1 > BED or y1 > BED:
        raise SystemExit(f"part hangs off the {BED:.0f} mm bed: x {x:.1f}-{x1:.1f}, y {y:.1f}-{y1:.1f}")


def main():
    STL_DIR.mkdir(parents=True, exist_ok=True)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

    short = leg_height(2)
    tall = leg_height(1)
    print(f"leg heights: 3-row {short} mm, 2-row {tall} mm")

    deck = build_deck()
    print(f"deck volume {deck.volume / 1000:.1f} cm³, watertight {deck.is_watertight}")

    halves = {}
    reports = {}
    for name, height in (("3row", short), ("2row", tall)):
        print(f"building {name} legs")
        half = build_half(deck, height)
        assert_printable(prepare_print(half), name)
        reports[name] = check_fit(half, height, 2 if name == "3row" else 1)
        printable = prepare_print(half)
        out = STL_DIR / f"shelf_half_{name}.stl"
        printable.export(out)
        print(f"wrote {out}  {printable.extents.round(1).tolist()} mm  {len(printable.faces)} faces")
        halves[name] = half

    pins = prepare_print(build_pins())
    pins.export(STL_DIR / "pins.stl")
    print(f"wrote pins {pins.extents.round(1).tolist()} mm")

    (STL_DIR / "fit.json").write_text(json.dumps(reports, indent=2) + "\n")

    plastic = (0.92, 0.92, 0.90)
    short_half = halves["3row"]
    rasterize([(prepare_print(short_half), plastic)], PREVIEW_DIR / "half_on_bed.png", az=-52, el=24)
    shelf = assemble_shelf(short_half, short)
    rasterize([(shelf, plastic)], PREVIEW_DIR / "one_shelf.png", az=-40, el=32, width=1200, height=800)
    rasterize([(shelf, plastic)], PREVIEW_DIR / "top.png", az=0, el=0, width=1100, height=1400)

    lower = shelf
    upper = shelf.copy()
    upper.apply_translation((0, 0, short + DECK_T))
    stacked = [(lower, plastic), (upper, (0.86, 0.88, 0.90))]
    rasterize(
        stacked,
        PREVIEW_DIR / "in_cabinet.png",
        az=-68,
        el=18,
        width=1400,
        height=1000,
        lines=cabinet_lines(),
    )
    side_view = np.array([[0, 1, 0], [0, 0, 1], [1, 0, 0]], dtype=float)
    rasterize(
        stacked,
        PREVIEW_DIR / "side.png",
        width=1400,
        height=900,
        lines=cabinet_lines(),
        view=side_view,
    )
    draw_schematic(PREVIEW_DIR / "clearances.png", short, tall)

    half_print = prepare_print(short_half)
    margin_x = (BED - half_print.extents[0]) / 2
    half_y = 10.0
    pin_x = margin_x
    pin_y = half_y + half_print.extents[1] + 8.0
    on_bed(half_print, margin_x, half_y)
    on_bed(pins, pin_x, pin_y)
    for label, half in halves.items():
        printable = prepare_print(half)
        objects = [(f"Shelf half ({label})", printable, (margin_x, half_y))]
        if label == "3row":
            objects.append(("Pins", pins, (pin_x, pin_y)))
        write_3mf(HERE / f"shoe_shelf_{label}.3mf", objects)
    print(json.dumps(reports, indent=2))


if __name__ == "__main__":
    main()
