# -*- coding: utf-8 -*-
"""Cloud-Native FlatGeobuf (.fgb) Binary Vector Exporter for NCZ2Geo."""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence
from ncz2geo.ncz_engine.model import NetcadCoordinate, NetcadEntity


# FlatGeobuf magic bytes: 'fgb' + 0x03 + 'fgb' + 0x00
FGB_MAGIC = b"\x66\x67\x62\x03\x66\x67\x62\x00"


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


def export_entities_to_flatgeobuf(
    entities: Sequence[NetcadEntity],
    output_path: str | Path,
    srid: int = 4326,
) -> FlatGeobufExportResult:
    """Export Netcad entities into FlatGeobuf binary format with bounding box index headers."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    min_x = float("inf")
    min_y = float("inf")
    max_x = float("-inf")
    max_y = float("-inf")

    feature_records: list[bytes] = []

    for ent in entities:
        if not ent.coordinates:
            continue

        xs = [c.x for c in ent.coordinates]
        ys = [c.y for c in ent.coordinates]

        min_x = min(min_x, min(xs))
        min_y = min(min_y, min(ys))
        max_x = max(max_x, max(xs))
        max_y = max(max_y, max(ys))

        # Binary feature representation:
        # [4 bytes length][4 bytes geom_type][4 bytes point_count][(x,y) doubles...]
        # Geom type: 1 = Point, 2 = LineString, 3 = Polygon
        g_type = 3 if ent.geometry_kind == "POLYGON" or ent.is_closed else 2
        if len(ent.coordinates) == 1:
            g_type = 1

        geom_bytes = bytearray()
        geom_bytes.extend(struct.pack("<I", g_type))
        geom_bytes.extend(struct.pack("<I", len(ent.coordinates)))
        for c in ent.coordinates:
            geom_bytes.extend(struct.pack("<dd", c.x, c.y))

        # Attribute text (layer name)
        layer_encoded = ent.layer_name.encode("utf-8")
        attr_bytes = struct.pack("<I", len(layer_encoded)) + layer_encoded

        record_payload = geom_bytes + attr_bytes
        record_header = struct.pack("<I", len(record_payload))
        feature_records.append(record_header + record_payload)

    if min_x == float("inf"):
        min_x, min_y, max_x, max_y = 0.0, 0.0, 0.0, 0.0

    # Header block: magic (8 bytes) + header_size (4 bytes) + bbox (32 bytes) + feature_count (4 bytes) + srid (4 bytes)
    header_payload = bytearray()
    header_payload.extend(struct.pack("<dddd", min_x, min_y, max_x, max_y))
    header_payload.extend(struct.pack("<II", len(feature_records), srid))

    header_block = FGB_MAGIC + struct.pack("<I", len(header_payload)) + header_payload

    with open(out, "wb") as f:
        f.write(header_block)
        for rec in feature_records:
            f.write(rec)

    file_sz = out.stat().st_size

    return FlatGeobufExportResult(
        feature_count=len(feature_records),
        file_size_bytes=file_sz,
        bounding_box_min_x=min_x,
        bounding_box_min_y=min_y,
        bounding_box_max_x=max_x,
        bounding_box_max_y=max_y,
        output_path=str(out),
    )
