#!/usr/bin/env python3
"""Build a wooden-style name puzzle for a Bambu Lab P2S.

The letters are Lilita One, the same chunky face as the printed FINN puzzle.
The board is always turned 45 degrees on the bed, so a longer name can use
the diagonal. A short name stays at the FINN letter size. A longer name is
scaled down in the plane until that turned board still clears the bed.
Thickness stays 11 mm, and every slot stays 0.40 mm larger than its letter.

Each slot is the letter's outline. Counters (O, R, A, B, and the rest) stay
in the board as islands. The 3MF is a closed mesh and a single-nozzle P2S
project: plate 1 is the board, and the letters follow with at most four per plate.

Letters print with the show face up. The top of that face is ironed.
Magnet pockets sit near the bed, and the rest of the letter prints over
them so the discs stay buried.

Optional 5x2 mm magnet pockets sit inside each letter (two) and in the
board floor under that letter. The project pauses before the layer that
covers them. Letter plates print one object at a time.
"""

from __future__ import annotations

import json
import math
import struct
import sys
import time
import zipfile
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from xml.sax.saxutils import escape

try:
    import cadquery as cq
except ModuleNotFoundError:
    cq = None  # type: ignore[assignment]

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
# 5x2 mm discs. The pocket is a little wider and a little deeper so a magnet
# from a loose batch drops in and sits below the layer that closes over it.
LAYER = 0.20
MAGNET_D = 5.0
MAGNET_T = 2.0
POCKET_D = 5.4
POCKET_H = 2.2
POCKET_R = POCKET_D / 2.0
# Two layers on the bed, then the pocket. The pause is the first layer that
# covers the magnet. The rest of the letter prints over that cover.
LETTER_SKIN = 0.40
LETTER_CAVITY_TOP = LETTER_SKIN + POCKET_H
LETTER_PAUSE_Z = round(LETTER_CAVITY_TOP + LAYER, 2)
# The board floor is 3.5 mm. The pocket ends on a layer line and leaves
# 0.5 mm of floor over the magnet, under the slot.
BOARD_CAVITY_TOP = 3.0
BOARD_CAVITY_BOTTOM = BOARD_CAVITY_TOP - POCKET_H
BOARD_PAUSE_Z = BOARD_CAVITY_TOP + LAYER
# Bambu's own pause. The printer waits here until the resume button is pressed.
PAUSE_GCODE = "M400 U1"
# Bambu Studio lays plates on a grid of bed * (1 + 1/5). Plate 2 starts here.
PLATE_STRIDE = BED * 1.2
MAX_LETTERS = 12
MAX_LETTERS_PER_PLATE = 4
# P2S by-object printing needs more than 57 mm between objects. The gap is
# the closest the boxes can be, including on a diagonal.
OBJECT_GAP = 58.0

_CADQUERY_HINT = (
    "CadQuery is not installed in this Python. The backend virtualenv is "
    "Python 3.9, and this app needs Python 3.11 or newer. On a Mac, "
    "Homebrew's Python works: brew install python@3.11. Then, from the "
    "name-puzzle-app folder, run: python3.11 -m venv .venv && "
    "source .venv/bin/activate && pip install -r requirements.txt && "
    "python -m uvicorn app:app --host 0.0.0.0 --port 8000"
)

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


def cadquery_ready() -> bool:
    return cq is not None


def cadquery_hint() -> str:
    return _CADQUERY_HINT


def require_cadquery() -> None:
    if cq is None:
        raise PuzzleError(_CADQUERY_HINT)


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


def estimate_full_size(name: str) -> tuple[float, float]:
    """Board width and depth at the full FINN letter size, from bounding boxes.

    The real layout measures pocket walls, which sit 0.40 mm outside the
    letter. This estimate is only the first guess; the build measures again.
    """
    probe = 36.0
    widths = []
    heights = []
    for ch in name:
        bb = bbox_of(make_letter(ch, probe, 2.0))
        widths.append(bb.xlen * (_FULL_FONT / probe))
        heights.append(bb.ylen * (_FULL_FONT / probe))
    gaps = max(len(name) - 1, 0)
    pitch = _FULL_GAP + 2 * FIT_CLEARANCE
    width = sum(widths) + gaps * pitch + 2 * _FULL_FRAME_X
    depth = max(heights) + 2 * _FULL_FRAME_Y
    return width, depth


def bed_span(length: float, depth: float, corner_r: float) -> float:
    """How much bed the board covers after it is turned 45 degrees.

    A 45 degree turn makes the footprint a square whose side is
    (length + depth) / sqrt(2). The rounded corners pull that square in.
    """
    corner = min(max(corner_r, 0.0), min(length, depth) / 2.0 - 0.8)
    relief = 0.0
    if corner >= 0.4:
        relief = 2.0 * corner * (math.sqrt(2.0) - 1.0)
    return (length + depth) / math.sqrt(2.0) - relief


def turn_onto_bed(shape: cq.Workplane) -> cq.Workplane:
    """Turn a board 45 degrees and sit its corner on the bed origin."""
    bb = bbox_of(shape)
    spun = shape.rotate((bb.center.x, bb.center.y, 0), (bb.center.x, bb.center.y, 1), 45)
    return to_bed(spun)


def choose_plan(name: str, progress: Progress | None) -> tuple[Plan, list[cq.Workplane], dict]:
    _log(progress, "Measuring the row")
    estimated_w, estimated_d = estimate_full_size(name)
    span = bed_span(estimated_w, estimated_d, _FULL_CORNER)
    scale = 1.0 if span <= TARGET_WIDTH else TARGET_WIDTH / span
    if scale < MIN_SCALE:
        raise PuzzleError("That name is too long to fit on one board.")

    letters: list[cq.Workplane] = []
    layout: dict = {}
    plan = Plan(scale)
    measured = span
    for attempt in range(5):
        plan = Plan(scale)
        if attempt == 0 and scale < 0.995:
            _log(progress, "Scaling the row so the turned board fits the printer")
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
        measured = bed_span(board_w, board_d, plan.corner_r)
        _log(progress, f"Board is {board_w:.1f} × {board_d:.1f} mm, {measured:.1f} mm once turned")
        fits = measured <= TARGET_WIDTH + 0.05
        if fits and (scale >= 0.999 or TARGET_WIDTH - measured <= 4.0):
            break
        if fits:
            grown = min(1.0, scale * (TARGET_WIDTH / measured))
            if grown < scale * 1.015:
                break
            scale = grown
            continue
        scale *= TARGET_WIDTH / measured
        if scale < MIN_SCALE:
            raise PuzzleError("That name is too long to fit on one board.")
    if measured > TARGET_WIDTH + 0.05:
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


# Five skins are 1.0 mm on each face. That closes the magnet lids and leaves
# the middle of the 3.5 mm floor as infill.
TOP_SHELLS = "5"
BOTTOM_SHELLS = "5"
# Keys that differ from the 0.20 mm Standard profile. Studio keeps a saved
# value only when its name is listed here.
PROCESS_SETTINGS = {
    "layer_height": "0.2",
    "initial_layer_print_height": "0.2",
    "top_shell_layers": TOP_SHELLS,
    "bottom_shell_layers": BOTTOM_SHELLS,
    "elefant_foot_compensation": "0.1",
    # Monotonic lines lay the show face in one direction. Ironing then
    # crosses that face. Topmost leaves the magnet lid alone.
    # zig-zag is Bambu's rectilinear ironing pattern.
    "top_surface_pattern": "monotonicline",
    "monotonic_travel_into_wall": "20%",
    "ironing_type": "topmost",
    "ironing_pattern": "zig-zag",
    "ironing_flow": "10%",
    "ironing_spacing": "0.1",
    "ironing_speed": "15",
    "ironing_inset": "0.2",
    "ironing_direction": "45",
    "brim_type": "no_brim",
}
PROCESS_DIFF = ";".join(PROCESS_SETTINGS)


def project_settings(colors: list[str]) -> dict:
    """Single-nozzle P2S project. One filament slot per color.

    extruder_type stays unset so Bambu Studio keeps the printer's own value
    instead of popping a substitution dialog. Nothing here replaces the
    filament start G-code. Layer height, shell count, elephant foot
    compensation, brim, and ironing are saved so the pauses land on the
    magnet pockets.
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
        "different_settings_to_system": [PROCESS_DIFF, *["filament_colour"] * count, ""],
        **PROCESS_SETTINGS,
    }


def plate_column_count(count: int) -> int:
    """How many columns Bambu Studio uses for this many plates."""
    if count <= 1:
        return 1
    value = math.sqrt(count)
    rounded = round(value)
    if value > rounded:
        return int(rounded) + 1
    return int(rounded)


def plate_origin(index: int, plate_count: int) -> tuple[float, float]:
    """World origin of a 0-based plate. Rows step toward -Y, as Studio does."""
    cols = plate_column_count(plate_count)
    col = index % cols
    row = index // cols
    return (col * PLATE_STRIDE, 0.0 if row == 0 else -row * PLATE_STRIDE)


def _fits_on_plate(
    origin: tuple[float, float, float],
    size: tuple[float, float],
    plate: int,
    plate_count: int,
) -> None:
    x0, y0, _z = origin
    width, depth = size
    ox, oy = plate_origin(plate - 1, plate_count)
    local_x = x0 - ox
    local_y = y0 - oy
    if local_x < 4 or local_y < 4 or local_x + width > BED - 4 or local_y + depth > BED - 4:
        raise PuzzleError(
            f"A part on plate {plate} is {width:.0f} × {depth:.0f} mm and does not fit the bed."
        )


def pack_letters(
    bed_letters: list[cq.Workplane],
) -> list[tuple[int, tuple[float, float, float]]]:
    """Lay letters on later plates, at most four per plate, centered.

    The gap leaves room for the toolhead, so those plates can print by object.
    """
    groups = [
        list(range(start, min(start + MAX_LETTERS_PER_PLATE, len(bed_letters))))
        for start in range(0, len(bed_letters), MAX_LETTERS_PER_PLATE)
    ]
    plate_count = 1 + len(groups)
    sizes = [bbox_of(letter) for letter in bed_letters]
    gap = OBJECT_GAP
    margin = 8.0
    max_w = BED - 2 * margin
    placements: list[tuple[int, tuple[float, float, float]] | None] = [None] * len(bed_letters)

    for group_index, group in enumerate(groups):
        plate = group_index + 2
        ox, oy = plate_origin(plate - 1, plate_count)
        rows: list[list[int]] = []
        current: list[int] = []
        current_w = 0.0
        for index in group:
            extra = sizes[index].xlen if not current else gap + sizes[index].xlen
            if current and current_w + extra > max_w:
                rows.append(current)
                current = [index]
                current_w = sizes[index].xlen
            else:
                current.append(index)
                current_w += extra
        if current:
            rows.append(current)
        if len(group) > MAX_LETTERS_PER_PLATE:
            raise PuzzleError("A plate has more than 4 letters.")

        row_heights = [max(sizes[i].ylen for i in row) for row in rows]
        row_widths = [sum(sizes[i].xlen for i in row) + gap * (len(row) - 1) for row in rows]
        total_h = sum(row_heights) + gap * (len(rows) - 1)
        if total_h > BED - 2 * margin:
            raise PuzzleError("The letters do not fit on their plate.")

        y = oy + (BED - total_h) / 2.0
        for row, row_w, row_h in zip(rows, row_widths, row_heights):
            x = ox + (BED - row_w) / 2.0
            for index in row:
                bb = sizes[index]
                pos = (x, y + (row_h - bb.ylen) / 2.0, 0.0)
                _fits_on_plate(pos, (bb.xlen, bb.ylen), plate, plate_count)
                placements[index] = (plate, pos)
                x += bb.xlen + gap
            y += row_h + gap
    return placements  # type: ignore[return-value]


def _letter_clearance(
    bed_letters: list[cq.Workplane],
    placements: list[tuple[int, tuple[float, float, float]]],
) -> float:
    """Closest distance between letter boxes that share a plate."""
    boxes = []
    for letter, (plate, pos) in zip(bed_letters, placements):
        bb = bbox_of(letter)
        boxes.append((plate, pos[0], pos[1], pos[0] + bb.xlen, pos[1] + bb.ylen))
    closest = math.inf
    for index, left in enumerate(boxes):
        for right in boxes[index + 1 :]:
            if left[0] != right[0]:
                continue
            gap_x = max(left[1] - right[3], right[1] - left[3])
            gap_y = max(left[2] - right[4], right[2] - left[4])
            if gap_x > 0 and gap_y > 0:
                distance = math.hypot(gap_x, gap_y)
            elif gap_x > 0:
                distance = gap_x
            elif gap_y > 0:
                distance = gap_y
            else:
                distance = max(gap_x, gap_y)
            closest = min(closest, distance)
    return closest


def _pause_xml(pauses: list[tuple[int, float]]) -> str:
    """Bambu Studio pause markers. type 1 is PausePrint.

    The command runs at the start of the layer whose top equals top_z, so
    top_z is the first layer that would cover the magnet.
    """
    by_plate: dict[int, list[float]] = {}
    for plate_id, top_z in pauses:
        by_plate.setdefault(plate_id, []).append(top_z)
    blocks = []
    for plate_id in sorted(by_plate):
        layers = "\n".join(
            f'<layer top_z="{top_z:.2f}" type="1" extruder="1" color="" extra="" gcode="{PAUSE_GCODE}"/>'
            for top_z in by_plate[plate_id]
        )
        blocks.append(
            "<plate>\n"
            f'<plate_info id="{plate_id}"/>\n'
            f"{layers}\n"
            '<mode value="SingleExtruder"/>\n'
            "</plate>"
        )
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<custom_gcodes_per_layer>\n"
        + "\n".join(blocks)
        + "\n</custom_gcodes_per_layer>\n"
    )


def write_3mf(
    path: Path,
    objects: list[dict],
    colors: list[str],
    title: str,
    pauses: list[tuple[int, float]] | None = None,
) -> None:
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

    plate_ids = sorted({int(obj["plate"]) for obj in objects})
    if plate_ids != list(range(1, len(plate_ids) + 1)):
        raise PuzzleError("The plates are not numbered in order.")
    letter_counts = Counter(int(obj["plate"]) for obj in objects if int(obj["plate"]) != 1)
    if not letter_counts or not any(int(obj["plate"]) == 1 for obj in objects):
        raise PuzzleError("The file needs a board plate and a letter plate.")
    if any(count > MAX_LETTERS_PER_PLATE for count in letter_counts.values()):
        raise PuzzleError("A plate has more than 4 letters.")
    letter_ids = [pid for pid in plate_ids if pid != 1]

    def plate_title(pid: int) -> str:
        if pid == 1:
            return "Board"
        if len(letter_ids) == 1:
            return "Letters"
        return f"Letters {letter_ids.index(pid) + 1}"

    object_xml = []
    build_items = []
    model_objects = []
    plate_instances: dict[int, list[str]] = {pid: [] for pid in plate_ids}
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
    def plate_xml(plate_id: int, name: str) -> str:
        # Letter plates print one object at a time. The board stays by layer.
        sequence = ""
        if plate_id != 1:
            sequence = '\n    <metadata key="print_sequence" value="by object"/>'
        return f'''  <plate>
    <metadata key="plater_id" value="{plate_id}"/>
    <metadata key="plater_name" value="{escape(name)}"/>
    <metadata key="locked" value="false"/>{sequence}
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
{chr(10).join(plate_xml(pid, plate_title(pid)) for pid in plate_ids)}
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
        if pauses:
            zf.writestr("Metadata/custom_gcode_per_layer.xml", _pause_xml(pauses))


def assert_3mf(
    path: Path,
    filament_count: int,
    pauses: list[tuple[int, float]] | None = None,
    plate_count: int = 2,
) -> None:
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        if names.index("3D/3dmodel.model") > names.index("Metadata/model_settings.config"):
            raise PuzzleError("The 3MF archive is ordered wrong.")
        loaded = json.loads(zf.read("Metadata/project_settings.config"))
        model_xml = zf.read("3D/3dmodel.model").decode("utf-8")
        settings_xml = zf.read("Metadata/model_settings.config").decode("utf-8")
        pause_name = "Metadata/custom_gcode_per_layer.xml"
        pause_xml = zf.read(pause_name).decode("utf-8") if pause_name in names else ""
    if loaded.get("printer_model") != "Bambu Lab P2S" or loaded.get("printer_variant") != "0.4":
        raise PuzzleError("The 3MF is not a P2S project.")
    if loaded.get("nozzle_diameter") != ["0.4"]:
        raise PuzzleError("The 3MF nozzle is not 0.4 mm.")
    if "extruder_type" in loaded or "filament_start_gcode" in loaded:
        raise PuzzleError("The 3MF changes printer settings it should leave alone.")
    if len(loaded["inherits_group"]) != filament_count + 2:
        raise PuzzleError("The filament list is the wrong length.")
    diffs = loaded["different_settings_to_system"]
    if len(diffs) != filament_count + 2 or diffs[0] != PROCESS_DIFF or diffs[-1] != "":
        raise PuzzleError("The filament overrides are the wrong length.")
    if any(item != "filament_colour" for item in diffs[1:-1]):
        raise PuzzleError("The 3MF overrides more than the filament color.")
    for key, value in PROCESS_SETTINGS.items():
        if loaded.get(key) != value:
            raise PuzzleError(f"The 3MF is missing the saved {key} setting.")
    if len(loaded["filament_colour"]) != filament_count:
        raise PuzzleError("The 3MF is missing a filament color.")
    if "BambuStudio-01.10.02.75" not in model_xml:
        raise PuzzleError("The 3MF is not marked as a Bambu Studio project.")
    if settings_xml.count("<plate>") != plate_count:
        raise PuzzleError("The 3MF has the wrong number of plates.")
    for plate in settings_xml.split("<plate>")[1:]:
        head = plate.split("</plate>", 1)[0]
        by_object = 'key="print_sequence" value="by object"' in head
        if 'key="plater_id" value="1"' in head:
            if by_object:
                raise PuzzleError("The board plate is set to print by object.")
        elif not by_object:
            raise PuzzleError("A letter plate is not set to print by object.")
    if not pauses:
        if pause_xml:
            raise PuzzleError("The 3MF pauses a print that has no magnets.")
        return
    if not pause_xml:
        raise PuzzleError("The 3MF is missing the magnet pause.")
    if pause_xml.count("<plate>") != len({plate for plate, _z in pauses}):
        raise PuzzleError("The magnet pause is missing a plate.")
    if pause_xml.count('type="1"') != len(pauses):
        raise PuzzleError("The magnet pause is not a pause command.")
    if pause_xml.count(PAUSE_GCODE) != len(pauses):
        raise PuzzleError("The magnet pause command is missing.")
    for plate_id, top_z in pauses:
        if f'<plate_info id="{plate_id}"/>' not in pause_xml:
            raise PuzzleError("The magnet pause is on the wrong plate.")
        if f'top_z="{top_z:.2f}"' not in pause_xml:
            raise PuzzleError("The magnet pause is at the wrong height.")


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


def _inside_face(face, x: float, y: float, z: float) -> bool:
    from OCP.BRepClass import BRepClass_FaceClassifier
    from OCP.TopAbs import TopAbs_IN
    from OCP.gp import gp_Pnt

    state = BRepClass_FaceClassifier(face.wrapped, gp_Pnt(x, y, z), 0.02).State()
    return state == TopAbs_IN


def _holds_disc(face, x: float, y: float, z: float, radius: float) -> bool:
    if not _inside_face(face, x, y, z):
        return False
    steps = 12
    for step in range(steps):
        angle = 2.0 * math.pi * step / steps
        if not _inside_face(face, x + radius * math.cos(angle), y + radius * math.sin(angle), z):
            return False
    return True


def _candidate_points(face, radius: float, step: float) -> list[tuple[float, float]]:
    bb = face.BoundingBox()
    z = float(face.Center().z)
    points: list[tuple[float, float]] = []
    y = bb.ymin + radius
    limit_y = bb.ymax - radius
    limit_x = bb.xmax - radius
    while y <= limit_y + 1e-6:
        x = bb.xmin + radius
        while x <= limit_x + 1e-6:
            if _holds_disc(face, x, y, z, radius):
                points.append((x, y))
            x += step
        y += step
    return points


def _pick_spots(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Two centers, spread apart, with plastic between the pockets."""
    if len(points) < 2:
        return list(points)
    min_gap = POCKET_D + 1.2
    best_pair = None
    best_d = -1.0
    for index, first in enumerate(points):
        for second in points[index + 1 :]:
            distance = math.hypot(first[0] - second[0], first[1] - second[1])
            if distance > best_d:
                best_pair = (first, second)
                best_d = distance
    if best_pair is None or best_d < min_gap:
        return [points[0]]
    return [best_pair[0], best_pair[1]]


def magnet_spots(letter: cq.Workplane) -> list[tuple[float, float]]:
    """Centers for 5 mm pockets that stay inside the letter."""
    faces = letter.faces(">Z").vals()
    if not faces:
        return []
    face = max(faces, key=lambda item: item.Area())
    for wall, step in ((1.4, 3.0), (1.4, 1.6), (1.0, 1.6), (0.7, 1.5)):
        chosen = _pick_spots(_candidate_points(face, POCKET_R + wall, step))
        if len(chosen) >= 2:
            return chosen
    return []


def _pocket_cutter(x: float, y: float, z0: float, z1: float) -> cq.Workplane:
    return (
        cq.Workplane("XY")
        .center(x, y)
        .circle(POCKET_R)
        .extrude(z1 - z0)
        .translate((0, 0, z0))
    )


def cut_pockets(
    shape: cq.Workplane,
    spots: list[tuple[float, float]],
    z0: float,
    z1: float,
    label: str,
) -> tuple[cq.Workplane, list[tuple[float, float]]]:
    """Cut enclosed pockets. A spot that breaks the solid, or opens the skin, is skipped."""
    kept: list[tuple[float, float]] = []
    volume = solid_volume(shape)
    pocket_volume = math.pi * POCKET_R * POCKET_R * (z1 - z0)
    for x, y in spots:
        try:
            trial = shape.cut(_pocket_cutter(x, y, z0, z1))
            assert_single_piece(trial, label)
            new_volume = solid_volume(trial)
        except Exception as exc:
            print(f"  pocket in {label} at {x:.1f}, {y:.1f} skipped ({exc})", flush=True)
            continue
        removed = volume - new_volume
        if abs(removed - pocket_volume) > 0.08 * pocket_volume:
            print(
                f"  pocket in {label} at {x:.1f}, {y:.1f} skipped "
                f"(removed {removed:.1f} mm³, expected {pocket_volume:.1f})",
                flush=True,
            )
            continue
        shape = trial
        volume = new_volume
        kept.append((x, y))
    return shape, kept


def add_magnets(
    name: str,
    letters: list[cq.Workplane],
    layout: dict,
    board: cq.Workplane,
    progress: Progress | None,
) -> tuple[list[cq.Workplane], cq.Workplane, list[int]]:
    """Pocket every letter and the matching spots in the board floor."""
    _log(progress, "Placing magnet pockets")
    new_letters: list[cq.Workplane] = []
    counts: list[int] = []
    board_spots: list[tuple[float, float]] = []
    for ch, letter, well in zip(name, letters, layout["wells"]):
        spots = magnet_spots(letter)
        cut_letter, kept = cut_pockets(letter, spots, LETTER_SKIN, LETTER_CAVITY_TOP, ch)
        dx, dy, _dz = shift_for(letter, well, 0)
        board_spots.extend((x + dx, y + dy) for x, y in kept)
        new_letters.append(cut_letter)
        counts.append(len(kept))
        _log(progress, f"{ch} gets {len(kept)} magnets")
    if sum(counts) == 0:
        raise PuzzleError("None of those letters has room for a 5 mm magnet.")
    _log(progress, "Cutting the magnet pockets into the board")
    cut_board, kept_board = cut_pockets(
        board, board_spots, BOARD_CAVITY_BOTTOM, BOARD_CAVITY_TOP, "The board"
    )
    if len(kept_board) != len(board_spots):
        raise PuzzleError("A magnet pocket did not fit in the board.")
    return new_letters, cut_board, counts


def generate(
    raw_name: str,
    out_dir: Path,
    progress: Progress | None = None,
    magnets: bool = False,
) -> dict:
    """Build the puzzle, write puzzle.3mf and model.json, and return the summary."""
    started = time.perf_counter()
    require_cadquery()
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

    _log(progress, "Checking the fit")
    clearances = _check_fit(name, letters, layout, board, progress)
    magnet_counts = [0] * len(name)
    if magnets:
        letters, board, magnet_counts = add_magnets(name, letters, layout, board, progress)
        board_bb = bbox_of(board)

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
        count = magnet_counts[index]
        if magnets and count == 0:
            warnings.append(f"{ch} has no room for two 5×2 mm magnets.")
        elif magnets and count == 1:
            warnings.append(f"{ch} has room for only one 5×2 mm magnet.")
        if count > 2:
            raise PuzzleError(f"{ch} has more than two magnets.")
        letter_meta.append(
            {
                "char": ch,
                "color": PALETTE[index % len(PALETTE)],
                "width": round(bb.xlen, 1),
                "depth": round(bb.ylen, 1),
                "magnets": count,
            }
        )

    _log(progress, "Writing the print file")
    stl_dir = out_dir / "stl"
    board_path = stl_dir / "board.stl"
    bed_board = turn_onto_bed(board)
    spun = bbox_of(bed_board)
    if spun.xlen > BED - 6 or spun.ylen > BED - 6:
        raise PuzzleError("The turned board does not fit the printer.")
    export_stl(bed_board, board_path, 0.08, 0.1)
    bed_letters = []
    letter_paths = []
    for ch, letter in zip(name, letters):
        path = stl_dir / f"letter_{ch}_{len(letter_paths) + 1}.stl"
        bed = to_bed(letter)
        export_stl(bed, path, 0.045, 0.06)
        bed_letters.append(bed)
        letter_paths.append(path)

    plate_count = 1 + math.ceil(len(bed_letters) / MAX_LETTERS_PER_PLATE)
    board_pos = ((BED - spun.xlen) / 2.0, (BED - spun.ylen) / 2.0, 0.0)
    _fits_on_plate(board_pos, (spun.xlen, spun.ylen), 1, plate_count)
    letter_pos = pack_letters(bed_letters)
    if len(bed_letters) > 1 and _letter_clearance(bed_letters, letter_pos) <= 57.0:
        raise PuzzleError("Letters on one plate are too close to print by object.")

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
            "plate": letter_pos[index][0],
            "mesh": stl_mesh(path),
            "pos": letter_pos[index][1],
        }
    )
    three_mf = out_dir / "puzzle.3mf"
    letter_plates = sorted({item[0] for item in letter_pos})
    pauses = [(1, BOARD_PAUSE_Z), *[(plate, LETTER_PAUSE_Z) for plate in letter_plates]] if magnets else None
    write_3mf(three_mf, objects, colors, f"{name} name puzzle", pauses)
    assert_3mf(three_mf, len(colors), pauses, plate_count)

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
        "diagonal": True,
        "print_span": round(max(spun.xlen, spun.ylen), 1),
        "shiny_top": False,
        "letter_plates": len(letter_plates),
        "letters_per_plate": MAX_LETTERS_PER_PLATE,
        "font_size": round(plan.font_size, 2),
        "clearances": [round(gap, 3) for gap in clearances],
        "warnings": warnings,
        "board_color": BOARD_COLOR,
        "letters": letter_meta,
        "magnets": magnets,
    }
    if magnets:
        summary["pause_board_mm"] = round(BOARD_PAUSE_Z, 2)
        summary["pause_letters_mm"] = round(LETTER_PAUSE_Z, 2)
        summary["magnet_size"] = f"{MAGNET_D:.0f}×{MAGNET_T:.0f} mm"
    preview = dict(summary)
    preview["board"] = board_mesh
    preview["letters"] = letter_views
    (out_dir / "model.json").write_text(json.dumps(preview, separators=(",", ":")), encoding="utf-8")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    _log(progress, f"Ready ({time.perf_counter() - started:.0f}s)")
    return summary


def main(argv: list[str]) -> None:
    magnets = "--magnets" in argv[1:]
    args = [item for item in argv[1:] if item != "--magnets"]
    raw = args[0] if args else "ROB"
    out = Path(args[1]) if len(args) > 1 else Path("/tmp/name-puzzles") / sanitize_name(raw)
    summary = generate(raw, out, magnets=magnets)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    try:
        main(sys.argv)
    except PuzzleError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
