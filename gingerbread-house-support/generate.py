#!/usr/bin/env python3
"""Robust gingerbread-house corner support for a Bambu Lab P2S.

The clip wraps the outside of one baked corner while the frosting sets.
The inside faces stay a sharp 90 degrees and run all the way down to the
table, so the cookie is not lifted. Everything else is thicker than the
0.6 mm original: a 3.6 mm wall, a 2.4 mm sole, and solid gussets.

Run from this directory:

    python3 generate.py
"""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
from manifold3d import Manifold

ROOT = Path(__file__).resolve().parent
STL_PATH = ROOT / "stl" / "gingerbread_corner_support.stl"
PREVIEW_DIR = ROOT / "preview"

# Millimetres. The inside corner is the origin before the final shift
# onto the bed. Cookie walls sit in the +X / +Y quadrant.
WALL = 4.0
ARM = 28.0
HEIGHT = 40.0
BASE = 2.4
FOOT = 16.0
GUSSET_T = 8.0
GUSSET_H = 26.0
CORNER_H = 28.0


def box(x0: float, y0: float, z0: float, x1: float, y1: float, z1: float) -> Manifold:
    return Manifold.cube((x1 - x0, y1 - y0, z1 - z0)).translate((x0, y0, z0))


def hull(points: list[tuple[float, float, float]]) -> Manifold:
    return Manifold.hull_points(points)


def build() -> Manifold:
    outer = -(WALL + FOOT)
    # Contact walls. Each one also fills the shared corner block.
    wall_y = box(-WALL, -WALL, 0.0, 0.0, ARM, HEIGHT)
    wall_x = box(-WALL, -WALL, 0.0, ARM, 0.0, HEIGHT)
    # Sole stays entirely outside the cookie quadrant.
    sole_y = box(outer, outer, 0.0, 0.0, ARM, BASE)
    sole_x = box(outer, outer, 0.0, ARM, 0.0, BASE)

    # Brace near the end of each arm. Solid to the bed, sloped only on top.
    y0 = ARM - 18.0
    y1 = y0 + GUSSET_T
    gusset_y = hull(
        [
            (outer, y0, 0.0),
            (-WALL, y0, 0.0),
            (-WALL, y0, GUSSET_H),
            (outer, y0, BASE),
            (outer, y1, 0.0),
            (-WALL, y1, 0.0),
            (-WALL, y1, GUSSET_H),
            (outer, y1, BASE),
        ]
    )
    x0 = ARM - 18.0
    x1 = x0 + GUSSET_T
    gusset_x = hull(
        [
            (x0, outer, 0.0),
            (x0, -WALL, 0.0),
            (x0, -WALL, GUSSET_H),
            (x0, outer, BASE),
            (x1, outer, 0.0),
            (x1, -WALL, 0.0),
            (x1, -WALL, GUSSET_H),
            (x1, outer, BASE),
        ]
    )
    # Buttress in the outer corner, tallest where the two walls meet.
    corner = hull(
        [
            (-WALL, -WALL, 0.0),
            (outer, -WALL, 0.0),
            (-WALL, outer, 0.0),
            (-WALL, -WALL, CORNER_H),
            (outer, -WALL, BASE),
            (-WALL, outer, BASE),
        ]
    )
    part = wall_y + wall_x + sole_y + sole_x + gusset_y + gusset_x + corner
    # Shift so the sole's outer corner is on the origin and Z is up.
    return part.translate((-outer, -outer, 0.0))


def write_stl(model: Manifold, path: Path) -> None:
    mesh = model.to_mesh()
    verts = np.asarray(mesh.vert_properties, dtype=np.float32)
    tris = np.asarray(mesh.tri_verts, dtype=np.uint32)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(b"Robust gingerbread corner support".ljust(80, b" "))
        handle.write(struct.pack("<I", len(tris)))
        for tri in tris:
            a, b, c = verts[tri[0]], verts[tri[1]], verts[tri[2]]
            normal = np.cross(b - a, c - a)
            length = float(np.linalg.norm(normal))
            if length > 0:
                normal /= length
            handle.write(struct.pack("<3f", *normal.astype(np.float32)))
            for vertex in (a, b, c):
                handle.write(struct.pack("<3f", *vertex))
            handle.write(struct.pack("<H", 0))


def check(model: Manifold) -> None:
    status = str(model.status())
    if "NoError" not in status:
        raise SystemExit(f"mesh error: {status}")
    bounds = model.bounding_box()
    x0, y0, z0, x1, y1, z1 = bounds
    if abs(x0) > 1e-6 or abs(y0) > 1e-6 or abs(z0) > 1e-6:
        raise SystemExit(f"part is not sitting on the origin: {bounds}")
    if z1 < HEIGHT - 0.1 or z1 > HEIGHT + 0.1:
        raise SystemExit(f"unexpected height {z1}")

    mesh = model.to_mesh()
    verts = np.asarray(mesh.vert_properties, dtype=np.float64)
    tris = np.asarray(mesh.tri_verts, dtype=np.int32)
    # Inside corner after the shift. Nothing may enter the cookie quadrant.
    corner = WALL + FOOT
    for tri in tris:
        points = verts[tri]
        if np.all(points[:, 0] > corner + 0.05) and np.all(points[:, 1] > corner + 0.05):
            raise SystemExit("geometry enters the cookie quadrant")

    overhangs = []
    for tri in tris:
        a, b, c = verts[tri]
        normal = np.cross(b - a, c - a)
        length = float(np.linalg.norm(normal))
        if length < 1e-9:
            continue
        normal /= length
        # Bottom face points down. Any other downward face is an overhang.
        if normal[2] < -0.25 and not np.all(np.abs(verts[tri][:, 2]) < 1e-4):
            angle = float(np.degrees(np.arcsin(np.clip(-normal[2], 0, 1))))
            overhangs.append(angle)
    if overhangs:
        raise SystemExit(f"needs support, shallowest underside {max(overhangs):.1f} deg")

    _expect_thickness(
        model,
        (corner - WALL - 5.0, corner + ARM * 0.45, HEIGHT * 0.85),
        (corner + 5.0, corner + ARM * 0.45, HEIGHT * 0.85),
        WALL,
    )
    _expect_thickness(
        model,
        (corner + ARM * 0.45, corner - WALL - 5.0, HEIGHT * 0.85),
        (corner + ARM * 0.45, corner + 5.0, HEIGHT * 0.85),
        WALL,
    )
    _expect_thickness(
        model,
        (corner - WALL - FOOT - 2.0, corner + ARM * 0.45, BASE * 0.5),
        (corner + 2.0, corner + ARM * 0.45, BASE * 0.5),
        WALL + FOOT,
    )
    print(f"size {x1 - x0:.1f} x {y1 - y0:.1f} x {z1 - z0:.1f} mm")
    print(f"volume {model.volume() / 1000:.1f} cm3, about {model.volume() * 0.00124:.0f} g in PLA")
    print(f"inside corner at x={corner:.1f}, y={corner:.1f}")


def _expect_thickness(
    model: Manifold,
    start: tuple[float, float, float],
    end: tuple[float, float, float],
    expected: float,
) -> None:
    hits = model.ray_cast(start, end)
    if len(hits) < 2:
        raise SystemExit(f"ray missed a solid section: {start} -> {end}, hits={len(hits)}")
    span = sum((end[i] - start[i]) ** 2 for i in range(3)) ** 0.5
    thickness = abs(hits[1].distance - hits[0].distance) * span
    if abs(thickness - expected) > 0.05:
        raise SystemExit(f"thickness {thickness:.2f} mm, expected {expected:.2f} mm")


def render(model: Manifold) -> None:
    mesh = model.to_mesh()
    verts = np.asarray(mesh.vert_properties, dtype=np.float64)
    tris = np.asarray(mesh.tri_verts, dtype=np.int32)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    views = {
        "top": np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=float),
        "front": np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], dtype=float),
        "side": np.array([[0, 1, 0], [0, 0, 1], [-1, 0, 0]], dtype=float),
        "iso": _iso_axes(),
    }
    for name, axes in views.items():
        _raster(verts, tris, axes, PREVIEW_DIR / f"{name}.png")


def _iso_axes() -> np.ndarray:
    yaw, pitch = np.radians(40), np.radians(32)
    cy, sy = np.cos(yaw), np.sin(yaw)
    cp, sp = np.cos(pitch), np.sin(pitch)
    # Columns are the projected X and Y axes and the depth axis.
    return np.array(
        [
            [cy, sy * sp, sy * cp],
            [-sy, cy * sp, cy * cp],
            [0, cp, -sp],
        ],
        dtype=float,
    )


def _raster(verts: np.ndarray, tris: np.ndarray, axes: np.ndarray, path: Path) -> None:
    projected = verts @ axes
    flat = projected[:, :2]
    depth = projected[:, 2]
    minimum = flat.min(axis=0)
    maximum = flat.max(axis=0)
    span = np.maximum(maximum - minimum, 1e-6)
    pixels = 640
    scale = (pixels - 40) / span.max()
    offset = (pixels - span * scale) / 2 - minimum * scale
    image = np.full((pixels, pixels, 3), 244, dtype=np.uint8)
    zbuf = np.full((pixels, pixels), -1e9, dtype=np.float32)
    order = np.argsort(depth[tris].mean(axis=1))
    for index in order:
        tri = tris[index]
        pts = flat[tri] * scale + offset
        zs = depth[tri]
        normal = np.cross(verts[tri[1]] - verts[tri[0]], verts[tri[2]] - verts[tri[0]])
        length = float(np.linalg.norm(normal))
        if length < 1e-9:
            continue
        normal /= length
        light = abs(float(np.dot(normal, np.array([0.35, 0.25, 0.90]))))
        shade = int(70 + 160 * light)
        color = np.array([shade, int(shade * 0.72), int(shade * 0.28)], dtype=np.uint8)
        _paint_triangle(image, zbuf, pts, zs, color)
    _write_png(path, image)


def _paint_triangle(
    image: np.ndarray,
    zbuf: np.ndarray,
    pts: np.ndarray,
    zs: np.ndarray,
    color: np.ndarray,
) -> None:
    minx = max(int(np.floor(pts[:, 0].min())), 0)
    maxx = min(int(np.ceil(pts[:, 0].max())), image.shape[1] - 1)
    miny = max(int(np.floor(pts[:, 1].min())), 0)
    maxy = min(int(np.ceil(pts[:, 1].max())), image.shape[0] - 1)
    if maxx < minx or maxy < miny:
        return
    area = np.cross(pts[1] - pts[0], pts[2] - pts[0])
    if abs(area) < 1e-6:
        return
    xs = np.arange(minx, maxx + 1) + 0.5
    ys = np.arange(miny, maxy + 1) + 0.5
    grid_x, grid_y = np.meshgrid(xs, ys)
    p = np.stack((grid_x - pts[0, 0], grid_y - pts[0, 1]), axis=-1)
    v1 = pts[1] - pts[0]
    v2 = pts[2] - pts[0]
    w1 = (p[..., 0] * v2[1] - v2[0] * p[..., 1]) / area
    w2 = (v1[0] * p[..., 1] - p[..., 0] * v1[1]) / area
    w0 = 1 - w1 - w2
    mask = (w0 >= -0.001) & (w1 >= -0.001) & (w2 >= -0.001)
    z = w0 * zs[0] + w1 * zs[1] + w2 * zs[2]
    update = mask & (z > zbuf[miny : maxy + 1, minx : maxx + 1])
    region = zbuf[miny : maxy + 1, minx : maxx + 1]
    region[update] = z[update]
    image[miny : maxy + 1, minx : maxx + 1][update] = color


def _write_png(path: Path, image: np.ndarray) -> None:
    import zlib

    raw = b"".join(b"\x00" + image[y].tobytes() for y in range(image.shape[0] - 1, -1, -1))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", image.shape[1], image.shape[0], 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9))
    png += chunk(b"IEND", b"")
    path.write_bytes(png)


def main() -> None:
    model = build()
    check(model)
    write_stl(model, STL_PATH)
    render(model)
    print(f"wrote {STL_PATH}")


if __name__ == "__main__":
    main()
