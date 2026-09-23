from __future__ import annotations

import io
import zipfile
from xml.sax.saxutils import escape

import numpy as np
import trimesh


CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
</Types>
"""

RELS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel" Target="/3D/3dmodel.model"/>
</Relationships>
"""


def _fmt(value: float) -> str:
    return f"{float(value):.6f}"


def build_model_xml(mesh: trimesh.Trimesh, object_name: str = "Drawing") -> str:
    vertices = np.asarray(mesh.vertices, dtype=float)
    faces = np.asarray(mesh.faces, dtype=int)
    lines: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<model unit="millimeter" xml:lang="en-US" '
        'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">',
        '  <metadata name="Application">Drawing to Print</metadata>',
        '  <metadata name="Title">' + escape(object_name) + "</metadata>",
        "  <resources>",
        '    <basematerials id="1">',
        '      <base name="PLA" displaycolor="#E8E8E8FF"/>',
        "    </basematerials>",
        f'    <object id="2" name="{escape(object_name)}" type="model" pid="1" pindex="0">',
        "      <mesh>",
        "        <vertices>",
    ]
    for x, y, z in vertices:
        lines.append(f'          <vertex x="{_fmt(x)}" y="{_fmt(y)}" z="{_fmt(z)}"/>')
    lines.append("        </vertices>")
    lines.append("        <triangles>")
    for a, b, c in faces:
        lines.append(f'          <triangle v1="{int(a)}" v2="{int(b)}" v3="{int(c)}"/>')
    lines.extend(
        [
            "        </triangles>",
            "      </mesh>",
            "    </object>",
            "  </resources>",
            "  <build>",
            '    <item objectid="2"/>',
            "  </build>",
            "</model>",
            "",
        ]
    )
    return "\n".join(lines)


def write_3mf(mesh: trimesh.Trimesh, object_name: str = "Drawing") -> bytes:
    model_xml = build_model_xml(mesh, object_name=object_name)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", CONTENT_TYPES)
        zf.writestr("_rels/.rels", RELS)
        zf.writestr("3D/3dmodel.model", model_xml)
    return buffer.getvalue()
