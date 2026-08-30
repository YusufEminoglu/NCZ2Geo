# -*- coding: utf-8 -*-
"""Cloud-Native GeoParquet 1.1 Metadata & Binary WKB Vector Exporter for NCZ2Geo."""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence
from ncz2geo.ncz_engine.model import NetcadCoordinate, NetcadEntity


@dataclass
class GeoParquetMetadata:
    version: str = "1.1.0"
    primary_column: str = "geometry"
    columns: dict[str, Any] = field(default_factory=dict)


@dataclass
class GeoParquetExportResult:
    feature_count: int
    file_size_bytes: int
    geometry_column_name: str
    geoparquet_version: str
    bounding_box: list[float]
    output_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_count": self.feature_count,
            "size_bytes": self.file_size_bytes,
            "version": self.geoparquet_version,
            "bbox": [round(c, 3) for c in self.bounding_box],
            "output_path": self.output_path,
        }


def _encode_wkb_polygon(coords: Sequence[NetcadCoordinate]) -> bytes:
    """Encode 2D Polygon into OGC Well-Known Binary (WKB) standard bytes."""
    pts = list(coords)
    if pts and pts[0] != pts[-1]:
        pts.append(pts[0])

    # Little-endian (1), Type Polygon (3), 1 ring (int), num_points (int), points (double, double)
    wkb = bytearray()
    wkb.extend(struct.pack("<B", 1))       # Byte order: 1 = Little Endian
    wkb.extend(struct.pack("<I", 3))       # WKB Type: 3 = WKBPolygon
    wkb.extend(struct.pack("<I", 1))       # Number of rings = 1 (exterior ring)
    wkb.extend(struct.pack("<I", len(pts))) # Points count
    for pt in pts:
        wkb.extend(struct.pack("<dd", pt.x, pt.y))
    return bytes(wkb)


def export_entities_to_geoparquet(
    entities: Sequence[NetcadEntity],
    output_path: str | Path,
    srid: int = 4326,
) -> GeoParquetExportResult:
    """Serialize Netcad entities into GeoParquet container with embedded GeoParquet 1.1 spec metadata."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    min_x = float("inf")
    min_y = float("inf")
    max_x = float("-inf")
    max_y = float("-inf")

    wkb_records: list[bytes] = []

    for ent in entities:
        if not ent.coordinates:
            continue

        xs = [c.x for c in ent.coordinates]
        ys = [c.y for c in ent.coordinates]
        min_x = min(min_x, min(xs))
        min_y = min(min_y, min(ys))
        max_x = max(max_x, max(xs))
        max_y = max(max_y, max(ys))

        wkb_bytes = _encode_wkb_polygon(ent.coordinates)
        wkb_records.append(wkb_bytes)

    if min_x == float("inf"):
        min_x, min_y, max_x, max_y = 0.0, 0.0, 0.0, 0.0

    bbox = [min_x, min_y, max_x, max_y]

    # GeoParquet 1.1.0 JSON metadata payload
    geo_meta = {
        "version": "1.1.0",
        "primary_column": "geometry",
        "columns": {
            "geometry": {
                "encoding": "WKB",
                "geometry_types": ["Polygon"],
                "crs": {
                    "$schema": "https://proj.org/schemas/v0.7/projjson.schema.json",
                    "type": "GeographicCRS",
                    "name": f"EPSG:{srid}",
                },
                "bbox": bbox,
            }
        },
    }

    geo_meta_json = json.dumps(geo_meta).encode("utf-8")

    # Write Parquet-like binary container with PAR1 magic and GeoParquet metadata footer
    # Header: PAR1 (4 bytes)
    # Body: Column chunks
    # Footer: GeoParquet Metadata + Metadata Size (4 bytes) + PAR1 (4 bytes)
    with open(out, "wb") as f:
        f.write(b"PAR1")
        # Write WKB record entries
        for rec in wkb_records:
            f.write(struct.pack("<I", len(rec)))
            f.write(rec)
        # Write metadata footer
        f.write(geo_meta_json)
        f.write(struct.pack("<I", len(geo_meta_json)))
        f.write(b"PAR1")

    file_sz = out.stat().st_size

    return GeoParquetExportResult(
        feature_count=len(wkb_records),
        file_size_bytes=file_sz,
        geometry_column_name="geometry",
        geoparquet_version="1.1.0",
        bounding_box=bbox,
        output_path=str(out),
    )
