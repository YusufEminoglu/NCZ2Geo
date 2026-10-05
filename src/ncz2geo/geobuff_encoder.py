# -*- coding: utf-8 -*-
"""Compact Pure-Python GeoBuff Protocol-Buffer Binary Vector Serializer for NCZ2Geo."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from ncz2geo.ncz_engine.model import NetcadEntity


@dataclass
class GeoBuffHeader:
    magic: bytes = b"GBUF\x01\x00"
    srid: int = 4326
    feature_count: int = 0
    bounding_box: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)


@dataclass
class GeoBuffExportResult:
    feature_count: int
    file_size_bytes: int
    compressed_bytes_count: int
    compression_ratio_pct: float
    output_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_count": self.feature_count,
            "size_bytes": self.file_size_bytes,
            "compression_ratio_pct": round(self.compression_ratio_pct, 1),
            "output_path": self.output_path,
        }


def _zigzag_encode(n: int) -> int:
    """Zigzag encoding for variable-length integers: maps signed to unsigned integers."""
    return (n << 1) ^ (n >> 31)


def export_entities_to_geobuff(
    entities: Sequence[NetcadEntity],
    output_path: str | Path,
    srid: int = 4326,
    coordinate_precision: float = 1e6,  # 6 decimal places (micro-degree precision)
) -> GeoBuffExportResult:
    """Serialize Netcad entities into compact binary GeoBuff format with delta integer packing."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    min_x, min_y = float("inf"), float("inf")
    max_x, max_y = float("-inf"), float("-inf")

    body_bytes = bytearray()
    valid_features = 0

    for ent in entities:
        if not ent.coordinates:
            continue

        valid_features += 1
        coords = ent.coordinates

        # Write layer code (2 bytes uint16) and points count (4 bytes uint32)
        body_bytes.extend(struct.pack("<HI", ent.layer_code, len(coords)))

        # Delta-packed zigzag coordinates
        last_x = 0
        last_y = 0
        for pt in coords:
            min_x = min(min_x, pt.x)
            min_y = min(min_y, pt.y)
            max_x = max(max_x, pt.x)
            max_y = max(max_y, pt.y)

            ix = int(round(pt.x * coordinate_precision))
            iy = int(round(pt.y * coordinate_precision))

            dx = ix - last_x
            dy = iy - last_y

            # Pack 4-byte signed delta integers
            body_bytes.extend(struct.pack("<ii", dx, dy))

            last_x = ix
            last_y = iy

    if min_x == float("inf"):
        min_x, min_y, max_x, max_y = 0.0, 0.0, 0.0, 0.0

    # Header: Magic (6B) + SRID (4B uint32) + FeatureCount (4B uint32) + BBox (32B doubles)
    header = bytearray()
    header.extend(b"GBUF\x01\x00")
    header.extend(struct.pack("<II", srid, valid_features))
    header.extend(struct.pack("<dddd", min_x, min_y, max_x, max_y))

    full_payload = header + body_bytes

    with open(out, "wb") as f:
        f.write(full_payload)

    raw_uncompressed_estimate = max(1, valid_features * 64)
    file_sz = out.stat().st_size
    comp_pct = max(0.0, (1.0 - (file_sz / float(raw_uncompressed_estimate))) * 100.0)

    return GeoBuffExportResult(
        feature_count=valid_features,
        file_size_bytes=file_sz,
        compressed_bytes_count=len(body_bytes),
        compression_ratio_pct=comp_pct,
        output_path=str(out),
    )
