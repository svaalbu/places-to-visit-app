#!/usr/bin/env python3
"""Generate a wooden-style FINN name puzzle sized for a Bambu Lab P2S.

The board is one piece. Each slot is that letter's outline, so F only fits
the F hole and N only fits an N hole. The slot is 0.40 mm larger than the
letter, which is the allowance a 0.4 mm nozzle needs for the piece to drop in.

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
NAME = "FINN"

# Millimetres. The P2S build volume is 256 x 256 x 256.
TARGET_BOARD_W = 236.0
# How far the slot wall sits outside the letter. This is the whole fit gap.
FIT_CLEARANCE = 0.40
FRAME_X = 13.0
FRAME_Y = 14.0
DIVIDER = 10.0
FLOOR = 5.0
WELL_DEPTH = 11.0
LETTER_THICK = 15.5
BOARD_CORNER_R = 11.0
OUTER_EDGE_R = 1.6
TOP_SOFTEN = 0.85
BOTTOM_LEAD = 0.30
BED = 256.0


COLORS = {
    "board": (0.91, 0.78, 0.58),
    "F": (0.86, 0.22, 0.18),
    "I": (0.18, 0.42, 0.86),
    "N1": (0.22, 0.62, 0.30),
    "N2": (0.95, 0.78, 0.12),
}

HEX = {
    "board": "#E8C794",
    "F": "#DB382E",
    "I": "#2E6BDB",
    "N1": "#389E4D",
    "N2": "#F2C71F",
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


def board_width_for(widths: list[float]) -> float:
    return sum(widths) + DIVIDER * (len(widths) - 1) + 2 * FRAME_X


def choose_font_size() -> float:
    """Pick a font size whose board lands just under the bed limit."""
    # Cap height scales with the requested size. Probe once, then scale.
    probe = 100.0
    widths = []
    for ch in NAME:
        bb = bbox_of(make_letter(ch, probe, 4.0))
        widths.append(bb.xlen)
    width = board_width_for(widths)
    size = probe * (TARGET_BOARD_W / width)
    # Re-measure because font hinting is not perfectly linear, then nudge.
    for _ in range(4):
        widths = [bbox_of(make_letter(ch, size, 4.0)).xlen for ch in NAME]
        width = board_width_for(widths)
        if abs(width - TARGET_BOARD_W) < 0.4:
            break
        size *= TARGET_BOARD_W / width
    return size


def _accept(candidate: cq.Workplane, fallback: cq.Workplane) -> cq.Workplane:
    try:
        solid = candidate.val()
        if solid.isValid() and len(candidate.solids().vals()) == 1 and solid.Volume() > 1000:
            return candidate
    except Exception:
        pass
    return fallback


def soften_letter(letter: cq.Workplane) -> cq.Workplane:
    """Break the sharp top edge when the font outline allows it.

    Lilita One is already rounded in plan. A failed fillet must not replace
    the letter with a broken solid.
    """
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
    """A prism of the letter outline, grown by clearance on every side."""
    wire = letter.faces("<Z").val().outerWire()
    grown = wire.offset2D(clearance, "arc")
    if len(grown) != 1:
        raise SystemExit(f"letter offset produced {len(grown)} outlines")
    pocket = cq.Workplane("XY").add(grown[0]).toPending().extrude(WELL_DEPTH + 3.0)
    if not pocket.val().isValid() or len(pocket.solids().vals()) != 1:
        raise SystemExit("letter pocket is not a single valid solid")
    return pocket


def build_board(layout: dict, raw_letters: list[cq.Workplane]) -> tuple[cq.Workplane, list[cq.Workplane]]:
    board_w = layout["board_w"]
    board_d = layout["board_d"]
    board_h = FLOOR + WELL_DEPTH
    board = (
        cq.Workplane("XY")
        .center(board_w / 2, board_d / 2)
        .rect(board_w, board_d)
        .extrude(board_h)
        .edges("|Z")
        .fillet(BOARD_CORNER_R)
    )
    try:
        board = board.faces(">Z").edges().fillet(OUTER_EDGE_R)
    except Exception as exc:
        print(f"  outer edge fillet skipped ({exc})")

    cutters = None
    pockets = []
    for well, letter in zip(layout["wells"], raw_letters):
        pocket = letter_pocket(letter, FIT_CLEARANCE)
        dx, dy, _ = shift_for(letter, well, 0.0)
        pocket = pocket.translate((dx, dy, FLOOR))
        pockets.append(pocket)
        cutters = pocket if cutters is None else cutters.union(pocket)

    board = board.cut(cutters)
    return board, pockets


def layout_for(raw_letters: list[cq.Workplane]) -> dict:
    boxes = [bbox_of(letter) for letter in raw_letters]
    letter_h = max(bb.ylen for bb in boxes)
    y0 = FRAME_Y
    wells = []
    x = FRAME_X
    for bb in boxes:
        wells.append(
            {
                "x0": x,
                "y0": y0,
                "w": bb.xlen,
                "h": letter_h,
                "cx": x + bb.xlen / 2,
                "cy": y0 + letter_h / 2,
                "letter_bb": bb,
            }
        )
        x += bb.xlen + DIVIDER
    board_w = x - DIVIDER + FRAME_X
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
        well["cx"] - bb.xlen / 2 - bb.xmin,
        well["cy"] - bb.ylen / 2 - bb.ymin,
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
    """Gap between the letter and the well wall, taken at mid-depth.

    A thin slice stays far from the floor and the top rim, so the nearest
    board surface is the wall rather than the bottom of the pocket.
    """
    z_mid = FLOOR + WELL_DEPTH / 2.0
    slice_h = 0.4
    clip = (
        cq.Workplane("XY")
        .box(board_w + 20, board_d + 20, slice_h, centered=(True, True, True))
        .translate((board_w / 2, board_d / 2, z_mid))
    )
    clipped = letter.intersect(clip)
    return min_distance(clipped.val(), board.val())


def solid_volume(shape: cq.Workplane) -> float:
    return float(shape.val().Volume())


def assert_single_piece(shape: cq.Workplane, label: str) -> None:
    solids = shape.solids().vals()
    if len(solids) != 1:
        raise SystemExit(f"{label} is {len(solids)} solids, expected 1")
    if not shape.val().isValid():
        raise SystemExit(f"{label} is not a valid solid")


def no_enclosed_counters(letter: cq.Workplane, label: str) -> None:
    """F, I and N are solid strokes. A hole would mean the font came out wrong."""
    wires = letter.faces("<Z").wires().vals()
    if len(wires) != 1:
        raise SystemExit(f"{label} bottom has {len(wires)} wires; expected a solid letter")


def to_bed(shape: cq.Workplane) -> cq.Workplane:
    bb = bbox_of(shape)
    return shape.translate((-bb.xmin, -bb.ymin, -bb.zmin))


def stl_mesh(path: Path) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]:
    """Load a binary STL and weld vertices.

    CadQuery's raw tessellation leaves cracks. The STL exporter welds them,
    and Bambu Studio reports those cracks as open edges.
    """
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
    """Single-nozzle P2S project. Five filament slots, one nozzle.

    Bambu Studio shows "invalid config" when the file is not a Bambu printer
    and nozzle_diameter has more entries than extruder_type. A P2S name plus
    one nozzle diameter passes that check. The preset names are the system
    profiles, so Studio keeps those profiles and only overrides the slot colors.
    """
    filaments = ["Bambu PLA Basic @BBL P2S"] * 5
    return {
        "name": "project_settings",
        "printer_model": "Bambu Lab P2S",
        "printer_variant": "0.4",
        "nozzle_diameter": ["0.4"],
        "extruder_type": ["Direct Drive Standard"],
        "printer_settings_id": "Bambu Lab P2S 0.4 nozzle",
        "print_settings_id": "0.20mm Standard @BBL P2S",
        "filament_settings_id": filaments,
        "filament_colour": [HEX["board"], HEX["F"], HEX["I"], HEX["N1"], HEX["N2"]],
        "filament_type": ["PLA"] * 5,
        "filament_diameter": ["1.75"] * 5,
        "filament_self_index": ["1", "2", "3", "4", "5"],
        "filament_extruder_variant": ["Direct Drive Standard"] * 5,
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
            "filament_colour",
            "filament_colour",
            "filament_colour",
            "filament_colour",
            "filament_colour",
            "",
        ],
    }


def write_3mf(path: Path, objects: list[dict]) -> None:
    """Bambu Studio project for a P2S with a 0.4 mm nozzle.

    Geometry is the welded STL mesh. Project settings name the P2S preset so
    Studio loads the file as its own project instead of discarding the config.
    """

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
    plate_instances = []
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
        plate_instances.append(
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
    if settings["printer_model"] != "Bambu Lab P2S" or settings["nozzle_diameter"] != ["0.4"]:
        raise SystemExit("project settings are not a single-nozzle P2S")
    if len(settings["inherits_group"]) != 7 or len(settings["different_settings_to_system"]) != 7:
        raise SystemExit("filament preset lists do not match the five colors")

    model = f'''<?xml version="1.0" encoding="UTF-8"?>
<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">
  <metadata name="Application">BambuStudio-01.10.02.75</metadata>
  <metadata name="BambuStudio:3mfVersion">1</metadata>
  <metadata name="Title">FINN name puzzle</metadata>
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
  <plate>
    <metadata key="plater_id" value="1"/>
    <metadata key="plater_name" value=""/>
    <metadata key="locked" value="false"/>
{chr(10).join(plate_instances)}
  </plate>
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


def _polydata(shape: cq.Workplane, tolerance: float = 0.12):
    import vtk

    verts, tris = shape.val().tessellate(tolerance, 0.1)
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


def render(board, placed, lifted_index: int, path: Path, kind: str) -> None:
    import vtk

    ren = vtk.vtkRenderer()
    ren.SetBackground(0.93, 0.91, 0.86)
    ren.AddActor(_actor(board, COLORS["board"], 0.12))
    keys = ["F", "I", "N1", "N2"]
    for i, letter in enumerate(placed):
        if kind == "holes":
            continue
        if i == lifted_index and kind == "top":
            continue
        shape = letter
        if i == lifted_index and kind == "angle":
            # Set the piece beside its hole so the matching cavity stays visible.
            shape = letter.translate((55, 18, 18))
        ren.AddActor(_actor(shape, COLORS[keys[i]], 0.28))

    win = vtk.vtkRenderWindow()
    win.SetOffScreenRendering(1)
    win.SetMultiSamples(8)
    win.AddRenderer(ren)
    win.SetSize(1800, 1100 if kind != "top" else 900)

    ren.ResetCamera()
    cam = ren.GetActiveCamera()
    bb = bbox_of(board)
    fx, fy = bb.center.x, bb.center.y
    if kind == "top":
        # Look straight down. Up-vector is +Y so the name reads left to right.
        cam.SetParallelProjection(True)
        cam.SetFocalPoint(fx, fy, 0)
        cam.SetPosition(fx, fy, 500)
        cam.SetViewUp(0, 1, 0)
        aspect = 1800 / 900
        half_height = max(bb.ylen * 0.62, (bb.xlen * 0.55) / aspect)
        cam.SetParallelScale(half_height)
    else:
        # Fit a front view, then orbit so the whole board stays in frame.
        # "holes" is steeper so the letter-shaped cavities read clearly.
        cam.SetViewUp(0, 0, 1)
        cam.SetFocalPoint(fx, fy, 6)
        cam.SetPosition(fx, fy - 800, 6)
        ren.ResetCamera()
        cam.Azimuth(18 if kind == "angle" else 12)
        cam.Elevation(42 if kind == "angle" else 58)
        cam.OrthogonalizeViewUp()
        cam.Zoom(1.28 if kind == "angle" else 1.35)
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
    """Return (triangle count, boundary edge count). Boundary edges should be 0."""
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


def export_stl(shape: cq.Workplane, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cq.exporters.export(shape, str(path), tolerance=0.045, angularTolerance=0.06)


def main() -> None:
    if not FONT.exists():
        raise SystemExit(f"Missing font: {FONT}")

    print("Choosing letter size for a 256 mm bed...")
    font_size = choose_font_size()
    print(f"  font size {font_size:.2f}")

    raw = [make_letter(ch, font_size, LETTER_THICK) for ch in NAME]
    for ch, letter in zip(NAME, raw):
        no_enclosed_counters(letter, ch)
        assert_single_piece(letter, f"raw {ch}")

    layout = layout_for(raw)
    print(f"  board {layout['board_w']:.1f} x {layout['board_d']:.1f} mm")
    if layout["board_w"] > BED - 8 or layout["board_d"] > BED - 8:
        raise SystemExit("Board does not fit the P2S bed with margin")
    print("  building letter-shaped slots...")
    board, pockets = build_board(layout, raw)
    assert_single_piece(board, "board")
    for index in range(len(pockets) - 1):
        wood = min_distance(pockets[index].val(), pockets[index + 1].val())
        print(f"  wood between slot {index + 1} and {index + 2}: {wood:.2f} mm")
        if wood < 4.0:
            raise SystemExit("letter slots break into each other")

    placed_raw = [place_letter(letter, well, FLOOR) for letter, well in zip(raw, layout["wells"])]
    clearances = []
    for ch, letter in zip(NAME, placed_raw):
        overlap = solid_volume(board.intersect(letter))
        if overlap > 0.05:
            raise SystemExit(f"{ch} intersects its own slot by {overlap:.3f} mm^3")
        gap_mm = side_clearance(letter, board, layout["board_w"], layout["board_d"])
        clearances.append(gap_mm)
        print(f"  {ch} fits its slot with {gap_mm:.2f} mm of room")
        if not 0.25 <= gap_mm <= 0.60:
            raise SystemExit(f"{ch} slot is not a close fit ({gap_mm:.2f} mm)")

    # A letter must collide with every slot that is not its own shape.
    # The two N pieces share a shape, so either N fits either N slot.
    for piece_i, piece_ch in enumerate(NAME):
        for slot_i, slot_ch in enumerate(NAME):
            if piece_ch == slot_ch:
                continue
            moved = place_letter(raw[piece_i], layout["wells"][slot_i], FLOOR)
            clash = solid_volume(board.intersect(moved))
            print(f"  {piece_ch} in the {slot_ch} slot clashes by {clash:.0f} mm^3")
            if clash < 200:
                raise SystemExit(f"{piece_ch} fits the {slot_ch} slot")

    print("Softening letter edges...")
    letters = []
    for ch, letter in zip(NAME, raw):
        print(f"  {ch}")
        letters.append(soften_letter(letter))
        assert_single_piece(letters[-1], ch)

    placed = [place_letter(letter, well, FLOOR) for letter, well in zip(letters, layout["wells"])]
    for ch, letter in zip(NAME, placed):
        overlap = solid_volume(board.intersect(letter))
        if overlap > 0.05:
            raise SystemExit(f"Softened {ch} hits the board ({overlap:.3f} mm^3)")
        bb = bbox_of(letter)
        if bb.zmin < FLOOR - 0.05:
            raise SystemExit(f"{ch} drops through the well floor")
        proud = bb.zmax - (FLOOR + WELL_DEPTH)
        print(f"  {ch} sits {proud:.2f} mm above the board")

    # Pieces must be larger than the US small-parts cylinder (31.7 mm diameter).
    for ch, letter in zip(NAME, letters):
        bb = bbox_of(letter)
        if min(bb.xlen, bb.ylen) < 32 or max(bb.xlen, bb.ylen) < 58:
            raise SystemExit(f"{ch} is small for a toddler toy: {bb.xlen:.1f} x {bb.ylen:.1f}")

    print("Exporting STL...")
    STL_DIR.mkdir(parents=True, exist_ok=True)
    stl_board = STL_DIR / "finn_board.stl"
    # The board is broad, flat surfaces. A slightly looser mesh is still far
    # smoother than a 0.4 mm nozzle and keeps the file smaller.
    cq.exporters.export(to_bed(board), str(stl_board), tolerance=0.08, angularTolerance=0.1)
    stl_letters = {}
    for ch, letter in zip("FIN", letters[:3]):
        # The two N pieces are the same shape. One file is printed twice.
        path = STL_DIR / f"finn_letter_{ch}.stl"
        export_stl(to_bed(letter), path)
        stl_letters[ch] = path

    for path in [stl_board, *stl_letters.values()]:
        tris, boundary = mesh_is_closed(path)
        print(f"  {path.name}: {tris} triangles, {boundary} open edges")
        if tris < 100 or boundary != 0:
            raise SystemExit(f"{path.name} is not a closed mesh")

    print("Writing 3MF plate...")
    bed_letters = [to_bed(letter) for letter in letters]
    bed_board = to_bed(board)
    # Lay the board behind the letters, everything in the positive quadrant.
    letter_depths = [bbox_of(letter).ylen for letter in bed_letters]
    row_h = max(letter_depths)
    cursor = 6.0
    letter_pos = []
    for letter in bed_letters:
        bb = bbox_of(letter)
        letter_pos.append((cursor, 6.0 + (row_h - bb.ylen) / 2, 0.0))
        cursor += bb.xlen + 8.0
    board_bb = bbox_of(bed_board)
    board_pos = (6.0, 6.0 + row_h + 12.0, 0.0)
    plate_w = max(board_pos[0] + board_bb.xlen, cursor) + 6
    plate_d = board_pos[1] + board_bb.ylen + 6
    if plate_w > BED or plate_d > BED:
        raise SystemExit(f"Plate layout is {plate_w:.1f} x {plate_d:.1f}, over the bed")

    # Filament slots are 1-based: board, F, I, green N, yellow N.
    # The two N pieces share one STL and are separate objects so the colors differ.
    n_mesh = stl_mesh(stl_letters["N"])
    objects = [
        {
            "name": "Board",
            "extruder": 1,
            "mesh": stl_mesh(stl_board),
            "pos": board_pos,
        },
        {
            "name": "Letter F",
            "extruder": 2,
            "mesh": stl_mesh(stl_letters["F"]),
            "pos": letter_pos[0],
        },
        {
            "name": "Letter I",
            "extruder": 3,
            "mesh": stl_mesh(stl_letters["I"]),
            "pos": letter_pos[1],
        },
        {
            "name": "Letter N (green)",
            "extruder": 4,
            "mesh": n_mesh,
            "pos": letter_pos[2],
        },
        {
            "name": "Letter N (yellow)",
            "extruder": 5,
            "mesh": n_mesh,
            "pos": letter_pos[3],
        },
    ]
    three_mf = ROOT / "finn_name_puzzle.3mf"
    write_3mf(three_mf, objects)
    with zipfile.ZipFile(three_mf) as zf:
        loaded = json.loads(zf.read("Metadata/project_settings.config"))
        if loaded["nozzle_diameter"] != ["0.4"] or loaded["printer_model"] != "Bambu Lab P2S":
            raise SystemExit("3MF project settings were not written")
        if "BambuStudio-01.10.02.75" not in zf.read("3D/3dmodel.model").decode("utf-8"):
            raise SystemExit("3MF is not marked as a Bambu Studio project")

    print("Rendering previews...")
    render(board, placed, lifted_index=3, path=PREVIEW_DIR / "finn_puzzle_angle.png", kind="angle")
    render(board, placed, lifted_index=-1, path=PREVIEW_DIR / "finn_puzzle_seated.png", kind="angle")
    render(board, placed, lifted_index=3, path=PREVIEW_DIR / "finn_puzzle_top.png", kind="top")
    render(board, placed, lifted_index=-1, path=PREVIEW_DIR / "finn_puzzle_holes.png", kind="holes")

    def grams(shape: cq.Workplane, shell_fraction: float) -> float:
        # PLA is about 1.24 g/cm^3. shell_fraction is a slicer estimate, not a solid.
        return shape.val().Volume() / 1000.0 * 1.24 * shell_fraction

    info = {
        "font_size": font_size,
        "board_w": layout["board_w"],
        "board_d": layout["board_d"],
        "board_h": FLOOR + WELL_DEPTH,
        "well_depth": WELL_DEPTH,
        "letter_thick": LETTER_THICK,
        "proud": LETTER_THICK - WELL_DEPTH,
        "fit_clearance": FIT_CLEARANCE,
        "measured_clearance": clearances,
        "floor": FLOOR,
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
