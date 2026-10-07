from __future__ import annotations

import zipfile
from io import BytesIO
from xml.etree import ElementTree as ET

import numpy as np
import trimesh

from app.config import settings
from app.mesh.prepare import prepare_for_print, rescale_prepared
from app.mesh.threemf import write_3mf
from app.providers.stub import ellipse_from_drawing
from tests.conftest import circle_png

NS = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}


def test_stub_mesh_is_watertight_volume():
    mesh = ellipse_from_drawing(circle_png())
    assert mesh.is_watertight
    assert mesh.volume > 0


def test_prepare_scales_grounds_and_centers():
    mesh = trimesh.creation.icosphere(subdivisions=2, radius=3.0)
    # Offset and Y-up-ish placement
    mesh.apply_translation([10, 20, 30])
    prepared = prepare_for_print(mesh, target_size_mm=80, y_up=False)
    assert prepared.is_watertight
    longest = float(prepared.mesh.extents.max())
    assert abs(longest - 80.0) < 0.05
    assert abs(prepared.mesh.bounds[0][2]) < 1e-3
    xy = prepared.mesh.centroid[:2]
    assert np.linalg.norm(xy) < 1e-2


def test_y_up_rotation_puts_min_on_bed():
    mesh = trimesh.creation.cylinder(radius=1.0, height=4.0, sections=24)
    # Cylinder along Z; mark as Y-up so it is rotated onto the bed.
    prepared = prepare_for_print(mesh, target_size_mm=80, y_up=True)
    assert abs(prepared.mesh.bounds[0][2]) < 1e-3
    assert abs(float(prepared.mesh.extents.max()) - 80.0) < 0.1


def test_size_clamp():
    mesh = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
    small = prepare_for_print(mesh, target_size_mm=1, y_up=False)
    large = prepare_for_print(mesh, target_size_mm=1000, y_up=False)
    assert abs(float(small.mesh.extents.max()) - settings.min_size_mm) < 0.05
    assert abs(float(large.mesh.extents.max()) - settings.max_size_mm) < 0.05


def test_rescale_keeps_ground():
    mesh = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
    prepared = prepare_for_print(mesh, target_size_mm=80, y_up=False)
    bigger = rescale_prepared(prepared.mesh, 120)
    assert abs(float(bigger.extents.max()) - 120) < 0.05
    assert abs(bigger.bounds[0][2]) < 1e-3


def test_open_mesh_is_made_watertight():
    src = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
    mesh = trimesh.Trimesh(vertices=src.vertices.copy(), faces=src.faces[:-40].copy(), process=True)
    prepared = prepare_for_print(mesh, target_size_mm=80, y_up=False)
    assert prepared.is_watertight
    assert abs(float(prepared.mesh.extents.max()) - 80.0) < 0.2
    assert abs(prepared.mesh.bounds[0][2]) < 1e-2


def test_3mf_is_core_zip_in_millimetres():
    mesh = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
    prepared = prepare_for_print(mesh, target_size_mm=80, y_up=False)
    data = write_3mf(prepared.mesh, object_name="Sphere")
    with zipfile.ZipFile(BytesIO(data)) as zf:
        names = set(zf.namelist())
        assert "[Content_Types].xml" in names
        assert "_rels/.rels" in names
        assert "3D/3dmodel.model" in names
        xml = zf.read("3D/3dmodel.model")
    root = ET.fromstring(xml)
    assert root.attrib.get("unit") == "millimeter"
    vertices = root.findall(".//m:vertex", NS)
    triangles = root.findall(".//m:triangle", NS)
    assert len(vertices) == len(prepared.mesh.vertices)
    assert len(triangles) == len(prepared.mesh.faces)
    zs = [float(v.attrib["z"]) for v in vertices]
    assert min(zs) >= -1e-3
