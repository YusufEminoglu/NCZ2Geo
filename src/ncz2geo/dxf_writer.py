# -*- coding: utf-8 -*-
"""AutoCAD DXF exporter for NCZ2Geo (ASCII DXF R12, pure Python).

R12 (AC1009) is the most widely readable DXF dialect: AutoCAD, Netcad, QGIS,
LibreCAD and GDAL all open it. Each Netcad layer becomes a DXF layer; points
become POINT, text annotations TEXT (height and rotation kept), lines and
polygon rings POLYLINE (3D polylines when the drawing has elevations, closed
for polygons). Text uses the Turkish ANSI_1254 code page. DXF has no attribute
table, so the PlanGML/e-Plan properties are not carried; use GeoPackage,
GeoParquet, FlatGeobuf or Shapefile when attributes matter.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence

from ncz2geo._feature_table import Feature, build_feature_table
from ncz2geo.ncz_engine.model import NetcadEntity

_CODEPAGE = "cp1254"
_TEXT_KINDS = {"text"}
_INVALID_LAYER_CHARS = re.compile(r"[<>/\\\":;?*|=,'\s]")


@dataclass
class DxfExportResult:
    """Summary of a DXF export."""

    output_path: str
    entity_counts: dict[str, int]
    layers: list[str] = field(default_factory=list)
    srid: Optional[int] = None

    @property
    def entity_count(self) -> int:
        """Total number of DXF entities written."""
        return sum(self.entity_counts.values())

    def to_dict(self) -> dict[str, Any]:
        """Return the export result as a JSON-serializable dictionary."""
        return {
            "output_path": self.output_path,
            "entity_counts": dict(self.entity_counts),
            "entity_count": self.entity_count,
            "layers": list(self.layers),
            "srid": self.srid,
        }


def dxf_layer_name(name: str) -> str:
    """Return a DXF-safe layer name (``0`` for empty names)."""
    cleaned = _INVALID_LAYER_CHARS.sub("_", name.strip())
    return cleaned[:255] or "0"


def _num(value: float) -> str:
    """Format a coordinate/number for DXF without exponent noise."""
    text = f"{value:.10f}".rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"


class _Dxf:
    """Accumulates DXF group-code/value pairs."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def add(self, code: int, value: Any) -> None:
        """Append one group code and its value."""
        self.lines.append(f"{code:>3}")
        self.lines.append(_num(value) if isinstance(value, float) else str(value))

    def point(self, x: float, y: float, z: float, base: int = 10) -> None:
        """Append an XYZ coordinate triple using group codes ``base``, ``base+10``, ``base+20``."""
        self.add(base, float(x))
        self.add(base + 10, float(y))
        self.add(base + 20, float(z))


def _write_polyline(
    dxf: _Dxf, layer: str, vertices: list[tuple[float, float, float]], closed: bool, has_z: bool
) -> None:
    """Append a POLYLINE with its VERTEX entities and SEQEND."""
    if closed and len(vertices) > 1 and vertices[0] == vertices[-1]:
        vertices = vertices[:-1]
    flags = (1 if closed else 0) | (8 if has_z else 0)
    dxf.add(0, "POLYLINE")
    dxf.add(8, layer)
    dxf.add(66, 1)
    dxf.point(0.0, 0.0, 0.0 if has_z else vertices[0][2])
    dxf.add(70, flags)
    for x, y, z in vertices:
        dxf.add(0, "VERTEX")
        dxf.add(8, layer)
        dxf.point(x, y, z if has_z else 0.0)
        if has_z:
            dxf.add(70, 32)  # 3D polyline vertex
    dxf.add(0, "SEQEND")
    dxf.add(8, layer)


def _write_feature(dxf: _Dxf, feature: Feature, has_z: bool, counts: dict[str, int]) -> None:
    """Append the DXF entities of one feature and update ``counts``."""
    props = feature.properties
    layer = dxf_layer_name(str(props.get("layer_name") or ""))
    kind = str(props.get("geometry_kind") or "").lower()
    if feature.geometry_type == "Point":
        x, y, z = feature.coordinates[0]
        text = str(props.get("label_text") or "")
        height = props.get("text_height") or 0.0
        if kind in _TEXT_KINDS and text and height > 0:
            dxf.add(0, "TEXT")
            dxf.add(8, layer)
            dxf.point(x, y, z)
            dxf.add(40, float(height))
            dxf.add(1, text.replace("\r", " ").replace("\n", " "))
            rotation = props.get("rotation_degrees") or 0.0
            if rotation:
                dxf.add(50, float(rotation))
            counts["TEXT"] = counts.get("TEXT", 0) + 1
        else:
            dxf.add(0, "POINT")
            dxf.add(8, layer)
            dxf.point(x, y, z)
            counts["POINT"] = counts.get("POINT", 0) + 1
        return
    if feature.geometry_type == "LineString":
        _write_polyline(dxf, layer, list(feature.coordinates), False, has_z)
        counts["POLYLINE"] = counts.get("POLYLINE", 0) + 1
        return
    for ring in feature.coordinates:
        _write_polyline(dxf, layer, list(ring), True, has_z)
        counts["POLYLINE"] = counts.get("POLYLINE", 0) + 1


def export_entities_to_dxf(
    entities: Sequence[NetcadEntity],
    output_path: str | Path,
    srid: Optional[int] = None,
    *,
    plan_type: str = "UIP",
) -> DxfExportResult:
    """Export Netcad entities to an ASCII DXF R12 drawing.

    Layers keep their Netcad names (characters DXF forbids become ``_``).
    ``srid`` is informational only: DXF has no CRS, so coordinates are written
    exactly as stored. Attributes are not exported (see module docstring).
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    table = build_feature_table(entities, plan_type=plan_type)
    layers = sorted(
        {dxf_layer_name(str(f.properties.get("layer_name") or "")) for f in table.features} | {"0"}
    )
    min_x, min_y, max_x, max_y = table.bbox or (0.0, 0.0, 0.0, 0.0)

    dxf = _Dxf()
    dxf.add(0, "SECTION")
    dxf.add(2, "HEADER")
    dxf.add(9, "$ACADVER")
    dxf.add(1, "AC1009")
    dxf.add(9, "$DWGCODEPAGE")
    dxf.add(3, "ANSI_1254")
    dxf.add(9, "$EXTMIN")
    dxf.point(min_x, min_y, 0.0)
    dxf.add(9, "$EXTMAX")
    dxf.point(max_x, max_y, 0.0)
    dxf.add(0, "ENDSEC")

    dxf.add(0, "SECTION")
    dxf.add(2, "TABLES")
    dxf.add(0, "TABLE")
    dxf.add(2, "LTYPE")
    dxf.add(70, 1)
    dxf.add(0, "LTYPE")
    dxf.add(2, "CONTINUOUS")
    dxf.add(70, 0)
    dxf.add(3, "Solid line")
    dxf.add(72, 65)
    dxf.add(73, 0)
    dxf.add(40, 0.0)
    dxf.add(0, "ENDTAB")
    dxf.add(0, "TABLE")
    dxf.add(2, "LAYER")
    dxf.add(70, len(layers))
    for name in layers:
        dxf.add(0, "LAYER")
        dxf.add(2, name)
        dxf.add(70, 0)
        dxf.add(62, 7)
        dxf.add(6, "CONTINUOUS")
    dxf.add(0, "ENDTAB")
    dxf.add(0, "ENDSEC")

    counts: dict[str, int] = {}
    dxf.add(0, "SECTION")
    dxf.add(2, "ENTITIES")
    for feature in table.features:
        _write_feature(dxf, feature, table.has_z, counts)
    dxf.add(0, "ENDSEC")
    dxf.add(0, "EOF")

    text = "\r\n".join(dxf.lines) + "\r\n"
    out.write_bytes(text.encode(_CODEPAGE, errors="replace"))
    return DxfExportResult(str(out), counts, [name for name in layers if name != "0"], srid)
