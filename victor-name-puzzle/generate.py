#!/usr/bin/env python3
"""Generate a wooden-style VICTOR name puzzle sized for a Bambu Lab P2S.

The row is one solid board, scaled so it fits the 256 mm P2S bed with a
few millimetres to spare. The wood between every pair of letters is the
same. Letter thickness stays 11 mm, and each slot stays 0.40 mm larger
than its letter.

Each slot is that letter's outline. O and R keep their counters, so the
board has a matching island. The slot is 0.40 mm larger than the letter.

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

import cadquery as cq

ROOT = Path(__file__).resolve().parent
FONT = ROOT / "fonts" / "LilitaOne-Regular.ttf"
STL_DIR = ROOT / "stl"
PREVIEW_DIR = ROOT / "preview"
NAME = "VICTOR"

# Millimetres. The P2S build volume is 256 x 256 x 256.
# The in-plane sizes below are the printed FINN letter size. apply_plan_scale
# shrinks them until the solid board fits the bed with 4 mm to spare on
# each side. Thickness and the slot clearance stay put.
BED = 256.0
# 4 mm of bed is kept clear on each side, plus a little so rounding
# cannot push the board onto the edge.
TARGET_WIDTH = BED - 8.5
PLAN_SCALE = 1.0
_FULL_FONT = 90.874509
_FULL_FRAME_X = 13.0
_FULL_FRAME_Y = 14.0
_FULL_GAP = 10.0
_FULL_CORNER = 11.0
FONT_SIZE = _FULL_FONT
FIT_CLEARANCE = 0.40
FRAME_X = _FULL_FRAME_X
FRAME_Y = _FULL_FRAME_Y
FLOOR = 3.5
WELL_DEPTH = 7.0
LETTER_THICK = 11.0
BOARD_CORNER_R = _FULL_CORNER
OUTER_EDGE_R = 1.6
TOP_SOFTEN = 0.85
BOTTOM_LEAD = 0.30
# Bambu Studio lays plates on a grid of bed * (1 + 1/5). Plate 2 starts here.
PLATE_STRIDE = BED * 1.2

# Wood between neighboring slots. Every pair uses this.
LETTER_GAP = _FULL_GAP


def apply_plan_scale(scale: float) -> None:
    """Shrink the row. Thickness and slot clearance stay fixed."""
    global PLAN_SCALE, FONT_SIZE, FRAME_X, FRAME_Y, LETTER_GAP, BOARD_CORNER_R
    if not 0.45 <= scale <= 1.0:
        raise SystemExit(f"plan scale {scale:.3f} is outside a sensible range")
    PLAN_SCALE = scale
    FONT_SIZE = _FULL_FONT * scale
    FRAME_X = _FULL_FRAME_X * scale
    FRAME_Y = _FULL_FRAME_Y * scale
    LETTER_GAP = _FULL_GAP * scale
    BOARD_CORNER_R = _FULL_CORNER * scale


COLORS = {
    "board": (0.91, 0.78, 0.58),
    "V": (0.86, 0.22, 0.18),
    "I": (0.18, 0.42, 0.86),
    "C": (0.22, 0.62, 0.30),
    "T": (0.95, 0.78, 0.12),
    "O": (0.88, 0.48, 0.18),
    "R": (0.48, 0.30, 0.72),
}

HEX = {
    "board": "#E8C794",
    "V": "#DB382E",
    "I": "#2E6BDB",
    "C": "#389E4D",
    "T": "#F2C71F",
    "O": "#E07A2F",
    "R": "#7A4DB8",
}


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


def _accept(candidate: cq.Workplane, fallback: cq.Workplane) -> cq.Workplane:
    try:
        solid = candidate.val()
        if solid.isValid() and len(candidate.solids().vals()) == 1 and solid.Volume() > 1000:
            return candidate
    except Exception:
        pass
    return fallback


def soften_letter(letter: cq.Workplane) -> cq.Workplane:
    """Break the sharp top edge when the font outline allows it."""
    original = letter
    try:
        letter = _accept(letter.faces(">Z").edges().fillet(TOP_SOFTEN), original)
    except Exception as exc:
        print(f"  top fillet skipped ({exc})")
        letter = original
    if letter is original:
        try:
            letter = _accept(original.faces(">Z").edges().chamfer(0.45), original)
        except Exception as exc:
            print(f"  top chamfer skipped ({exc})")
            letter = original
    try:
        softened = letter.faces("<Z").edges().chamfer(BOTTOM_LEAD)
        letter = _accept(softened, letter)
    except Exception as exc:
        print(f"  bottom lead-in skipped ({exc})")
    return letter


def letter_pocket(letter: cq.Workplane, clearance: float) -> cq.Workplane:
    """A prism of the letter outline, grown by clearance on every side.

    Counters become islands: the hole in the cutter is 0.40 mm smaller than
    the letter's hole, so the island that remains in the board is a loose fit.
    """
    bb = bbox_of(letter)
    slab = (
        cq.Workplane("XY")
        .box(bb.xlen + 30, bb.ylen + 30, 0.2, centered=(True, True, True))
        .translate((bb.center.x, bb.center.y, bb.zmin + 1.0))
    )
    section = letter.intersect(slab)
    faces = section.faces(">Z").vals()
    if len(faces) != 1:
        raise SystemExit(f"letter section has {len(faces)} faces")
    face = faces[0]
    outer = face.outerWire()
    outer = outer.translate((0, 0, -outer.Center().z))
    grown = outer.offset2D(clearance, "arc")
    if len(grown) != 1:
        raise SystemExit(f"letter offset produced {len(grown)} outlines")
    pocket = cq.Workplane("XY").add(grown[0]).toPending().extrude(WELL_DEPTH + 3.0)

    for inner in face.innerWires():
        inner = inner.translate((0, 0, -inner.Center().z))
        shrunk = inner.offset2D(-clearance, "arc")
        if len(shrunk) != 1:
            raise SystemExit(f"counter offset produced {len(shrunk)} outlines")
        hole_bb = inner.BoundingBox()
        island_bb = shrunk[0].BoundingBox()
        if island_bb.xlen > hole_bb.xlen - 0.5 or island_bb.ylen > hole_bb.ylen - 0.5:
            raise SystemExit("counter island is not smaller than the letter hole")
        island = cq.Workplane("XY").add(shrunk[0]).toPending().extrude(WELL_DEPTH + 3.0)
        pocket = pocket.cut(island)

    if not pocket.val().isValid() or len(pocket.solids().vals()) != 1:
        raise SystemExit("letter pocket is not a single valid solid")
    return pocket


def _try_top_fillet(shape: cq.Workplane, label: str) -> cq.Workplane:
    try:
        filleted = shape.faces(">Z").edges().fillet(OUTER_EDGE_R)
        solid = filleted.val()
        if solid.isValid() and len(filleted.solids().vals()) == 1:
            return filleted
    except Exception as exc:
        print(f"  {label} outer edge skipped ({exc})")
    return shape


def build_board(
    layout: dict, raw_letters: list[cq.Workplane]
) -> tuple[cq.Workplane, list[cq.Workplane]]:
    """One solid board. The slots are cut out of it."""
    board_h = FLOOR + WELL_DEPTH
    board_w = layout["board_w"]
    board_d = layout["board_d"]
    board = (
        cq.Workplane("XY")
        .center(board_w / 2.0, board_d / 2.0)
        .rect(board_w, board_d)
        .extrude(board_h)
        .edges("|Z")
        .fillet(BOARD_CORNER_R)
    )
    board = _try_top_fillet(board, "board")

    pockets = []
    for well, letter in zip(layout["wells"], raw_letters):
        pocket = letter_pocket(letter, FIT_CLEARANCE)
        dx, dy, _ = shift_for(letter, well, 0.0)
        pocket = pocket.translate((dx, dy, FLOOR))
        pockets.append(pocket)
        board = board.cut(pocket)
    return board, pockets


def _place_pocket(pocket: cq.Workplane, bb: cq.BoundBox, x0: float, y0: float, letter_h: float) -> cq.Workplane:
    dy = (y0 + letter_h / 2.0) - bb.ylen / 2.0 - bb.ymin
    return pocket.translate((x0 - bb.xmin, dy, 0))


def _gap_at(prev: cq.Workplane, pocket: cq.Workplane, bb: cq.BoundBox, x0: float, y0: float, letter_h: float) -> float:
    return min_distance(prev.val(), _place_pocket(pocket, bb, x0, y0, letter_h).val())


def _x_for_gap(prev: cq.Workplane, pocket: cq.Workplane, bb: cq.BoundBox, y0: float, letter_h: float) -> float:
    """Left edge of the next letter, so the wood between slots is LETTER_GAP.

    Moving a letter along the row changes the gap by the same amount, so two
    corrections land on the target.
    """
    x = bbox_of(prev).xmax + 1.0
    for _ in range(4):
        gap = _gap_at(prev, pocket, bb, x, y0, letter_h)
        error = LETTER_GAP - gap
        if abs(error) < 0.02:
            break
        x += error
    return x


def layout_for(raw_letters: list[cq.Workplane]) -> dict:
    boxes = [bbox_of(letter) for letter in raw_letters]
    letter_h = max(bb.ylen for bb in boxes)
    y0 = FRAME_Y
    pockets = [letter_pocket(letter, FIT_CLEARANCE) for letter in raw_letters]
    wells = []
    placed = []
    x = FRAME_X
    for index, (bb, pocket) in enumerate(zip(boxes, pockets)):
        if index:
            x = _x_for_gap(placed[-1], pocket, bb, y0, letter_h)
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
            print(f"  gap before {NAME[index]}: {wood:.2f} mm")
    board_w = wells[-1]["x0"] + wells[-1]["w"] + FRAME_X
    board_d = FRAME_Y + letter_h + FRAME_Y
    return {
        "wells": wells,
        "board_w": board_w,
        "board_d": board_d,
        "letter_h": letter_h,
        "gap": FIT_CLEARANCE,
    }


def shift_for(letter: cq.Workplane, well: dict, z: float) -> tuple[float, float, float]:
    """Move a letter so it is centered on its slot and sitting on z."""
    bb = bbox_of(letter)
    return (
        well["cx"] - bb.xlen / 2.0 - bb.xmin,
        well["cy"] - bb.ylen / 2.0 - bb.ymin,
        z - bb.zmin,
    )


def place_letter(letter: cq.Workplane, well: dict, z: float) -> cq.Workplane:
    return letter.translate(shift_for(letter, well, z))


def min_distance(a: cq.Shape, b: cq.Shape) -> float:
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape

    calc = BRepExtrema_DistShapeShape(a.wrapped, b.wrapped)
    if not calc.Perform():
        raise RuntimeError("distance calculation failed")
    return float(calc.Value())


def side_clearance(letter: cq.Workplane, board: cq.Workplane, board_w: float, board_d: float) -> float:
    """Gap between the letter and the well wall, taken at mid-depth."""
    z_mid = FLOOR + WELL_DEPTH / 2.0
    slice_h = 0.4
    clip = (
        cq.Workplane("XY")
        .box(board_w + 20, board_d + 20, slice_h, centered=(True, True, True))
        .translate((board_w / 2.0, board_d / 2.0, z_mid))
    )
    clipped = letter.intersect(clip)
    return min_distance(clipped.val(), board.val())


def solid_volume(shape: cq.Workplane) -> float:
    solids = shape.solids().vals()
    if not solids:
        return 0.0
    return float(sum(solid.Volume() for solid in solids))


def assert_single_piece(shape: cq.Workplane, label: str) -> None:
    solids = shape.solids().vals()
    if len(solids) != 1:
        raise SystemExit(f"{label} is {len(solids)} solids, expected 1")
    if not shape.val().isValid():
        raise SystemExit(f"{label} is not a valid solid")


def to_bed(shape: cq.Workplane) -> cq.Workplane:
    bb = bbox_of(shape)
    return shape.translate((-bb.xmin, -bb.ymin, -bb.zmin))


def stl_mesh(path: Path) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]:
    """Load a binary STL and weld vertices so the 3MF has no open edges."""
    data = path.read_bytes()
    count = struct.unpack_from("<I", data, 80)[0]
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


def project_settings() -> dict:
    """Single-nozzle P2S project. One filament slot per color, one nozzle.

    extruder_type is left unset so Bambu Studio keeps the printer's own value
    instead of popping a substitution dialog.
    """
    order = ["board", "V", "I", "C", "T", "O", "R"]
    filaments = ["Bambu PLA Basic @BBL P2S"] * len(order)
    return {
        "name": "project_settings",
        "printer_model": "Bambu Lab P2S",
        "printer_variant": "0.4",
        "nozzle_diameter": ["0.4"],
        "printer_settings_id": "Bambu Lab P2S 0.4 nozzle",
        "print_settings_id": "0.20mm Standard @BBL P2S",
        "filament_settings_id": filaments,
        "filament_colour": [HEX[name] for name in order],
        "filament_type": ["PLA"] * len(order),
        "filament_diameter": ["1.75"] * len(order),
        "filament_self_index": [str(i) for i in range(1, len(order) + 1)],
        "filament_extruder_variant": ["Direct Drive Standard"] * len(order),
        "extruder_variant_list": [
            "Direct Drive Standard,Direct Drive High Flow,Direct Drive E3D High Flow"
        ],
        "inherits_group": [
            "0.20mm Standard @BBL P2S",
            *filaments,
            "Bambu Lab P2S 0.4 nozzle",
        ],
        "different_settings_to_system": [
            "",
            *["filament_colour"] * len(order),
            "",
        ],
    }


def write_3mf(path: Path, objects: list[dict]) -> None:
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
            raise SystemExit(f"{obj['name']} mesh is not closed")
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

    settings = project_settings()
    filament_count = len(settings["filament_colour"])
    if settings["printer_model"] != "Bambu Lab P2S" or settings["nozzle_diameter"] != ["0.4"]:
        raise SystemExit("project settings are not a single-nozzle P2S")
    if "extruder_type" in settings:
        raise SystemExit("extruder_type must stay unset")
    if len(settings["inherits_group"]) != filament_count + 2:
        raise SystemExit("filament preset lists do not match the colors")
    if len(settings["different_settings_to_system"]) != filament_count + 2:
        raise SystemExit("filament diff lists do not match the colors")
    if not plate_instances[1] or not plate_instances[2]:
        raise SystemExit("both plates need at least one object")

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
  <metadata name="Title">VICTOR name puzzle</metadata>
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
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("3D/3dmodel.model", model)
        zf.writestr("Metadata/project_settings.config", json.dumps(settings, indent=2))
        zf.writestr("Metadata/model_settings.config", model_settings)


def _polydata(shape: cq.Workplane, tolerance: float = 0.15):
    import vtk

    verts, tris = shape.val().tessellate(tolerance, 0.15)
    points = vtk.vtkPoints()
    for v in verts:
        points.InsertNextPoint(float(v.x), float(v.y), float(v.z))
    cells = vtk.vtkCellArray()
    for a, b, c in tris:
        cells.InsertNextCell(3)
        cells.InsertCellPoint(int(a))
        cells.InsertCellPoint(int(b))
        cells.InsertCellPoint(int(c))
    poly = vtk.vtkPolyData()
    poly.SetPoints(points)
    poly.SetPolys(cells)
    normals = vtk.vtkPolyDataNormals()
    normals.SetInputData(poly)
    normals.ConsistencyOn()
    normals.AutoOrientNormalsOn()
    normals.SplittingOff()
    normals.Update()
    return normals.GetOutput()


def _actor(shape: cq.Workplane, rgb: tuple[float, float, float], specular: float):
    import vtk

    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputData(_polydata(shape))
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    prop = actor.GetProperty()
    prop.SetColor(*rgb)
    prop.SetSpecular(specular)
    prop.SetSpecularPower(18)
    prop.SetDiffuse(0.78)
    prop.SetAmbient(0.22)
    prop.SetInterpolationToPhong()
    return actor


def render(
    board: cq.Workplane,
    placed: list[cq.Workplane],
    lifted_index: int,
    path: Path,
    kind: str,
) -> None:
    import vtk

    ren = vtk.vtkRenderer()
    ren.SetBackground(0.93, 0.91, 0.86)
    ren.AddActor(_actor(board, COLORS["board"], 0.12))
    for i, letter in enumerate(placed):
        if kind == "holes":
            continue
        shape = letter
        if i == lifted_index and kind == "top":
            continue
        if i == lifted_index and kind == "angle":
            shape = shape.translate((0, 28, 22))
        ren.AddActor(_actor(shape, COLORS[NAME[i]], 0.28))

    win = vtk.vtkRenderWindow()
    win.SetOffScreenRendering(1)
    win.SetMultiSamples(8)
    win.AddRenderer(ren)
    height = 780 if kind == "top" else 900
    win.SetSize(2000, height)

    ren.ResetCamera()
    cam = ren.GetActiveCamera()
    bb = bbox_of(board)
    fx = bb.center.x
    fy = bb.center.y
    span_x = bb.xlen
    span_y = bb.ylen
    if kind == "top":
        cam.SetParallelProjection(True)
        cam.SetFocalPoint(fx, fy, 0)
        cam.SetPosition(fx, fy, 500)
        cam.SetViewUp(0, 1, 0)
        aspect = 2000 / height
        half_height = max(span_y * 0.62, (span_x * 0.55) / aspect)
        cam.SetParallelScale(half_height)
    else:
        cam.SetViewUp(0, 0, 1)
        cam.SetFocalPoint(fx, fy, 6)
        cam.SetPosition(fx, fy - 900, 6)
        ren.ResetCamera()
        cam.Azimuth(16 if kind == "angle" else 12)
        cam.Elevation(36 if kind == "angle" else 55)
        cam.Zoom(1.15 if kind == "angle" else 1.22)
        cam.OrthogonalizeViewUp()
    ren.ResetCameraClippingRange()

    key = vtk.vtkLight()
    key.SetLightTypeToSceneLight()
    key.SetPosition(fx + 80, fy - 160, 260)
    key.SetFocalPoint(fx, fy, 0)
    key.SetIntensity(0.9)
    fill = vtk.vtkLight()
    fill.SetLightTypeToSceneLight()
    fill.SetPosition(fx - 180, fy - 40, 120)
    fill.SetFocalPoint(fx, fy, 0)
    fill.SetIntensity(0.45)
    ren.AddLight(key)
    ren.AddLight(fill)

    win.Render()
    window_to_image = vtk.vtkWindowToImageFilter()
    window_to_image.SetInput(win)
    window_to_image.SetScale(1)
    window_to_image.SetInputBufferTypeToRGB()
    window_to_image.Update()
    writer = vtk.vtkPNGWriter()
    path.parent.mkdir(parents=True, exist_ok=True)
    writer.SetFileName(str(path))
    writer.SetInputConnection(window_to_image.GetOutputPort())
    writer.Write()
    _crop_to_subject(path)


def _crop_to_subject(path: Path, pad: int = 36) -> None:
    """Trim the flat backdrop so the puzzle fills the picture."""
    from PIL import Image

    image = Image.open(path).convert("RGB")
    background = image.getpixel((1, 1))
    width, height = image.size
    pixels = image.load()
    min_x, min_y, max_x, max_y = width, height, 0, 0
    for y in range(0, height, 2):
        for x in range(0, width, 2):
            red, green, blue = pixels[x, y]
            if (
                abs(red - background[0])
                + abs(green - background[1])
                + abs(blue - background[2])
                > 16
            ):
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
    if max_x <= min_x or max_y <= min_y:
        return
    box = (
        max(0, min_x - pad),
        max(0, min_y - pad),
        min(width, max_x + pad),
        min(height, max_y + pad),
    )
    image.crop(box).save(path)


def mesh_is_closed(path: Path) -> tuple[int, int]:
    import vtk

    reader = vtk.vtkSTLReader()
    reader.SetFileName(str(path))
    reader.Update()
    edges = vtk.vtkFeatureEdges()
    edges.SetInputConnection(reader.GetOutputPort())
    edges.BoundaryEdgesOn()
    edges.FeatureEdgesOff()
    edges.NonManifoldEdgesOn()
    edges.ManifoldEdgesOff()
    edges.Update()
    polys = reader.GetOutput().GetNumberOfPolys()
    boundary = edges.GetOutput().GetNumberOfCells()
    return int(polys), int(boundary)


def export_stl(shape: cq.Workplane, path: Path, tolerance: float, angular: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cq.exporters.export(shape, str(path), tolerance=tolerance, angularTolerance=angular)


def _fits_on_plate(origin: tuple[float, float, float], size: tuple[float, float], plate: int) -> None:
    x0, y0, _z = origin
    w, h = size
    stride = 0.0 if plate == 1 else PLATE_STRIDE
    local_x = x0 - stride
    if local_x < 4 or y0 < 4 or local_x + w > BED - 4 or y0 + h > BED - 4:
        raise SystemExit(
            f"object on plate {plate} uses {local_x:.1f},{y0:.1f} size {w:.1f}x{h:.1f}, outside the bed"
        )


def main() -> None:
    if not FONT.exists():
        raise SystemExit(f"Missing font: {FONT}")

    print(f"Fitting VICTOR onto one {TARGET_WIDTH:.0f} mm board...")
    # The full-size row is 360.8 mm. One correction is enough because width
    # tracks the plan scale almost exactly.
    scale = TARGET_WIDTH / 360.83
    raw = None
    layout = None
    for _ in range(3):
        apply_plan_scale(scale)
        raw = [make_letter(ch, FONT_SIZE, LETTER_THICK) for ch in NAME]
        for ch, letter in zip(NAME, raw):
            assert_single_piece(letter, f"raw {ch}")
        layout = layout_for(raw)
        print(f"  scale {scale:.4f} -> board {layout['board_w']:.2f} mm")
        if layout["board_w"] > TARGET_WIDTH:
            scale *= TARGET_WIDTH / layout["board_w"]
            continue
        if TARGET_WIDTH - layout["board_w"] < 0.4:
            break
        scale *= TARGET_WIDTH / layout["board_w"]
    if layout["board_w"] > TARGET_WIDTH + 0.05:
        raise SystemExit(f"board is {layout['board_w']:.2f} mm, wanted at most {TARGET_WIDTH:.0f}")
    print(f"  letters at font {FONT_SIZE:.2f}, wood between letters {LETTER_GAP:.2f} mm")
    for ch, letter in zip(NAME, raw):
        bb = bbox_of(letter)
        print(f"  {ch} {bb.xlen:.1f} x {bb.ylen:.1f} x {bb.zlen:.1f}")
    print(f"  board {layout['board_w']:.1f} x {layout['board_d']:.1f} mm")
    if layout["board_w"] > BED - 8 or layout["board_d"] > BED - 8:
        raise SystemExit("Board does not fit the P2S bed with margin")
    print("  cutting letter slots...")
    board, pockets = build_board(layout, raw)
    assert_single_piece(board, "board")

    board_bb = bbox_of(board)
    print(f"  board piece {board_bb.xlen:.1f} x {board_bb.ylen:.1f} x {board_bb.zlen:.1f}")
    board_h = FLOOR + WELL_DEPTH
    if abs(board_bb.zlen - board_h) > 0.05:
        raise SystemExit("the board is not the expected thickness")
    if board_bb.xlen > BED - 8 or board_bb.ylen > BED - 8:
        raise SystemExit("the board does not fit the P2S bed with margin")

    woods = []
    for index in range(len(pockets) - 1):
        wood = min_distance(pockets[index].val(), pockets[index + 1].val())
        woods.append(wood)
        print(f"  wood between slot {index + 1} and {index + 2}: {wood:.2f} mm")
    if max(woods) - min(woods) > 0.25 or abs(sum(woods) / len(woods) - LETTER_GAP) > 0.25:
        raise SystemExit(f"letter gaps are not equal: {woods}")

    placed_raw = [place_letter(letter, well, FLOOR) for letter, well in zip(raw, layout["wells"])]
    clearances = []
    for ch, letter in zip(NAME, placed_raw):
        hit = solid_volume(board.intersect(letter))
        if hit > 0.05:
            raise SystemExit(f"{ch} intersects its own slot by {hit:.3f} mm^3")
        gap_mm = side_clearance(letter, board, layout["board_w"], layout["board_d"])
        clearances.append(gap_mm)
        print(f"  {ch} fits its slot with {gap_mm:.2f} mm of room")
        if not 0.25 <= gap_mm <= 0.60:
            raise SystemExit(f"{ch} slot is not a close fit ({gap_mm:.2f} mm)")

    for piece_i, piece_ch in enumerate(NAME):
        for slot_i, slot_ch in enumerate(NAME):
            if piece_i == slot_i:
                continue
            moved = place_letter(raw[piece_i], layout["wells"][slot_i], FLOOR)
            clash = solid_volume(board.intersect(moved))
            print(f"  {piece_ch} in the {slot_ch} slot clashes by {clash:.0f} mm^3")
            if clash < 200.0 * PLAN_SCALE * PLAN_SCALE:
                raise SystemExit(f"{piece_ch} fits the {slot_ch} slot")

    print("Softening letter edges...")
    letters = []
    for ch, letter in zip(NAME, raw):
        print(f"  {ch}")
        letters.append(soften_letter(letter))
        assert_single_piece(letters[-1], ch)

    placed = [place_letter(letter, well, FLOOR) for letter, well in zip(letters, layout["wells"])]
    for ch, letter in zip(NAME, placed):
        hit = solid_volume(board.intersect(letter))
        if hit > 0.05:
            raise SystemExit(f"Softened {ch} hits the board ({hit:.3f} mm^3)")
        bb = bbox_of(letter)
        if bb.zmin < FLOOR - 0.05:
            raise SystemExit(f"{ch} drops through the well floor")
        proud = bb.zmax - (FLOOR + WELL_DEPTH)
        print(f"  {ch} sits {proud:.2f} mm above the board")

    for ch, letter in zip(NAME, letters):
        bb = bbox_of(letter)
        dims = (bb.xlen, bb.ylen, bb.zlen)
        fits_cylinder = False
        for depth_index, depth in enumerate(dims):
            others = [dims[i] for i in range(3) if i != depth_index]
            diagonal = (others[0] ** 2 + others[1] ** 2) ** 0.5
            if depth < 57.1 and diagonal < 31.7:
                fits_cylinder = True
        if fits_cylinder:
            print(
                f"  warning: {ch} is {bb.xlen:.1f} x {bb.ylen:.1f} x {bb.zlen:.1f} mm"
                " and fits a small-parts cylinder"
            )

    print("Exporting STL...")
    STL_DIR.mkdir(parents=True, exist_ok=True)
    board_path = STL_DIR / "victor_board.stl"
    export_stl(to_bed(board), board_path, 0.08, 0.1)
    letter_paths = {}
    bed_letters = []
    for ch, letter in zip(NAME, letters):
        path = STL_DIR / f"victor_letter_{ch}.stl"
        bed = to_bed(letter)
        export_stl(bed, path, 0.045, 0.06)
        letter_paths[ch] = path
        bed_letters.append(bed)

    for path in [board_path, *letter_paths.values()]:
        tris, boundary = mesh_is_closed(path)
        print(f"  {path.name}: {tris} triangles, {boundary} open edges")
        if tris < 100 or boundary != 0:
            raise SystemExit(f"{path.name} is not a closed mesh")

    print("Writing 3MF plates...")
    bed_board = to_bed(board)
    board_size = bbox_of(bed_board)
    board_pos = ((BED - board_size.xlen) / 2.0, (BED - board_size.ylen) / 2.0, 0.0)
    _fits_on_plate(board_pos, (board_size.xlen, board_size.ylen), 1)

    # Letters sit on plate 2 in two loose rows. Colors are separate prints;
    # this packing is only so the plate opens inside the bed.
    letter_rows = [bed_letters[:3], bed_letters[3:]]
    row_gap = 10.0
    letter_pos = []
    row_heights = []
    row_widths = []
    for row in letter_rows:
        sizes = [bbox_of(letter) for letter in row]
        row_heights.append(max(size.ylen for size in sizes))
        row_widths.append(sum(size.xlen for size in sizes) + 8.0 * (len(row) - 1))
    letters_h = row_heights[0] + row_gap + row_heights[1]
    y = (BED - letters_h) / 2.0
    for row, row_w, row_h in zip(letter_rows, row_widths, row_heights):
        x = PLATE_STRIDE + (BED - row_w) / 2.0
        for letter in row:
            bb = bbox_of(letter)
            pos = (x, y + (row_h - bb.ylen) / 2.0, 0.0)
            letter_pos.append(pos)
            _fits_on_plate(pos, (bb.xlen, bb.ylen), 2)
            x += bb.xlen + 8.0
        y += row_h + row_gap

    objects = [
        {"name": "Board", "extruder": 1, "plate": 1, "mesh": stl_mesh(board_path), "pos": board_pos},
    ]
    for index, ch in enumerate(NAME):
        objects.append(
            {
                "name": f"Letter {ch}",
                "extruder": index + 2,
                "plate": 2,
                "mesh": stl_mesh(letter_paths[ch]),
                "pos": letter_pos[index],
            }
        )
    three_mf = ROOT / "victor_name_puzzle.3mf"
    write_3mf(three_mf, objects)
    with zipfile.ZipFile(three_mf) as zf:
        loaded = json.loads(zf.read("Metadata/project_settings.config"))
        if loaded["nozzle_diameter"] != ["0.4"] or loaded["printer_model"] != "Bambu Lab P2S":
            raise SystemExit("3MF project settings were not written")
        if "extruder_type" in loaded:
            raise SystemExit("3MF still sets extruder_type")
        model_xml = zf.read("3D/3dmodel.model").decode("utf-8")
        if "BambuStudio-01.10.02.75" not in model_xml:
            raise SystemExit("3MF is not marked as a Bambu Studio project")
        settings_xml = zf.read("Metadata/model_settings.config").decode("utf-8")
        if settings_xml.count("<plate>") != 2:
            raise SystemExit("3MF does not contain two plates")

    print("Rendering previews...")
    render(board, placed, 4, PREVIEW_DIR / "victor_puzzle_angle.png", "angle")
    render(board, placed, -1, PREVIEW_DIR / "victor_puzzle_seated.png", "angle")
    render(board, placed, 4, PREVIEW_DIR / "victor_puzzle_top.png", "top")
    render(board, placed, -1, PREVIEW_DIR / "victor_puzzle_holes.png", "holes")

    def grams(shape: cq.Workplane, shell_fraction: float) -> float:
        return shape.val().Volume() / 1000.0 * 1.24 * shell_fraction

    info = {
        "font_size": FONT_SIZE,
        "plan_scale": PLAN_SCALE,
        "letter_gap": LETTER_GAP,
        "board_w": layout["board_w"],
        "board_d": layout["board_d"],
        "board_h": FLOOR + WELL_DEPTH,
        "well_depth": WELL_DEPTH,
        "letter_thick": LETTER_THICK,
        "proud": LETTER_THICK - WELL_DEPTH,
        "fit_clearance": FIT_CLEARANCE,
        "measured_clearance": clearances,
        "floor": FLOOR,
        "letters_mm": [
            (ch, round(bbox_of(letter).xlen, 1), round(bbox_of(letter).ylen, 1))
            for ch, letter in zip(NAME, letters)
        ],
        "board_g": grams(board, 0.45),
        "letters_g": [grams(letter, 0.55) for letter in letters],
    }
    (ROOT / "build_info.txt").write_text(
        "\n".join(f"{key}={value}" for key, value in info.items()) + "\n",
        encoding="utf-8",
    )
    print("Done.")
    for key, value in info.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
