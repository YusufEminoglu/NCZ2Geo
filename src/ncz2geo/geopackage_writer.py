# -*- coding: utf-8 -*-
"""OGC GeoPackage (GPKG) SQLite Vector & Spatial Metadata Exporter for NCZ2Geo."""

from __future__ import annotations

import sqlite3
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence
from .ncz_engine.model import NetcadEntity


@dataclass
class GeoPackageExportResult:
    output_path: str
    total_features_written: int
    table_name: str
    srs_id: int
    file_size_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "output_path": self.output_path,
            "total_features": self.total_features_written,
            "table_name": self.table_name,
            "srs_id": self.srs_id,
            "file_size_bytes": self.file_size_bytes,
        }


def _create_gpkg_geometry_blob(coordinates: Sequence[tuple[float, float]], srs_id: int = 4326) -> bytes:
    """Encode 2D Polygon WKB into standard OGC GeoPackage Binary Header format (GPKG 1.2)."""
    # GPKG Header: Magic 'GP' (0x47, 0x50), Version 0, Flags (byte order little endian = 1, empty = 0), SRS ID (uint32)
    magic = b"GP"
    version = 0
    flags = 0x01  # Little endian, no envelope
    header = magic + struct.pack("<BB", version, flags) + struct.pack("<i", srs_id)

    # Standard WKB Polygon
    # Byte order 1 (Little endian)
    # Type 3 (wkbPolygon)
    # Num rings (1)
    # Num points (N)
    pts = list(coordinates)
    if pts and pts[0] != pts[-1]:
        pts.append(pts[0])

    wkb_byte_order = struct.pack("<B", 1)
    wkb_type = struct.pack("<I", 3)
    wkb_num_rings = struct.pack("<I", 1)
    wkb_num_points = struct.pack("<I", len(pts))

    pts_bytes = b""
    for x, y in pts:
        pts_bytes += struct.pack("<dd", float(x), float(y))

    wkb = wkb_byte_order + wkb_type + wkb_num_rings + wkb_num_points + pts_bytes
    return header + wkb


def export_entities_to_geopackage(
    entities: Iterable[NetcadEntity],
    output_gpkg_path: str | Path,
    table_name: str = "cadastral_parcels",
    srs_id: int = 5254,
) -> GeoPackageExportResult:
    """Export Netcad entities to a valid standalone OGC GeoPackage (.gpkg) SQLite database."""
    out = Path(output_gpkg_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    conn = sqlite3.connect(str(out))
    cursor = conn.cursor()

    # Create OGC GeoPackage system tables
    cursor.executescript("""
        CREATE TABLE gpkg_spatial_ref_sys (
            srs_name TEXT NOT NULL,
            srs_id INTEGER NOT NULL PRIMARY KEY,
            organization TEXT NOT NULL,
            organization_coordsys_id INTEGER NOT NULL,
            definition TEXT NOT NULL,
            description TEXT
        );
        CREATE TABLE gpkg_contents (
            table_name TEXT NOT NULL PRIMARY KEY,
            data_type TEXT NOT NULL,
            identifier TEXT UNIQUE,
            description TEXT DEFAULT '',
            last_change DATETIME NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
            min_x DOUBLE,
            min_y DOUBLE,
            max_x DOUBLE,
            max_y DOUBLE,
            srs_id INTEGER,
            CONSTRAINT fk_gc_r_srs_id FOREIGN KEY (srs_id) REFERENCES gpkg_spatial_ref_sys(srs_id)
        );
        CREATE TABLE gpkg_geometry_columns (
            table_name TEXT NOT NULL,
            column_name TEXT NOT NULL,
            geometry_type_name TEXT NOT NULL,
            srs_id INTEGER NOT NULL,
            z TINYINT NOT NULL,
            m TINYINT NOT NULL,
            CONSTRAINT pk_geom_cols PRIMARY KEY (table_name, column_name),
            CONSTRAINT fk_gc_tn FOREIGN KEY (table_name) REFERENCES gpkg_contents(table_name),
            CONSTRAINT fk_gc_srs FOREIGN KEY (srs_id) REFERENCES gpkg_spatial_ref_sys(srs_id)
        );
    """)

    # Insert SRS
    cursor.execute(
        "INSERT INTO gpkg_spatial_ref_sys VALUES (?, ?, ?, ?, ?, ?)",
        ("EPSG_CUSTOM", srs_id, "EPSG", srs_id, "PROJCS[...]", "Cadastral Local Grid"),
    )

    # Create feature table
    cursor.execute(f"""
        CREATE TABLE {table_name} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            geom BLOB,
            layer_name TEXT,
            layer_code INTEGER,
            area_m2 DOUBLE
        );
    """)

    # Register in metadata
    cursor.execute(
        "INSERT INTO gpkg_contents (table_name, data_type, identifier, srs_id) VALUES (?, ?, ?, ?)",
        (table_name, "features", table_name, srs_id),
    )
    cursor.execute(
        "INSERT INTO gpkg_geometry_columns VALUES (?, ?, ?, ?, ?, ?)",
        (table_name, "geom", "POLYGON", srs_id, 0, 0),
    )

    count = 0
    for e in entities:
        if not e.coordinates:
            continue
        coords = [(pt.x, pt.y) for pt in e.coordinates]
        geom_blob = _create_gpkg_geometry_blob(coords, srs_id=srs_id)
        area = 0.0
        for j in range(len(coords) - 1):
            area += coords[j][0] * coords[j + 1][1] - coords[j + 1][0] * coords[j][1]
        area = abs(area) * 0.5

        cursor.execute(
            f"INSERT INTO {table_name} (geom, layer_name, layer_code, area_m2) VALUES (?, ?, ?, ?)",
            (geom_blob, e.layer_name, e.layer_code, area),
        )
        count += 1

    conn.commit()
    conn.close()

    return GeoPackageExportResult(
        output_path=str(out),
        total_features_written=count,
        table_name=table_name,
        srs_id=srs_id,
        file_size_bytes=out.stat().st_size if out.exists() else 0,
    )
