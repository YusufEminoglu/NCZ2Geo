# -*- coding: utf-8 -*-
"""Cloud-Native FlatGeobuf (.fgb) Binary Vector Exporter for NCZ2Geo.

Writes spec-conformant FlatGeobuf v3 files (https://flatgeobuf.org): a
FlatBuffers header with typed attribute columns and CRS, an optional packed
Hilbert R-tree spatial index, and size-prefixed FlatBuffers features. The
output opens in GDAL/OGR, QGIS and the FlatGeobuf JavaScript/Python readers,
and the index lets clients fetch only the features of a bounding box.
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence

from ncz2geo._feature_table import BOOL, FLOAT, INT, Feature, build_feature_table
from ncz2geo._flatbuffers import Table, encode
from ncz2geo.ncz_engine.model import NetcadEntity

# FlatGeobuf magic bytes: 'fgb' + spec major version 3 + 'fgb' + patch 0
FGB_MAGIC = b"\x66\x67\x62\x03\x66\x67\x62\x00"

_GEOMETRY_CODES = {"Point": 1, "LineString": 2, "Polygon": 3}
_COLUMN_CODES = {BOOL: 2, INT: 7, FLOAT: 10}  # Bool, Long, Double; everything else String
_STRING_CODE = 11
_NODE_ITEM = struct.Struct("<ddddQ")  # min_x, min_y, max_x, max_y, offset
DEFAULT_INDEX_NODE_SIZE = 16


@dataclass
class FlatGeobufExportResult:
    feature_count: int
    file_size_bytes: int
    bounding_box_min_x: float
    bounding_box_min_y: float
    bounding_box_max_x: float
    bounding_box_max_y: float
    output_path: str

    def to_dict(self) -> dict[str, Any]:
        """Return the FlatGeobuf export result as a JSON-serializable dictionary."""
        return {
            "feature_count": self.feature_count,
            "file_size_bytes": self.file_size_bytes,
            "bbox": [
                round(self.bounding_box_min_x, 3),
                round(self.bounding_box_min_y, 3),
                round(self.bounding_box_max_x, 3),
                round(self.bounding_box_max_y, 3),
            ],
            "output_path": self.output_path,
        }


def _feature_bbox(feature: Feature) -> tuple[float, float, float, float]:
    """Return the 2D bounding box of one feature."""
    vertices = feature.vertices()
    xs = [pt[0] for pt in vertices]
    ys = [pt[1] for pt in vertices]
    return min(xs), min(ys), max(xs), max(ys)


def _hilbert(x: int, y: int) -> int:
    """Hilbert curve index of a cell on a 2**16 x 2**16 grid."""
    index = 0
    s = 1 << 15
    while s > 0:
        rx = 1 if x & s else 0
        ry = 1 if y & s else 0
        index += s * s * ((3 * rx) ^ ry)
        if ry == 0:
            if rx == 1:
                x, y = s - 1 - x, s - 1 - y
            x, y = y, x
        s >>= 1
    return index


def _level_bounds(num_items: int, node_size: int) -> list[tuple[int, int]]:
    """Node ranges of each R-tree level, leaves first, as stored root-first on disk.

    Mirrors the reference ``PackedRTree::generateLevelBounds``: the parent loop runs
    at least once, so even a single feature gets a root node above its leaf.
    """
    sizes = [num_items]
    n = num_items
    while True:
        n = math.ceil(n / node_size)
        sizes.append(n)
        if n == 1:
            break
    total = sum(sizes)
    bounds = []
    for size in sizes:
        total -= size
        bounds.append((total, total + size))
    return bounds


def _packed_rtree(leaves: list[tuple[float, float, float, float, int]], node_size: int) -> bytes:
    """Serialise a packed Hilbert R-tree whose leaves are already in Hilbert order."""
    levels = _level_bounds(len(leaves), node_size)
    nodes: list[tuple[float, float, float, float, int]] = [(0.0, 0.0, 0.0, 0.0, 0)] * levels[0][1]
    start = levels[0][0]
    for i, leaf in enumerate(leaves):
        nodes[start + i] = leaf
    for (pos, end), (parent_pos, _) in zip(levels, levels[1:]):
        while pos < end:
            first = pos
            min_x = min_y = math.inf
            max_x = max_y = -math.inf
            for _ in range(node_size):
                if pos >= end:
                    break
                n_min_x, n_min_y, n_max_x, n_max_y, _offset = nodes[pos]
                min_x, min_y = min(min_x, n_min_x), min(min_y, n_min_y)
                max_x, max_y = max(max_x, n_max_x), max(max_y, n_max_y)
                pos += 1
            nodes[parent_pos] = (min_x, min_y, max_x, max_y, first)
            parent_pos += 1
    return b"".join(_NODE_ITEM.pack(*node) for node in nodes)


def _encode_properties(feature: Feature, columns: list[tuple[str, str]]) -> bytes:
    """Encode non-null attribute values as FlatGeobuf (column index, value) pairs."""
    out = bytearray()
    for index, (name, kind) in enumerate(columns):
        value = feature.properties.get(name)
        if value is None:
            continue
        out.extend(struct.pack("<H", index))
        if kind == BOOL:
            out.extend(struct.pack("<B", 1 if value else 0))
        elif kind == INT:
            out.extend(struct.pack("<q", value))
        elif kind == FLOAT:
            out.extend(struct.pack("<d", value))
        else:
            data = str(value).encode("utf-8")
            out.extend(struct.pack("<I", len(data)) + data)
    return bytes(out)


def _encode_feature(feature: Feature, columns: list[tuple[str, str]], has_z: bool) -> bytes:
    """Encode one feature as a size-prefixed FlatBuffers ``Feature`` table."""
    vertices = feature.vertices()
    geometry: dict[int, tuple[str, Any]] = {
        1: ("vec:f64", [c for pt in vertices for c in pt[:2]]),
        6: ("u8", _GEOMETRY_CODES[feature.geometry_type]),
    }
    if has_z:
        geometry[2] = ("vec:f64", [pt[2] for pt in vertices])
    if feature.geometry_type == "Polygon" and len(feature.coordinates) > 1:
        ends, total = [], 0
        for ring in feature.coordinates:
            total += len(ring)
            ends.append(total)
        geometry[0] = ("vec:u32", ends)
    fields: dict[int, tuple[str, Any]] = {0: ("table", Table(geometry))}
    properties = _encode_properties(feature, columns)
    if properties:
        fields[1] = ("bytes", properties)
    body = encode(Table(fields))
    return struct.pack("<I", len(body)) + body


def export_entities_to_flatgeobuf(
    entities: Sequence[NetcadEntity],
    output_path: str | Path,
    srid: Optional[int] = 4326,
    *,
    plan_type: str = "UIP",
    index_node_size: int = DEFAULT_INDEX_NODE_SIZE,
) -> FlatGeobufExportResult:
    """Export Netcad entities to a spec-conformant FlatGeobuf file.

    Attributes are the same PlanGML/e-Plan properties as :func:`write_geojson`.
    ``srid`` is written as an EPSG code (``None`` or ``0`` writes no CRS).
    ``index_node_size`` is 16 (write a packed Hilbert R-tree and store features
    in Hilbert order) or 0 (no index). Other fan-outs are valid in the spec but
    GDAL/QGIS size the index as if it were 16 and then fail to read the file.
    """
    if index_node_size not in (0, DEFAULT_INDEX_NODE_SIZE):
        raise ValueError(
            f"index_node_size must be {DEFAULT_INDEX_NODE_SIZE} or 0, got {index_node_size}"
        )
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    table = build_feature_table(entities, plan_type=plan_type)
    features = table.features
    min_x, min_y, max_x, max_y = table.bbox or (0.0, 0.0, 0.0, 0.0)

    use_index = index_node_size > 0 and len(features) > 0
    if use_index:
        width = max(max_x - min_x, 1e-12)
        height = max(max_y - min_y, 1e-12)
        scale = (1 << 16) - 1

        def hilbert_key(feature: Feature) -> int:
            """Hilbert index of the feature's bounding-box centre within the extent."""
            f_min_x, f_min_y, f_max_x, f_max_y = _feature_bbox(feature)
            cx = int(scale * ((f_min_x + f_max_x) / 2 - min_x) / width)
            cy = int(scale * ((f_min_y + f_max_y) / 2 - min_y) / height)
            return _hilbert(cx, cy)

        features = sorted(features, key=hilbert_key)

    single_type = len(table.geometry_types) == 1
    header_fields: dict[int, tuple[str, Any]] = {
        0: ("str", out.stem),
        2: ("u8", _GEOMETRY_CODES[table.geometry_types[0]] if single_type else 0),
        8: ("u64", len(features)),
        9: ("u16", index_node_size if use_index else 0),
    }
    if table.bbox is not None:
        header_fields[1] = ("vec:f64", [min_x, min_y, max_x, max_y])
    if table.has_z:
        header_fields[3] = ("bool", 1)
    if table.columns:
        header_fields[7] = (
            "tables",
            [
                Table({0: ("str", name), 1: ("u8", _COLUMN_CODES.get(kind, _STRING_CODE))})
                for name, kind in table.columns
            ],
        )
    if srid:
        header_fields[10] = ("table", Table({0: ("str", "EPSG"), 1: ("i32", int(srid))}))
    header = encode(Table(header_fields))

    encoded = [_encode_feature(feature, table.columns, table.has_z) for feature in features]

    with open(out, "wb") as handle:
        handle.write(FGB_MAGIC)
        handle.write(struct.pack("<I", len(header)))
        handle.write(header)
        if use_index:
            leaves, offset = [], 0
            for feature, blob in zip(features, encoded):
                leaves.append((*_feature_bbox(feature), offset))
                offset += len(blob)
            handle.write(_packed_rtree(leaves, index_node_size))
        for blob in encoded:
            handle.write(blob)

    return FlatGeobufExportResult(
        feature_count=len(features),
        file_size_bytes=out.stat().st_size,
        bounding_box_min_x=min_x,
        bounding_box_min_y=min_y,
        bounding_box_max_x=max_x,
        bounding_box_max_y=max_y,
        output_path=str(out),
    )
