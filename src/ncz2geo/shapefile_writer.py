# -*- coding: utf-8 -*-
"""ESRI Shapefile exporter for NCZ2Geo (pure Python, no GDAL/pyshp).

A shapefile holds one geometry type, so a drawing is split into up to three
shapefiles: ``<name>_points``, ``<name>_lines`` and ``<name>_polygons``. Each is
written as ``.shp`` + ``.shx`` + ``.dbf`` with a UTF-8 ``.cpg`` and, for bundled
EPSG codes, an ESRI ``.prj``. Z values produce PointZ/PolyLineZ/PolygonZ shapes.
dBase limits attribute names to 10 characters, so the PlanGML/e-Plan columns
are given stable short names; the mapping is returned in the result.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Optional, Sequence

from ncz2geo._crs import esri_wkt
from ncz2geo._feature_table import (
    BOOL,
    FLOAT,
    INT,
    Feature,
    FeatureTable,
    build_feature_table,
    ring_signed_area,
)
from ncz2geo.ncz_engine.model import NetcadEntity

_SUFFIX = {"Point": "points", "LineString": "lines", "Polygon": "polygons"}
_SHAPE_2D = {"Point": 1, "LineString": 3, "Polygon": 5}
_SHAPE_Z = {"Point": 11, "LineString": 13, "Polygon": 15}
_NO_M = -1.0e39  # "no data" measure value

# Readable 10-character dBase names for the standard export columns.
_SHORT_NAMES = {
    "geometry_kind": "geom_kind",
    "layer_code": "layer_code",
    "layer_name": "layer_name",
    "color_argb": "color_argb",
    "name": "name",
    "label_text": "label_text",
    "text_height": "text_h",
    "rotation_degrees": "rotation",
    "box_width": "box_width",
    "box_height": "box_height",
    "scale": "scale",
    "grid_x": "grid_x",
    "grid_y": "grid_y",
    "radius": "radius",
    "start_angle": "start_ang",
    "end_angle": "end_angle",
    "is_closed": "is_closed",
    "plangml_plan_type": "pg_plan",
    "plangml_matched": "pg_matched",
    "plangml_tabaka": "pg_tabaka",
    "plangml_ust_grup_id": "pg_ugrp_id",
    "plangml_ust_grup_adi": "pg_ugrp_ad",
    "plangml_fonksiyon_kodu": "pg_fn_kod",
    "plangml_fonksiyon_adi": "pg_fn_adi",
    "plangml_geometri": "pg_geom",
    "plangml_match_type": "pg_match",
    "eplan_style_key": "ep_style",
    "eplan_style_plan_type": "ep_st_plan",
}


@dataclass
class ShapefileExportResult:
    """Paths, counts and attribute-name mapping of a shapefile export."""

    shapefiles: dict[str, str]  # geometry type -> .shp path
    feature_counts: dict[str, int]
    field_names: dict[str, str]  # export column -> dBase field name
    srid: Optional[int]
    prj_written: bool
    files: list[str] = field(default_factory=list)

    @property
    def feature_count(self) -> int:
        """Total number of features written across all shapefiles."""
        return sum(self.feature_counts.values())

    def to_dict(self) -> dict[str, Any]:
        """Return the export result as a JSON-serializable dictionary."""
        return {
            "shapefiles": dict(self.shapefiles),
            "feature_counts": dict(self.feature_counts),
            "feature_count": self.feature_count,
            "field_names": dict(self.field_names),
            "srid": self.srid,
            "prj_written": self.prj_written,
            "files": list(self.files),
        }


def dbf_field_names(columns: Sequence[str]) -> dict[str, str]:
    """Map export column names to unique dBase field names of at most 10 characters."""
    used: set[str] = set()
    mapping: dict[str, str] = {}
    for column in columns:
        base = _SHORT_NAMES.get(column)
        if base is None:
            base = column.replace("plangml_", "pg_").replace("eplan_", "ep_")
            base = "".join(
                ch if ch.isascii() and (ch.isalnum() or ch == "_") else "_" for ch in base
            )
        base = base[:10] or "field"
        candidate, n = base, 1
        while candidate.lower() in used:
            tail = f"_{n}"
            candidate = base[: 10 - len(tail)] + tail
            n += 1
        used.add(candidate.lower())
        mapping[column] = candidate
    return mapping


def _oriented_rings(feature: Feature) -> list[list[tuple[float, float, float]]]:
    """Return polygon rings with the exterior clockwise and holes counter-clockwise."""
    rings = []
    for index, ring in enumerate(feature.coordinates):
        clockwise = ring_signed_area(ring) < 0
        want_clockwise = index == 0
        rings.append(list(ring) if clockwise == want_clockwise else list(reversed(ring)))
    return rings


def _shape_record(feature: Feature, has_z: bool) -> bytes:
    """Encode one shape record body (little-endian content, no record header)."""
    gtype = feature.geometry_type
    shape_type = (_SHAPE_Z if has_z else _SHAPE_2D)[gtype]
    if gtype == "Point":
        x, y, z = feature.coordinates[0]
        body = struct.pack("<idd", shape_type, x, y)
        return body + (struct.pack("<dd", z, _NO_M) if has_z else b"")

    parts = _oriented_rings(feature) if gtype == "Polygon" else [list(feature.coordinates)]
    points = [pt for part in parts for pt in part]
    xs = [pt[0] for pt in points]
    ys = [pt[1] for pt in points]
    out = bytearray(
        struct.pack(
            "<i4d2i", shape_type, min(xs), min(ys), max(xs), max(ys), len(parts), len(points)
        )
    )
    start = 0
    for part in parts:
        out.extend(struct.pack("<i", start))
        start += len(part)
    for x, y, _z in points:
        out.extend(struct.pack("<2d", x, y))
    if has_z:
        zs = [pt[2] for pt in points]
        out.extend(struct.pack("<2d", min(zs), max(zs)))
        out.extend(struct.pack(f"<{len(zs)}d", *zs))
    return bytes(out)


def _main_header(
    shape_type: int, file_words: int, bbox: tuple[float, ...], zrange: tuple[float, float]
) -> bytes:
    """Return the 100-byte header shared by ``.shp`` and ``.shx``."""
    return (
        struct.pack(">7i", 9994, 0, 0, 0, 0, 0, file_words)
        + struct.pack("<2i", 1000, shape_type)
        + struct.pack("<4d", *bbox)
        + struct.pack("<4d", zrange[0], zrange[1], 0.0, 0.0)
    )


def _write_geometry(path: Path, features: list[Feature], has_z: bool) -> None:
    """Write the ``.shp`` and ``.shx`` files of one geometry type."""
    shape_type = (_SHAPE_Z if has_z else _SHAPE_2D)[features[0].geometry_type]
    vertices = [pt for f in features for pt in f.vertices()]
    bbox = (
        min(p[0] for p in vertices),
        min(p[1] for p in vertices),
        max(p[0] for p in vertices),
        max(p[1] for p in vertices),
    )
    zrange = (min(p[2] for p in vertices), max(p[2] for p in vertices)) if has_z else (0.0, 0.0)

    records = [_shape_record(f, has_z) for f in features]
    shp_body, shx_body = bytearray(), bytearray()
    offset_words = 50
    for number, content in enumerate(records, start=1):
        words = len(content) // 2
        shx_body.extend(struct.pack(">2i", offset_words, words))
        shp_body.extend(struct.pack(">2i", number, words) + content)
        offset_words += 4 + words

    path.with_suffix(".shp").write_bytes(
        _main_header(shape_type, 50 + len(shp_body) // 2, bbox, zrange) + bytes(shp_body)
    )
    path.with_suffix(".shx").write_bytes(
        _main_header(shape_type, 50 + len(shx_body) // 2, bbox, zrange) + bytes(shx_body)
    )


def _truncate_utf8(text: str, limit: int) -> bytes:
    """Encode ``text`` as UTF-8, cut to ``limit`` bytes without splitting a character."""
    data = text.encode("utf-8")
    if len(data) <= limit:
        return data
    return data[:limit].decode("utf-8", errors="ignore").encode("utf-8")


def _format_number(value: Optional[float], width: int, decimals: int) -> bytes:
    """Right-aligned dBase numeric text; blanks encode null."""
    if value is None:
        return b" " * width
    text = f"{value:.{decimals}f}" if decimals else str(int(value))
    if len(text) > width:  # keep the field width: fall back to exponent notation
        text = f"{value:.{max(0, width - 7)}e}"
    return text.rjust(width).encode("ascii")


def _write_dbf(
    path: Path, features: list[Feature], table: FeatureTable, names: dict[str, str]
) -> None:
    """Write the ``.dbf`` attribute table (dBase III) for ``features``."""
    specs: list[tuple[str, bytes, int, int]] = []  # column, type, width, decimals
    for column, kind in table.columns:
        if kind == BOOL:
            specs.append((column, b"L", 1, 0))
        elif kind == INT:
            specs.append((column, b"N", 18, 0))
        elif kind == FLOAT:
            specs.append((column, b"N", 24, 15))
        else:
            longest = max(
                [
                    len(str(f.properties[column]).encode("utf-8"))
                    for f in features
                    if f.properties[column] is not None
                ]
                or [1]
            )
            specs.append((column, b"C", max(1, min(254, longest)), 0))

    record_length = 1 + sum(width for _, _, width, _ in specs)
    header_length = 32 + 32 * len(specs) + 1
    today = date.today()
    out = bytearray(
        struct.pack(
            "<4BIHH20x",
            0x03,
            today.year - 1900,
            today.month,
            today.day,
            len(features),
            header_length,
            record_length,
        )
    )
    for column, ftype, width, decimals in specs:
        name = names[column].encode("ascii")
        out.extend(
            name.ljust(11, b"\0") + ftype + b"\0" * 4 + bytes([width, decimals]) + b"\0" * 14
        )
    out.append(0x0D)

    for feature in features:
        out.append(0x20)  # not deleted
        for column, ftype, width, decimals in specs:
            value = feature.properties[column]
            if ftype == b"L":
                out.extend(b"?" if value is None else (b"T" if value else b"F"))
            elif ftype == b"N":
                out.extend(_format_number(value, width, decimals))
            else:
                data = b"" if value is None else _truncate_utf8(str(value), width)
                out.extend(data.ljust(width, b" "))
    out.append(0x1A)
    path.with_suffix(".dbf").write_bytes(bytes(out))


def export_entities_to_shapefile(
    entities: Sequence[NetcadEntity],
    output_path: str | Path,
    srid: Optional[int] = None,
    *,
    plan_type: str = "UIP",
) -> ShapefileExportResult:
    """Export Netcad entities to ESRI Shapefiles, one per geometry type.

    ``output_path`` names the set: ``plan.shp`` (or ``plan``) writes
    ``plan_points.shp``, ``plan_lines.shp`` and ``plan_polygons.shp`` for the
    geometry types present. Attributes are the PlanGML/e-Plan properties of
    :func:`write_geojson` under 10-character dBase names (see
    ``result.field_names``); text is UTF-8 (declared in ``.cpg``) and cut at 254
    bytes. ``srid`` writes a ``.prj`` when the EPSG code is bundled.
    """
    base = Path(output_path)
    if base.suffix.lower() == ".shp":
        base = base.with_suffix("")
    base.parent.mkdir(parents=True, exist_ok=True)
    table = build_feature_table(entities, plan_type=plan_type)
    names = dbf_field_names([name for name, _ in table.columns])
    prj = esri_wkt(srid)

    shapefiles: dict[str, str] = {}
    counts: dict[str, int] = {}
    files: list[str] = []
    for gtype in ("Point", "LineString", "Polygon"):
        group = [f for f in table.features if f.geometry_type == gtype]
        if not group:
            continue
        target = base.parent / f"{base.name}_{_SUFFIX[gtype]}"
        _write_geometry(target, group, table.has_z)
        _write_dbf(target, group, table, names)
        target.with_suffix(".cpg").write_text("UTF-8", encoding="ascii")
        written = [target.with_suffix(ext) for ext in (".shp", ".shx", ".dbf", ".cpg")]
        if prj:
            target.with_suffix(".prj").write_text(prj, encoding="ascii")
            written.append(target.with_suffix(".prj"))
        shapefiles[gtype] = str(target.with_suffix(".shp"))
        counts[gtype] = len(group)
        files.extend(str(p) for p in written)

    return ShapefileExportResult(shapefiles, counts, names, srid, bool(prj and shapefiles), files)
