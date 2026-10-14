#!/usr/bin/env python3
"""Build a wooden-style name puzzle for a Bambu Lab P2S.

The letters are Lilita One, the same chunky face as the printed FINN puzzle.
A short name stays at that size. A longer name is scaled down in the plane
until the board fits the 256 mm bed with a few millimetres to spare.
Thickness stays 11 mm, and every slot stays 0.40 mm larger than its letter.

Each slot is the letter's outline. Counters (O, R, A, B, and the rest) stay
in the board as islands. The 3MF is a closed mesh and a single-nozzle P2S
project: plate 1 is the board, plate 2 is the letters.
"""

from __future__ import annotations

import json
import struct
import sys
import time
import zipfile
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from xml.sax.saxutils import escape

import cadquery as cq

ROOT = Path(__file__).resolve().parent
FONT = ROOT / "fonts" / "LilitaOne-Regular.ttf"

# Millimetres. The in-plane sizes are the printed FINN letter size.
BED = 256.0
# 4 mm of bed stays clear on each side, plus a little so rounding cannot
# push the board onto the edge.
TARGET_WIDTH = BED - 8.5
MIN_SCALE = 0.25
_FULL_FONT = 90.874509
_FULL_FRAME_X = 13.0
_FULL_FRAME_Y = 14.0
_FULL_GAP = 10.0
_FULL_CORNER = 11.0
FIT_CLEARANCE = 0.40
# Lilita One draws a narrow F. When the name also has an N, the arms are
# stretched so the F sits near that N, the same way as the printed puzzle.
F_TO_N_WIDTH = 0.90
FLOOR = 3.5
WELL_DEPTH = 7.0
LETTER_THICK = 11.0
OUTER_EDGE_R = 1.6
# Bambu Studio lays plates on a grid of bed * (1 + 1/5). Plate 2 starts here.
PLATE_STRIDE = BED * 1.2
MAX_LETTERS = 12

BOARD_COLOR = "#E8C794"
PALETTE = (
    "#DB382E",
    "#2E6BDB",
    "#389E4D",
    "#F2C71F",
    "#E07A2F",
    "#7A4DB8",
    "#E23B8C",
    "#1AA6A6",
)

Progress = Callable[[str], None]


class PuzzleError(Exception):
    """A name the app can explain, or a puzzle that failed its own checks."""


class Plan:
    def __init__(self, scale: float) -> None:
        if scale > 1.0001 or scale < MIN_SCALE:
            raise PuzzleError("That name is too long to fit on one board.")
        self.scale = min(scale, 1.0)
        self.font_size = _FULL_FONT * self.scale
        self.frame_x = _FULL_FRAME_X * self.scale
        self.frame_y = _FULL_FRAME_Y * self.scale
        self.letter_gap = _FULL_GAP * self.scale
        self.corner_r = _FULL_CORNER * self.scale


def sanitize_name(raw: str) -> str:
    """Keep A–Z, drop spaces and everything else, and refuse an empty result."""
    if not isinstance(raw, str) or len(raw) > 80:
        raise PuzzleError("Type a name using the letters A to Z.")
    letters = "".join(ch for ch in raw.upper() if "A" <= ch <= "Z")
    if not letters:
        raise PuzzleError("Type a name using the letters A to Z.")
    if len(letters) > MAX_LETTERS:
        raise PuzzleError(f"Use {MAX_LETTERS} letters or fewer.")
    return letters


def _log(progress: Progress | None, message: str) -> None:
    print(message, flush=True)
    if progress is not None:
        progress(message)


def make_letter(ch: str, size: float, thickness: float) -> cq.Workplane:
    """Chunky uppercase letter, sitting on the XY plane."""
    return cq.Workplane("XY").text(
        ch,
        size,
        thickness,
        combine=False,
        clean=True,
        fontPath=str(FONT),
        halign="left",
        valign="bottom",
    )


def bbox_of(shape: cq.Workplane) -> cq.BoundBox:
    return shape.val().BoundingBox()


def _stem_right(letter: cq.Workplane) -> float:
    """Right edge of the F upright, taken where the arms have not started."""
    bb = bbox_of(letter)
    best = None
    for frac in (0.08, 0.14, 0.20, 0.26):
        y = bb.ymin + bb.ylen * frac
        clip = (
            cq.Workplane("XY")
            .box(bb.xlen + 40, 0.5, bb.zlen + 4, centered=(True, True, True))
            .translate((bb.center.x, y, bb.center.z))
        )
        solids = letter.intersect(clip).solids().vals()
        if len(solids) != 1:
            continue
        xmax = solids[0].BoundingBox().xmax
        if best is None or xmax < best:
            best = xmax
    if best is None:
        raise PuzzleError("The F upright could not be found.")
    return best


def widen_f(letter: cq.Workplane, target_width: float) -> cq.Workplane:
    """Lengthen the arms of F without fattening the upright."""
    bb = bbox_of(letter)
    if bb.xlen >= target_width - 0.2:
        return letter
    stem = _stem_right(letter)
    arm = bb.xmax - stem
    if arm < 2.0:
        raise PuzzleError("The F does not have an arm to widen.")
    scale = ((bb.xmin + target_width) - stem) / arm
    cut_x = stem - 0.4
    right_box = (
        cq.Workplane("XY")
        .box(400, 400, bb.zlen + 20, centered=(True, True, True))
        .translate((cut_x + 200, bb.center.y, bb.center.z))
    )
    right = letter.intersect(right_box)
    left = letter.cut(right_box)
    matrix = cq.Matrix(
        [
            [scale, 0, 0, stem * (1 - scale)],
            [0, 1, 0, 0],
            [0, 0, 1, 0],
        ]
    )
    stretched = cq.Workplane(obj=right.val().transformGeometry(matrix))
    widened = left.union(stretched)
    assert_single_piece(widened, "The widened F")
    return widened


def shape_letters(name: str, letters: list[cq.Workplane]) -> list[cq.Workplane]:
    if "F" not in name or "N" not in name:
        return letters
    n_width = bbox_of(letters[name.index("N")]).xlen
    target = F_TO_N_WIDTH * n_width
    return [widen_f(letter, target) if ch == "F" else letter for ch, letter in zip(name, letters)]


def assert_single_piece(shape: cq.Workplane, label: str) -> None:
    try:
        solids = shape.solids().vals()
        valid = bool(shape.val().isValid())
    except Exception as exc:
        raise PuzzleError(f"{label} did not come out as a solid.") from exc
    if len(solids) != 1 or not valid:
        raise PuzzleError(f"{label} did not come out as a single solid.")


def _offset_wire(wire: cq.Wire, amount: float, label: str) -> cq.Wire:
    last = "the outline split"
    for kind in ("arc", "intersection"):
        try:
            grown = wire.offset2D(amount, kind)
        except Exception as exc:
            last = str(exc)
            continue
        if len(grown) == 1:
            return grown[0]
        last = f"{len(grown)} outlines"
    raise PuzzleError(f"The {label} outline could not be turned into a slot ({last}).")


def letter_pocket(letter: cq.Workplane, label: str) -> cq.Workplane:
    """A prism of the letter outline, grown by the fit clearance on every side.

    A horizontal slice is used instead of the bottom face, which can carry
    a seam. Counters become islands: the hole in the cutter is 0.40 mm
    smaller than the letter's hole, so the island left in the board is loose.
    """
    bb = bbox_of(letter)
    slab = (
        cq.Workplane("XY")
        .box(bb.xlen + 30, bb.ylen + 30, 0.2, centered=(True, True, True))
        .translate((bb.center.x, bb.center.y, bb.zmin + 1.0))
    )
    try:
        faces = letter.intersect(slab).faces(">Z").vals()
    except Exception as exc:
        raise PuzzleError(f"{label} did not slice into one outline.") from exc
    if len(faces) != 1:
        raise PuzzleError(f"{label} did not slice into one outline.")
    face = faces[0]
    outer = face.outerWire()
    outer = outer.translate((0, 0, -outer.Center().z))
    grown = _offset_wire(outer, FIT_CLEARANCE, label)
    pocket = cq.Workplane("XY").add(grown).toPending().extrude(WELL_DEPTH + 3.0)

    for inner in face.innerWires():
        inner = inner.translate((0, 0, -inner.Center().z))
        shrunk = _offset_wire(inner, -FIT_CLEARANCE, f"{label} hole")
        hole_bb = inner.BoundingBox()
        island_bb = shrunk.BoundingBox()
        if island_bb.xlen > hole_bb.xlen - 0.5 or island_bb.ylen > hole_bb.ylen - 0.5:
            raise PuzzleError(f"The {label} hole did not stay open in the slot.")
        island = cq.Workplane("XY").add(shrunk).toPending().extrude(WELL_DEPTH + 3.0)
        pocket = pocket.cut(island)

    assert_single_piece(pocket, f"The {label} slot")
    return pocket


def min_distance(a: cq.Shape, b: cq.Shape) -> float:
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape

    calc = BRepExtrema_DistShapeShape(a.wrapped, b.wrapped)
    if not calc.Perform():
        raise PuzzleError("Could not measure the space between two letters.")
    return float(calc.Value())


def _place_pocket(
    pocket: cq.Workplane, bb: cq.BoundBox, x0: float, y0: float, letter_h: float
) -> cq.Workplane:
    dy = (y0 + letter_h / 2.0) - bb.ylen / 2.0 - bb.ymin
    return pocket.translate((x0 - bb.xmin, dy, 0))


def _x_for_gap(
    prev: cq.Workplane,
    pocket: cq.Workplane,
    bb: cq.BoundBox,
    y0: float,
    letter_h: float,
    gap: float,
) -> float:
    """Left edge of the next letter, so the wood between slots is `gap`.

    Sliding the letter along the row changes the gap by the same amount,
    so a few corrections land on the target.
    """
    x = bbox_of(prev).xmax + 1.0
    for _ in range(6):
        placed = _place_pocket(pocket, bb, x, y0, letter_h)
        error = gap - min_distance(prev.val(), placed.val())
        if abs(error) < 0.02:
            break
        x += error
    return x


def layout_for(letters: list[cq.Workplane], plan: Plan, name: str, progress: Progress | None) -> dict:
    boxes = [bbox_of(letter) for letter in letters]
    letter_h = max(bb.ylen for bb in boxes)
    y0 = plan.frame_y
    pockets = []
    for ch, letter in zip(name, letters):
        _log(progress, f"Cutting the {ch} slot")
        pockets.append(letter_pocket(letter, ch))

    wells = []
    placed = []
    x = plan.frame_x
    for index, (bb, pocket) in enumerate(zip(boxes, pockets)):
        if index:
            x = _x_for_gap(placed[-1], pocket, bb, y0, letter_h, plan.letter_gap)
        wells.append(
            {
                "x0": x,
                "y0": y0,
                "w": bb.xlen,
                "h": letter_h,
                "cx": x + bb.xlen / 2.0,
                "cy": y0 + letter_h / 2.0,
                "letter_bb": bb,
            }
        )
        placed.append(_place_pocket(pocket, bb, x, y0, letter_h))
        if index:
            wood = min_distance(placed[-2].val(), placed[-1].val())
            print(f"  wood before {name[index]}: {wood:.2f} mm", flush=True)

    board_w = wells[-1]["x0"] + wells[-1]["w"] + plan.frame_x
    board_d = plan.frame_y + letter_h + plan.frame_y
    return {
        "wells": wells,
        "board_w": board_w,
        "board_d": board_d,
        "letter_h": letter_h,
        "pockets": placed,
    }


def _try_top_fillet(shape: cq.Workplane) -> cq.Workplane:
    try:
        filleted = shape.faces(">Z").edges().fillet(OUTER_EDGE_R)
        solid = filleted.val()
        if solid.isValid() and len(filleted.solids().vals()) == 1:
            return filleted
    except Exception as exc:
        print(f"  outer edge skipped ({exc})", flush=True)
    return shape


def build_board(layout: dict, plan: Plan) -> cq.Workplane:
    """One solid board. The slots are already positioned; they are cut out of it."""
    board_h = FLOOR + WELL_DEPTH
    board_w = layout["board_w"]
    board_d = layout["board_d"]
    corner = min(plan.corner_r, min(board_w, board_d) / 2.0 - 0.8)
    board = (
        cq.Workplane("XY")
        .center(board_w / 2.0, board_d / 2.0)
        .rect(board_w, board_d)
        .extrude(board_h)
    )
    if corner >= 0.4:
        board = board.edges("|Z").fillet(corner)
    board = _try_top_fillet(board)
    for pocket in layout["pockets"]:
        board = board.cut(pocket.translate((0, 0, FLOOR)))
    try:
        if len(board.solids().vals()) != 1 or not board.val().isValid():
            cleaned = board.clean()
            if cleaned.val().isValid() and len(cleaned.solids().vals()) == 1:
                board = cleaned
    except Exception:
        pass
    assert_single_piece(board, "The board")
    return board


def shift_for(letter: cq.Workplane, well: dict, z: float) -> tuple[float, float, float]:
    bb = bbox_of(letter)
    return (
        well["cx"] - bb.xlen / 2.0 - bb.xmin,
        well["cy"] - bb.ylen / 2.0 - bb.ymin,
        z - bb.zmin,
    )


def place_letter(letter: cq.Workplane, well: dict, z: float) -> cq.Workplane:
    return letter.translate(shift_for(letter, well, z))


def solid_volume(shape: cq.Workplane) -> float:
    solids = shape.solids().vals()
    if not solids:
        return 0.0
    return float(sum(solid.Volume() for solid in solids))


def side_clearance(letter: cq.Workplane, board: cq.Workplane, board_w: float, board_d: float) -> float:
    """Gap between the letter and the well wall, taken at mid-depth.

    The slice stays off the floor and the top rim, so the nearest board
    surface is the wall rather than the bottom of the pocket.
    """
    z_mid = FLOOR + WELL_DEPTH / 2.0
    clip = (
        cq.Workplane("XY")
        .box(board_w + 20, board_d + 20, 0.4, centered=(True, True, True))
        .translate((board_w / 2.0, board_d / 2.0, z_mid))
    )
    clipped = letter.intersect(clip)
    return min_distance(clipped.val(), board.val())


def estimate_full_width(name: str) -> float:
    """Board width at the full FINN letter size, from bounding boxes.

    The real layout measures pocket walls, which sit 0.40 mm outside the
    letter. This estimate is only the first guess; the build measures again.
    """
    probe = 36.0
    widths = []
    for ch in name:
        bb = bbox_of(make_letter(ch, probe, 2.0))
        widths.append(bb.xlen * (_FULL_FONT / probe))
    gaps = max(len(name) - 1, 0)
    pitch = _FULL_GAP + 2 * FIT_CLEARANCE
    return sum(widths) + gaps * pitch + 2 * _FULL_FRAME_X


def choose_plan(name: str, progress: Progress | None) -> tuple[Plan, list[cq.Workplane], dict]:
    _log(progress, "Measuring the row")
    estimated = estimate_full_width(name)
    scale = 1.0 if estimated <= TARGET_WIDTH else TARGET_WIDTH / estimated
    if scale < MIN_SCALE:
        raise PuzzleError("That name is too long to fit on one board.")

    letters: list[cq.Workplane] = []
    layout: dict = {}
    plan = Plan(scale)
    for attempt in range(3):
        plan = Plan(scale)
        if attempt == 0 and scale < 0.995:
            _log(progress, "Scaling the row so it fits the printer")
        elif attempt:
            _log(progress, "Adjusting the size")
        letters = []
        for ch in name:
            _log(progress, f"Shaping {ch}")
            letter = make_letter(ch, plan.font_size, LETTER_THICK)
            assert_single_piece(letter, ch)
            letters.append(letter)
        letters = shape_letters(name, letters)
        layout = layout_for(letters, plan, name, progress)
        board_w = layout["board_w"]
        board_d = layout["board_d"]
        _log(progress, f"Board is {board_w:.1f} × {board_d:.1f} mm")
        fits = board_w <= TARGET_WIDTH + 0.05 and board_d <= BED - 8.5
        if fits and (scale >= 0.999 or TARGET_WIDTH - board_w <= 4.0):
            break
        if fits:
            grown = min(1.0, scale * (TARGET_WIDTH / board_w))
            if grown < scale * 1.015:
                break
            scale = grown
            continue
        scale *= min(TARGET_WIDTH / board_w, (BED - 8.5) / board_d)
        if scale < MIN_SCALE:
            raise PuzzleError("That name is too long to fit on one board.")
    if layout["board_w"] > TARGET_WIDTH + 0.05 or layout["board_d"] > BED - 8.5:
        raise PuzzleError("The board does not fit the printer.")
    return plan, letters, layout


def fits_small_opening(bb: cq.BoundBox) -> bool:
    """True when the part can fall through a 31.7 × 57.1 mm opening.

    Some face of the box has to be the depth, and the other two sides have
    to fit across the round opening together.
    """
    dims = (bb.xlen, bb.ylen, bb.zlen)
    for index, depth in enumerate(dims):
        others = [dims[i] for i in range(3) if i != index]
        diagonal = (others[0] ** 2 + others[1] ** 2) ** 0.5
        if depth < 57.1 and diagonal < 31.7:
            return True
    return False


def to_bed(shape: cq.Workplane) -> cq.Workplane:
    bb = bbox_of(shape)
    return shape.translate((-bb.xmin, -bb.ymin, -bb.zmin))


def stl_mesh(path: Path) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]:
    """Load a binary STL and weld vertices so the 3MF has no open edges.

    CadQuery's raw tessellation leaves cracks. The STL exporter welds them,
    and Bambu Studio reports those cracks as open edges.
    """
    data = path.read_bytes()
    if len(data) < 84:
        raise PuzzleError(f"{path.name} is not a mesh.")
    count = struct.unpack_from("<I", data, 80)[0]
    expected = 84 + count * 50
    if count < 100 or expected != len(data):
        raise PuzzleError(f"{path.name} is not a closed mesh.")
    index: dict[tuple[float, float, float], int] = {}
    verts: list[tuple[float, float, float]] = []
    tris: list[tuple[int, int, int]] = []
    offset = 84
    for _ in range(count):
        values = struct.unpack_from("<12fH", data, offset)
        ids = []
        for corner in range(3):
            key = tuple(round(values[3 + 3 * corner + axis], 4) for axis in range(3))
            vertex_id = index.get(key)
            if vertex_id is None:
                vertex_id = len(verts)
                index[key] = vertex_id
                verts.append(key)
            ids.append(vertex_id)
        if len(set(ids)) == 3:
            tris.append((ids[0], ids[1], ids[2]))
        offset += 50
    return verts, tris


def boundary_edge_count(tris: list[tuple[int, int, int]]) -> int:
    edges: Counter[tuple[int, int]] = Counter()
    for a, b, c in tris:
        for edge in ((a, b), (b, c), (c, a)):
            edges[tuple(sorted(edge))] += 1
    return sum(1 for count in edges.values() if count != 2)


def export_stl(shape: cq.Workplane, path: Path, tolerance: float, angular: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cq.exporters.export(shape, str(path), tolerance=tolerance, angularTolerance=angular)


def project_settings(colors: list[str]) -> dict:
    """Single-nozzle P2S project. One filament slot per color.

    extruder_type stays unset so Bambu Studio keeps the printer's own value
    instead of popping a substitution dialog. Nothing here replaces the
    filament start G-code.
    """
    count = len(colors)
    filaments = ["Bambu PLA Basic @BBL P2S"] * count
    return {
        "name": "project_settings",
        "printer_model": "Bambu Lab P2S",
        "printer_variant": "0.4",
        "nozzle_diameter": ["0.4"],
        "printer_settings_id": "Bambu Lab P2S 0.4 nozzle",
        "print_settings_id": "0.20mm Standard @BBL P2S",
        "filament_settings_id": filaments,
        "filament_colour": colors,
        "filament_type": ["PLA"] * count,
        "filament_diameter": ["1.75"] * count,
        "filament_self_index": [str(i) for i in range(1, count + 1)],
        "filament_extruder_variant": ["Direct Drive Standard"] * count,
        "extruder_variant_list": [
            "Direct Drive Standard,Direct Drive High Flow,Direct Drive E3D High Flow"
        ],
        "inherits_group": [
            "0.20mm Standard @BBL P2S",
            *filaments,
            "Bambu Lab P2S 0.4 nozzle",
        ],
        "different_settings_to_system": ["", *["filament_colour"] * count, ""],
    }


def _fits_on_plate(origin: tuple[float, float, float], size: tuple[float, float], plate: int) -> None:
    x0, y0, _z = origin
    width, depth = size
    stride = 0.0 if plate == 1 else PLATE_STRIDE
    local_x = x0 - stride
    if local_x < 4 or y0 < 4 or local_x + width > BED - 4 or y0 + depth > BED - 4:
        raise PuzzleError(
            f"A part on plate {plate} is {width:.0f} × {depth:.0f} mm and does not fit the bed."
        )


def pack_letters(bed_letters: list[cq.Workplane]) -> list[tuple[float, float, float]]:
    """Lay letters on plate 2 in rows, centered, with a gap a finger can use."""
    sizes = [bbox_of(letter) for letter in bed_letters]
    gap = 8.0
    margin = 8.0
    max_w = BED - 2 * margin
    rows: list[list[int]] = []
    current: list[int] = []
    current_w = 0.0
    for index, size in enumerate(sizes):
        extra = size.xlen if not current else gap + size.xlen
        if current and current_w + extra > max_w:
            rows.append(current)
            current = [index]
            current_w = size.xlen
        else:
            current.append(index)
            current_w += extra
    if current:
        rows.append(current)

    row_heights = []
    row_widths = []
    for row in rows:
        row_heights.append(max(sizes[i].ylen for i in row))
        row_widths.append(sum(sizes[i].xlen for i in row) + gap * (len(row) - 1))
    total_h = sum(row_heights) + gap * (len(rows) - 1)
    if total_h > BED - 2 * margin:
        raise PuzzleError("The letters do not fit on the second plate.")

    positions: list[tuple[float, float, float] | None] = [None] * len(bed_letters)
    y = (BED - total_h) / 2.0
    for row, row_w, row_h in zip(rows, row_widths, row_heights):
        x = PLATE_STRIDE + (BED - row_w) / 2.0
        for index in row:
            bb = sizes[index]
            pos = (x, y + (row_h - bb.ylen) / 2.0, 0.0)
            _fits_on_plate(pos, (bb.xlen, bb.ylen), 2)
            positions[index] = pos
            x += bb.xlen + gap
        y += row_h + gap
    return positions  # type: ignore[return-value]


def write_3mf(path: Path, objects: list[dict], colors: list[str], title: str) -> None:
    """Bambu Studio project for a P2S with a 0.4 mm nozzle and two plates."""

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
    plate_instances: dict[int, list[str]] = {1: [], 2: []}
    assemble_items = []
    for index, obj in enumerate(objects):
        object_id = index + 1
        verts, tris = obj["mesh"]
        if boundary_edge_count(tris) != 0:
            raise PuzzleError(f"{obj['name']} is not a closed mesh.")
        if not 1 <= obj["extruder"] <= len(colors):
            raise PuzzleError(f"{obj['name']} points at a missing color.")
        object_xml.append(
            f'<object id="{object_id}" name="{escape(obj["name"])}" type="model">'
            f"{mesh_xml(verts, tris)}"
            "</object>"
        )
        x, y, z = obj["pos"]
        build_items.append(
            f'<item objectid="{object_id}" transform="1 0 0 0 1 0 0 0 1 {x:.4f} {y:.4f} {z:.4f}" printable="1"/>'
        )
        model_objects.append(
            f'''  <object id="{object_id}">
    <metadata key="name" value="{escape(obj["name"])}"/>
    <metadata key="extruder" value="{obj["extruder"]}"/>
    <part id="{object_id}" subtype="normal_part">
      <metadata key="name" value="{escape(obj["name"])}"/>
      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>
      <mesh_stat face_count="{len(tris)}" edges_fixed="0" degenerate_facets="0" facets_removed="0" facets_reversed="0" backwards_edges="0"/>
    </part>
  </object>'''
        )
        plate_instances[obj["plate"]].append(
            f'''    <model_instance>
      <metadata key="object_id" value="{object_id}"/>
      <metadata key="instance_id" value="0"/>
      <metadata key="identify_id" value="{object_id}"/>
    </model_instance>'''
        )
        assemble_items.append(
            f'<assemble_item object_id="{object_id}" instance_id="0" '
            f'transform="1 0 0 0 1 0 0 0 1 {x:.4f} {y:.4f} {z:.4f}" offset="0 0 0"/>'
        )

    settings = project_settings(colors)
    filament_count = len(colors)
    if settings["printer_model"] != "Bambu Lab P2S" or settings["nozzle_diameter"] != ["0.4"]:
        raise PuzzleError("The project is not a single-nozzle P2S.")
    if "extruder_type" in settings or "filament_start_gcode" in settings:
        raise PuzzleError("The project changes printer settings it should leave alone.")
    if len(settings["inherits_group"]) != filament_count + 2:
        raise PuzzleError("The filament list is the wrong length.")
    if len(settings["different_settings_to_system"]) != filament_count + 2:
        raise PuzzleError("The filament overrides are the wrong length.")
    if not plate_instances[1] or not plate_instances[2]:
        raise PuzzleError("The file needs a board plate and a letter plate.")

    def plate_xml(plate_id: int, name: str) -> str:
        return f'''  <plate>
    <metadata key="plater_id" value="{plate_id}"/>
    <metadata key="plater_name" value="{escape(name)}"/>
    <metadata key="locked" value="false"/>
{chr(10).join(plate_instances[plate_id])}
  </plate>'''

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
{plate_xml(1, "Board")}
{plate_xml(2, "Letters")}
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
        # The model has to be stored before model_settings. Studio indexes
        # objects while reading the archive, then looks them up from the plate.
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("3D/3dmodel.model", model)
        zf.writestr("Metadata/project_settings.config", json.dumps(settings, indent=2))
        zf.writestr("Metadata/model_settings.config", model_settings)


def assert_3mf(path: Path, filament_count: int) -> None:
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        if names.index("3D/3dmodel.model") > names.index("Metadata/model_settings.config"):
            raise PuzzleError("The 3MF archive is ordered wrong.")
        loaded = json.loads(zf.read("Metadata/project_settings.config"))
        model_xml = zf.read("3D/3dmodel.model").decode("utf-8")
        settings_xml = zf.read("Metadata/model_settings.config").decode("utf-8")
    if loaded.get("printer_model") != "Bambu Lab P2S" or loaded.get("printer_variant") != "0.4":
        raise PuzzleError("The 3MF is not a P2S project.")
    if loaded.get("nozzle_diameter") != ["0.4"]:
        raise PuzzleError("The 3MF nozzle is not 0.4 mm.")
    if "extruder_type" in loaded or "filament_start_gcode" in loaded:
        raise PuzzleError("The 3MF changes printer settings it should leave alone.")
    if len(loaded["inherits_group"]) != filament_count + 2:
        raise PuzzleError("The filament list is the wrong length.")
    diffs = loaded["different_settings_to_system"]
    if len(diffs) != filament_count + 2 or diffs[0] != "" or diffs[-1] != "":
        raise PuzzleError("The filament overrides are the wrong length.")
    if any(item != "filament_colour" for item in diffs[1:-1]):
        raise PuzzleError("The 3MF overrides more than the filament color.")
    if len(loaded["filament_colour"]) != filament_count:
        raise PuzzleError("The 3MF is missing a filament color.")
    if "BambuStudio-01.10.02.75" not in model_xml:
        raise PuzzleError("The 3MF is not marked as a Bambu Studio project.")
    if settings_xml.count("<plate>") != 2:
        raise PuzzleError("The 3MF should have a board plate and a letter plate.")


def _mesh_payload(shape: cq.Workplane, tolerance: float, angular: float, origin: tuple[float, float]) -> dict:
    """Tessellate for the browser. Z-up becomes Y-up, and the board is centered."""
    verts, tris = shape.val().tessellate(tolerance, angular)
    ox, oy = origin
    positions: list[float] = []
    for vertex in verts:
        positions.append(round(float(vertex.x) - ox, 2))
        positions.append(round(float(vertex.z), 2))
        positions.append(round(-(float(vertex.y) - oy), 2))
    indices = [int(corner) for tri in tris for corner in tri]
    return {"positions": positions, "indices": indices}


def _letter_object_name(ch: str, seen: Counter[str]) -> str:
    seen[ch] += 1
    if seen[ch] == 1:
        return f"Letter {ch}"
    return f"Letter {ch} {seen[ch]}"


def _check_fit(
    name: str,
    letters: list[cq.Workplane],
    layout: dict,
    board: cq.Workplane,
    progress: Progress | None,
) -> list[float]:
    woods = []
    pockets = layout["pockets"]
    for index in range(len(pockets) - 1):
        woods.append(min_distance(pockets[index].val(), pockets[index + 1].val()))
    if woods:
        spread = max(woods) - min(woods)
        mean = sum(woods) / len(woods)
        gap = layout["letter_gap"]
        if spread > 0.25 or abs(mean - gap) > 0.25:
            raise PuzzleError("The spaces between the letters did not come out equal.")

    clearances = []
    placed = [place_letter(letter, well, FLOOR) for letter, well in zip(letters, layout["wells"])]
    for ch, letter in zip(name, placed):
        _log(progress, f"Checking {ch}")
        hit = solid_volume(board.intersect(letter))
        if hit > 0.5:
            raise PuzzleError(f"{ch} collides with its slot.")
        gap_mm = side_clearance(letter, board, layout["board_w"], layout["board_d"])
        clearances.append(gap_mm)
        if not 0.25 <= gap_mm <= 0.60:
            raise PuzzleError(f"The {ch} slot is {gap_mm:.2f} mm, and it needs to be about 0.40 mm.")
        bb = bbox_of(letter)
        proud = bb.zmax - (FLOOR + WELL_DEPTH)
        if bb.zmin < FLOOR - 0.05 or not 3.5 <= proud <= 4.5:
            raise PuzzleError(f"{ch} does not sit in its slot.")
    return clearances


def generate(raw_name: str, out_dir: Path, progress: Progress | None = None) -> dict:
    """Build the puzzle, write puzzle.3mf and model.json, and return the summary."""
    started = time.perf_counter()
    if not FONT.exists():
        raise PuzzleError("The letter font is missing.")
    name = sanitize_name(raw_name)
    out_dir.mkdir(parents=True, exist_ok=True)

    plan, letters, layout = choose_plan(name, progress)
    layout["letter_gap"] = plan.letter_gap
    _log(progress, "Cutting the slots into the board")
    board = build_board(layout, plan)
    board_bb = bbox_of(board)
    board_h = FLOOR + WELL_DEPTH
    if abs(board_bb.zlen - board_h) > 0.05:
        raise PuzzleError("The board came out the wrong thickness.")
    if board_bb.xlen > BED - 8 or board_bb.ylen > BED - 8:
        raise PuzzleError("The board does not fit the printer.")

    _log(progress, "Checking the fit")
    clearances = _check_fit(name, letters, layout, board, progress)

    warnings = []
    letter_meta = []
    for index, (ch, letter) in enumerate(zip(name, letters)):
        bb = bbox_of(letter)
        if abs(bb.zlen - LETTER_THICK) > 0.05:
            raise PuzzleError(f"{ch} came out the wrong thickness.")
        if fits_small_opening(bb):
            warnings.append(
                f"{ch} is {bb.xlen:.0f} × {bb.ylen:.0f} × {bb.zlen:.0f} mm and can drop "
                "through the printer's small-parts opening."
            )
        letter_meta.append(
            {
                "char": ch,
                "color": PALETTE[index % len(PALETTE)],
                "width": round(bb.xlen, 1),
                "depth": round(bb.ylen, 1),
            }
        )

    _log(progress, "Writing the print file")
    stl_dir = out_dir / "stl"
    board_path = stl_dir / "board.stl"
    export_stl(to_bed(board), board_path, 0.08, 0.1)
    bed_letters = []
    letter_paths = []
    for ch, letter in zip(name, letters):
        path = stl_dir / f"letter_{ch}_{len(letter_paths) + 1}.stl"
        bed = to_bed(letter)
        export_stl(bed, path, 0.045, 0.06)
        bed_letters.append(bed)
        letter_paths.append(path)

    bed_board = to_bed(board)
    board_size = bbox_of(bed_board)
    board_pos = ((BED - board_size.xlen) / 2.0, (BED - board_size.ylen) / 2.0, 0.0)
    _fits_on_plate(board_pos, (board_size.xlen, board_size.ylen), 1)
    letter_pos = pack_letters(bed_letters)

    colors = [BOARD_COLOR, *[item["color"] for item in letter_meta]]
    seen: Counter[str] = Counter()
    objects = [
        {
            "name": "Board",
            "extruder": 1,
            "plate": 1,
            "mesh": stl_mesh(board_path),
            "pos": board_pos,
        }
    ]
    for index, (meta, path) in enumerate(zip(letter_meta, letter_paths)):
        objects.append(
            {
                "name": _letter_object_name(meta["char"], seen),
                "extruder": index + 2,
                "plate": 2,
                "mesh": stl_mesh(path),
                "pos": letter_pos[index],
            }
        )
    three_mf = out_dir / "puzzle.3mf"
    write_3mf(three_mf, objects, colors, f"{name} name puzzle")
    assert_3mf(three_mf, len(colors))

    _log(progress, "Building the preview")
    # Lift the preview letters a hair so their floor does not flicker against
    # the slot bottom. The print file keeps the real 3.5 mm floor.
    origin = (board_bb.center.x, board_bb.center.y)
    board_mesh = _mesh_payload(board, 0.7, 0.35, origin)
    letter_views = []
    for meta, letter, well in zip(letter_meta, letters, layout["wells"]):
        placed = place_letter(letter, well, FLOOR + 0.2)
        view = dict(meta)
        view.update(_mesh_payload(placed, 0.45, 0.25, origin))
        letter_views.append(view)

    summary = {
        "name": name,
        "width": round(board_bb.xlen, 1),
        "depth": round(board_bb.ylen, 1),
        "height": round(board_h, 1),
        "letter_thickness": LETTER_THICK,
        "clearance": FIT_CLEARANCE,
        "letter_gap": round(plan.letter_gap, 2),
        "scale": round(plan.scale, 4),
        "scaled": plan.scale < 0.995,
        "font_size": round(plan.font_size, 2),
        "clearances": [round(gap, 3) for gap in clearances],
        "warnings": warnings,
        "board_color": BOARD_COLOR,
        "letters": letter_meta,
    }
    preview = dict(summary)
    preview["board"] = board_mesh
    preview["letters"] = letter_views
    (out_dir / "model.json").write_text(json.dumps(preview, separators=(",", ":")), encoding="utf-8")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    _log(progress, f"Ready ({time.perf_counter() - started:.0f}s)")
    return summary


def main(argv: list[str]) -> None:
    raw = argv[1] if len(argv) > 1 else "ROB"
    out = Path(argv[2]) if len(argv) > 2 else Path("/tmp/name-puzzles") / sanitize_name(raw)
    summary = generate(raw, out)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    try:
        main(sys.argv)
    except PuzzleError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
