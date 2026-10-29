#!/usr/bin/env python3
"""Robust gingerbread-house corner support for a Bambu Lab P2S.

The clip wraps the outside of one baked corner while the frosting sets.
The inside faces stay a sharp 90 degrees and run all the way down to the
table, so the cookie is not lifted. Everything else is thicker than the
0.6 mm original: a 4 mm wall, a 2.4 mm sole, and solid gussets.

Run from this directory:

    python3 generate.py
"""

from __future__ import annotations

import json
import struct
import zipfile
from collections import Counter
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
from manifold3d import Manifold

ROOT = Path(__file__).resolve().parent
STL_PATH = ROOT / "stl" / "gingerbread_corner_support.stl"
PROJECT_PATH = ROOT / "gingerbread_corner_support.3mf"
PREVIEW_DIR = ROOT / "preview"
BED = 256.0
GINGER = "#C67B3A"

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


def boundary_edge_count(tris: list[tuple[int, int, int]]) -> int:
    edges: Counter[tuple[int, int]] = Counter()
    for a, b, c in tris:
        for edge in ((a, b), (b, c), (c, a)):
            edges[tuple(sorted(edge))] += 1
    return sum(1 for count in edges.values() if count != 2)


def welded_mesh(model: Manifold) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]:
    mesh = model.to_mesh()
    raw_verts = np.asarray(mesh.vert_properties, dtype=np.float64)
    raw_tris = np.asarray(mesh.tri_verts, dtype=np.int64)
    index: dict[tuple[float, float, float], int] = {}
    verts: list[tuple[float, float, float]] = []
    tris: list[tuple[int, int, int]] = []
    for tri in raw_tris:
        ids = []
        for vertex in raw_verts[tri]:
            key = tuple(round(float(axis), 4) for axis in vertex)
            vertex_id = index.get(key)
            if vertex_id is None:
                vertex_id = len(verts)
                index[key] = vertex_id
                verts.append(key)
            ids.append(vertex_id)
        if len(set(ids)) == 3:
            tris.append((ids[0], ids[1], ids[2]))
    if boundary_edge_count(tris) != 0:
        raise SystemExit("corner support mesh is not closed")
    return verts, tris


def project_settings() -> dict:
    """P2S, 0.4 mm nozzle, one spool of PLA Pure.

    The process keys below are the ones that matter for this part, and each
    is named in different_settings_to_system so Studio keeps them instead of
    reverting to the 0.20 mm Standard preset.
    """
    filament = "Bambu PLA Pure @BBL P2S 0.4 nozzle"
    process_overrides = ";".join(
        [
            "enable_support",
            "sparse_infill_density",
            "sparse_infill_pattern",
            "wall_generator",
            "wall_loops",
        ]
    )
    return {
        "name": "project_settings",
        "printer_model": "Bambu Lab P2S",
        "printer_variant": "0.4",
        "nozzle_diameter": ["0.4"],
        "printer_settings_id": "Bambu Lab P2S 0.4 nozzle",
        "print_settings_id": "0.20mm Standard @BBL P2S",
        "filament_settings_id": [filament],
        "filament_colour": [GINGER],
        "filament_type": ["PLA"],
        "filament_diameter": ["1.75"],
        "filament_self_index": ["1"],
        "filament_extruder_variant": ["Direct Drive Standard"],
        "extruder_variant_list": [
            "Direct Drive Standard,Direct Drive High Flow,Direct Drive E3D High Flow"
        ],
        "inherits_group": [
            "0.20mm Standard @BBL P2S",
            filament,
            "Bambu Lab P2S 0.4 nozzle",
        ],
        "different_settings_to_system": [process_overrides, "filament_colour", ""],
        "curr_bed_type": "Textured PEI Plate",
        "wall_loops": "5",
        "sparse_infill_density": "20%",
        "sparse_infill_pattern": "gyroid",
        "wall_generator": "arachne",
        "enable_support": "0",
    }


def write_3mf(path: Path, verts, tris) -> None:
    """Four supports on one P2S plate. The mesh is shared by every copy."""
    span = max(v[0] for v in verts)
    depth = max(v[1] for v in verts)
    gap = 12.0
    origin = (BED - (span * 2 + gap)) / 2
    positions = [
        (origin, origin),
        (origin + span + gap, origin),
        (origin, origin + depth + gap),
        (origin + span + gap, origin + depth + gap),
    ]
    if origin < 8 or origin + span * 2 + gap > BED - 8:
        raise SystemExit("four supports do not fit the P2S bed")

    v_lines = [f'<vertex x="{x:.4f}" y="{y:.4f}" z="{z:.4f}"/>' for x, y, z in verts]
    t_lines = [f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in tris]
    mesh_xml = (
        "<mesh>"
        f"<vertices>{''.join(v_lines)}</vertices>"
        f"<triangles>{''.join(t_lines)}</triangles>"
        "</mesh>"
    )
    name = "Corner support"
    model = f'''<?xml version="1.0" encoding="UTF-8"?>
<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">
  <metadata name="Application">BambuStudio-01.10.02.75</metadata>
  <metadata name="BambuStudio:3mfVersion">1</metadata>
  <metadata name="Title">Gingerbread corner supports</metadata>
  <resources>
    <object id="1" name="{escape(name)}" type="model">{mesh_xml}</object>
  </resources>
  <build>
    {''.join(
        f'<item objectid="1" transform="1 0 0 0 1 0 0 0 1 {x:.4f} {y:.4f} 0.0000" printable="1"/>'
        for x, y in positions
    )}
  </build>
</model>
'''
    instances = "\n".join(
        f'''    <model_instance>
      <metadata key="object_id" value="1"/>
      <metadata key="instance_id" value="{index}"/>
      <metadata key="identify_id" value="{index + 1}"/>
    </model_instance>'''
        for index in range(len(positions))
    )
    assemble = "\n    ".join(
        f'<assemble_item object_id="1" instance_id="{index}" '
        f'transform="1 0 0 0 1 0 0 0 1 {x:.4f} {y:.4f} 0.0000" offset="0 0 0"/>'
        for index, (x, y) in enumerate(positions)
    )
    model_settings = f'''<?xml version="1.0" encoding="UTF-8"?>
<config>
  <object id="1">
    <metadata key="name" value="{escape(name)}"/>
    <metadata key="extruder" value="1"/>
    <part id="1" subtype="normal_part">
      <metadata key="name" value="{escape(name)}"/>
      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>
      <mesh_stat face_count="{len(tris)}" edges_fixed="0" degenerate_facets="0" facets_removed="0" facets_reversed="0" backwards_edges="0"/>
    </part>
  </object>
  <plate>
    <metadata key="plater_id" value="1"/>
    <metadata key="plater_name" value=""/>
    <metadata key="locked" value="false"/>
    <metadata key="bed_type" value="Textured PEI Plate"/>
{instances}
  </plate>
  <assemble>
    {assemble}
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
    settings = project_settings()
    if settings["printer_model"] != "Bambu Lab P2S" or settings["nozzle_diameter"] != ["0.4"]:
        raise SystemExit("project settings are not a single-nozzle P2S")
    if len(settings["inherits_group"]) != 3 or len(settings["different_settings_to_system"]) != 3:
        raise SystemExit("filament preset lists do not match one spool")
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("3D/3dmodel.model", model)
        archive.writestr("Metadata/project_settings.config", json.dumps(settings, indent=2))
        archive.writestr("Metadata/model_settings.config", model_settings)

    with zipfile.ZipFile(path) as archive:
        loaded = json.loads(archive.read("Metadata/project_settings.config"))
        if loaded["wall_loops"] != "5" or loaded["wall_generator"] != "arachne":
            raise SystemExit("3MF process overrides were not written")
        if loaded["filament_settings_id"] != ["Bambu PLA Pure @BBL P2S 0.4 nozzle"]:
            raise SystemExit("3MF filament preset was not written")
        plate = archive.read("3D/3dmodel.model").decode("utf-8")
        if plate.count('objectid="1"') != 4:
            raise SystemExit("3MF does not place four supports")
        if "BambuStudio-01.10.02.75" not in plate:
            raise SystemExit("3MF is not marked as a Bambu Studio project")


def main() -> None:
    model = build()
    check(model)
    write_stl(model, STL_PATH)
    render(model)
    write_3mf(PROJECT_PATH, *welded_mesh(model))
    print(f"wrote {STL_PATH}")
    print(f"wrote {PROJECT_PATH}")


if __name__ == "__main__":
    main()
