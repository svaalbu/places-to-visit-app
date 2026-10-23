#!/usr/bin/env python3
"""Build the three-row shelf as it sits in the cabinet, with small shoes.

Writes a viewable 3D model and the pictures that show how four printed halves
become two grids.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import Polygon

import generate as g

HERE = Path(__file__).resolve().parent
PREVIEW = HERE / "preview"

SHOE_LENGTH = 250.0
SHOE_WIDTH = 82.0
SHOE_HEIGHT = 96.0


def font(size: int):
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def paint(mesh: trimesh.Trimesh, rgb: tuple[float, float, float]) -> trimesh.Trimesh:
    out = mesh.copy()
    color = np.array([int(c * 255) for c in rgb] + [255], dtype=np.uint8)
    out.visual.face_colors = np.tile(color, (len(out.faces), 1))
    return out


def shoe_mesh() -> trimesh.Trimesh:
    """One low shoe, toe toward -Y, heel toward +Y, sole on z=0."""
    profile = Polygon(
        [
            (0, 0),
            (SHOE_LENGTH, 0),
            (SHOE_LENGTH, 72),
            (214, SHOE_HEIGHT),
            (160, 64),
            (90, 46),
            (28, 30),
            (0, 18),
        ]
    )
    mesh = trimesh.creation.extrude_polygon(profile, SHOE_WIDTH)
    # Extrude leaves length on X, height on Y, width on Z.
    mesh.apply_transform(np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]]))
    mesh.apply_translation((-SHOE_WIDTH / 2, -SHOE_LENGTH / 2, 0))
    return mesh


def place_shoes(level_z: list[float]) -> list[trimesh.Trimesh]:
    """Two shoes per row, heels toward the front of the cabinet (+Y)."""
    template = shoe_mesh()
    # Keep the pair between the side legs, and the heel short of the front legs.
    gap = 8.0
    left_x = -(gap / 2 + SHOE_WIDTH / 2)
    right_x = gap / 2 + SHOE_WIDTH / 2
    heel_y = 150.0
    shoes = []
    for z in level_z:
        for x in (left_x, right_x):
            shoe = template.copy()
            shoe.apply_translation((x, heel_y - SHOE_LENGTH / 2, z + 0.4))
            shoes.append(shoe)
    return shoes


def cabinet_frame(thickness: float = 6.0) -> trimesh.Trimesh:
    w, d, h = g.OPENING_W, g.OPENING_D, g.OPENING_H
    corners = [(x, y, z) for x in (-w / 2, w / 2) for y in (-d / 2, d / 2) for z in (0.0, h)]
    edges = []
    for i, a in enumerate(corners):
        for b in corners[i + 1 :]:
            same = sum(abs(a[k] - b[k]) < 1e-6 for k in range(3))
            if same != 2:
                continue
            start = np.array(a, dtype=float)
            end = np.array(b, dtype=float)
            length = float(np.linalg.norm(end - start))
            bar = trimesh.creation.box(extents=(thickness, thickness, length))
            direction = (end - start) / length
            bar.apply_transform(trimesh.geometry.align_vectors([0, 0, 1], direction))
            bar.apply_translation((start + end) / 2)
            edges.append(bar)
    return trimesh.util.concatenate(edges)


def halves(half: trimesh.Trimesh, height: float) -> tuple[trimesh.Trimesh, trimesh.Trimesh]:
    one = g.to_use(half, height)
    other = g.to_use(g.rotated_mate(half), height)
    if one.centroid[1] >= other.centroid[1]:
        return one, other
    return other, one


def shift(mesh: trimesh.Trimesh, x=0.0, y=0.0, z=0.0) -> trimesh.Trimesh:
    out = mesh.copy()
    out.apply_translation((x, y, z))
    return out


def caption(image: Image.Image, title: str, note: str) -> Image.Image:
    bar_h = 78
    canvas = Image.new("RGB", (image.width, image.height + bar_h), (246, 244, 241))
    canvas.paste(image, (0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.text((28, image.height + 12), title, fill=(32, 30, 28), font=font(24))
    draw.text((28, image.height + 44), note, fill=(70, 64, 58), font=font(16))
    return canvas


def draw_fit_diagram(path: Path, height: float) -> None:
    """Side and front of the cabinet with the two grids and six small shoes."""
    image = Image.new("RGB", (1480, 860), (246, 244, 241))
    draw = ImageDraw.Draw(image)
    draw.text((36, 24), "Small-shoe shelf inside the cabinet", fill=(32, 30, 28), font=font(28))
    draw.text(
        (36, 64),
        "Four printed halves. Two of them glue into each grid. The upper grid stands on the lower one.",
        fill=(70, 64, 58),
        font=font(18),
    )

    def shoe_poly(ox, oy, scale, z_base, face_right):
        profile = [(0, 0), (250, 0), (250, 72), (214, 96), (160, 64), (90, 46), (28, 30), (0, 18)]
        pts = []
        for length, shoe_z in profile:
            along = length if face_right else SHOE_LENGTH - length
            x = ox + (40 + along) * scale
            y = oy - (z_base + shoe_z) * scale
            pts.append((x, y))
        draw.polygon(pts, fill=(58, 62, 68))

    def panel(origin, across_mm, label, shoes_across):
        ox, oy = origin
        scale = 1.35
        cw, ch = across_mm * scale, g.OPENING_H * scale
        draw.text((ox, oy - 28), label, fill=(40, 36, 32), font=font(18))
        draw.rectangle([ox, oy, ox + cw, oy + ch], outline=(92, 74, 56), width=7, fill=(232, 224, 214))
        # Two deck bands and their legs.
        for level in (0, 1):
            z_foot = level * (height + g.DECK_T)
            z_top = z_foot + height + g.DECK_T
            y_top = oy + ch - z_top * scale
            y_under = oy + ch - (z_foot + height) * scale
            draw.rectangle([ox + 8, y_top, ox + cw - 8, y_under], fill=(214, 214, 210))
            for end in (8, cw / 2 - 6, cw - 20):
                draw.rectangle([ox + end, y_under, ox + end + 12, oy + ch - z_foot * scale], fill=(186, 186, 182))
        if shoes_across == 1:
            for level in range(3):
                shoe_poly(ox, oy + ch, scale, level * (height + g.DECK_T), face_right=True)
        else:
            for level in range(3):
                z = level * (height + g.DECK_T)
                y0 = oy + ch - (z + 78) * scale
                y1 = oy + ch - z * scale
                inset = 22
                mid = cw / 2
                draw.rounded_rectangle([ox + inset, y0, ox + mid - 8, y1], radius=8, fill=(58, 62, 68))
                draw.rounded_rectangle([ox + mid + 8, y0, ox + cw - inset, y1], radius=8, fill=(58, 62, 68))

    panel((48, 150), g.OPENING_D, "From the side  ·  380 mm deep", 1)
    panel((760, 150), g.OPENING_W, "From the front  ·  210 mm wide", 2)

    draw.text(
        (760, 700),
        "Each dark shape is one low shoe, 96 mm tall.\n"
        "A row is 125 mm clear, so the shoe has room\n"
        "under the grid above it. One pair per row.",
        fill=(50, 46, 42),
        font=font(18),
    )
    image.save(path)


def export_scene(path: Path, geometries: list[tuple[str, trimesh.Trimesh, tuple[float, float, float]]]) -> None:
    scene = trimesh.Scene()
    for name, mesh, rgb in geometries:
        scene.add_geometry(paint(mesh, rgb), geom_name=name, node_name=name)
    path.parent.mkdir(parents=True, exist_ok=True)
    scene.export(path)
    print(f"wrote {path}")


def main():
    PREVIEW.mkdir(parents=True, exist_ok=True)
    height = g.leg_height(2)
    deck = g.build_deck()
    half = g.build_half(deck, height)
    front, back = halves(half, height)
    pitch = height + g.DECK_T
    upper_front = shift(front, z=pitch)
    upper_back = shift(back, z=pitch)

    shoes = place_shoes([0.0, pitch, pitch * 2])
    frame = cabinet_frame()
    lines = g.cabinet_lines()

    shelf_color = (0.90, 0.90, 0.87)
    shelf_color_b = (0.78, 0.80, 0.78)
    upper_color = (0.84, 0.86, 0.88)
    upper_color_b = (0.72, 0.76, 0.80)
    shoe_color = (0.22, 0.24, 0.27)
    wood = (0.62, 0.50, 0.38)

    assembled = [
        (back, shelf_color_b),
        (front, shelf_color),
        (upper_back, upper_color_b),
        (upper_front, upper_color),
        *[(shoe, shoe_color) for shoe in shoes],
    ]
    iso = PREVIEW / "_iso.png"
    g.rasterize(assembled, iso, az=-38, el=24, width=1600, height=1100, lines=lines, margin=0.06)
    caption(
        Image.open(iso),
        "Assembled shelf, small shoes",
        "The brown outline is the inside of the cabinet, 210 wide × 380 deep × 390 tall. Three pairs, one pair on each row.",
    ).save(PREVIEW / "assembled_iso.png")

    exploded = [
        (shift(back, y=-90), shelf_color_b),
        (shift(front, y=90), shelf_color),
        (shift(upper_back, y=-90, z=80), upper_color_b),
        (shift(upper_front, y=90, z=80), upper_color),
    ]
    exp = PREVIEW / "_exploded.png"
    g.rasterize(exploded, exp, az=-38, el=24, width=1600, height=1100, lines=lines, margin=0.05)
    caption(
        Image.open(exp),
        "The four pieces, pulled apart",
        "Glue a light half to a dark half along the teeth. Stack the second pair on top of the first. Print the same file four times.",
    ).save(PREVIEW / "assembled_exploded.png")

    side = PREVIEW / "_side3d.png"
    side_view = np.array([[0, 1, 0], [0, 0, 1], [1, 0, 0]], dtype=float)
    g.rasterize(assembled, side, width=1500, height=900, lines=lines, view=side_view, margin=0.07)
    caption(
        Image.open(side),
        "Same shelf from the side",
        "125 mm of open height on every row. The shoes are 96 mm tall, so they sit under the next grid.",
    ).save(PREVIEW / "assembled_side.png")

    draw_fit_diagram(PREVIEW / "how_it_fits.png", height)

    geometries = [
        ("lower_back", back, shelf_color_b),
        ("lower_front", front, shelf_color),
        ("upper_back", upper_back, upper_color_b),
        ("upper_front", upper_front, upper_color),
        ("cabinet", frame, wood),
    ]
    for index, shoe in enumerate(shoes, start=1):
        geometries.append((f"shoe_{index}", shoe, shoe_color))
    export_scene(PREVIEW / "assembled_small_shoes.glb", geometries)

    # One mesh for viewers that only open STL. Cabinet and shoes included.
    merged = trimesh.util.concatenate([mesh for _, mesh, _ in geometries])
    stl_path = HERE / "stl" / "assembled_small_shoes_VIEW_ONLY.stl"
    merged.export(stl_path)
    print(f"wrote {stl_path} extents {merged.extents.round(1).tolist()}")

    for temporary in (iso, exp, side):
        temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
