# -*- coding: utf-8 -*-
"""OGC GeoPackage 1.2 (GPKG) exporter for NCZ2Geo.

Writes a standards-conformant GeoPackage with Python's built-in ``sqlite3``:
the required system tables and SRS rows, a feature table holding every
geometry type (points, lines and polygons, with Z when the drawing has
elevations) plus all PlanGML/e-Plan attributes, and a ``gpkg_rtree_index``
spatial index with the standard maintenance triggers. The file passes GDAL's
``validate_gpkg.py`` and opens directly in QGIS, ArcGIS Pro and GDAL/OGR.
"""

from __future__ import annotations

import sqlite3
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

from ._crs import crs_name, ogc_wkt
from ._feature_table import BOOL, FLOAT, INT, Feature, build_feature_table, ring_signed_area, to_wkb
from .ncz_engine.model import NetcadEntity

_APPLICATION_ID = 0x47504B47  # "GPKG"
_USER_VERSION = 10200  # GeoPackage 1.2
_SQL_TYPES = {BOOL: "BOOLEAN", INT: "INTEGER", FLOAT: "DOUBLE"}
_WGS84_WKT = (
    'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,'
    'AUTHORITY["EPSG","7030"]],AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0,'
    'AUTHORITY["EPSG","8901"]],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],'
    'AXIS["Latitude",NORTH],AXIS["Longitude",EAST],AUTHORITY["EPSG","4326"]]'
)


@dataclass
class GeoPackageExportResult:
    output_path: str
    total_features_written: int
    table_name: str
    srs_id: int
    file_size_bytes: int

    def to_dict(self) -> dict[str, Any]:
        """Return the GeoPackage export result as a JSON-serializable dictionary."""
        return {
            "output_path": self.output_path,
            "total_features": self.total_features_written,
            "table_name": self.table_name,
            "srs_id": self.srs_id,
            "file_size_bytes": self.file_size_bytes,
        }


def _quote(identifier: str) -> str:
    """Quote an SQL identifier."""
    return '"' + identifier.replace('"', '""') + '"'


def _gpkg_blob(feature: Feature, srs_id: int, has_z: bool) -> bytes:
    """Encode a GeoPackage geometry blob: GP header (with XY envelope) + ISO WKB."""
    if feature.geometry_type == "Point":
        header = b"GP" + struct.pack("<BBi", 0, 0x01, srs_id)  # little endian, no envelope
    else:
        vertices = feature.vertices()
        xs = [p[0] for p in vertices]
        ys = [p[1] for p in vertices]
        header = b"GP" + struct.pack("<BBi4d", 0, 0x03, srs_id, min(xs), max(xs), min(ys), max(ys))
    return header + to_wkb(feature, has_z)


def _rtree_triggers(table: str, geom: str, fid: str) -> list[str]:
    """SQL for the GeoPackage 1.2 ``gpkg_rtree_index`` maintenance triggers."""
    t, c, i = _quote(table), _quote(geom), _quote(fid)
    rt_name = f"rtree_{table}_{geom}"
    rt = _quote(rt_name)
    values = f"NEW.{i}, ST_MinX(NEW.{c}), ST_MaxX(NEW.{c}), ST_MinY(NEW.{c}), ST_MaxY(NEW.{c})"

    def name(suffix: str) -> str:
        return _quote(f"{rt_name}_{suffix}")

    return [
        f"CREATE TRIGGER {name('insert')} AFTER INSERT ON {t} "
        f"WHEN (new.{c} NOT NULL AND NOT ST_IsEmpty(NEW.{c})) "
        f"BEGIN INSERT OR REPLACE INTO {rt} VALUES ({values}); END",
        f"CREATE TRIGGER {name('update1')} AFTER UPDATE OF {c} ON {t} "
        f"WHEN OLD.{i} = NEW.{i} AND (NEW.{c} NOTNULL AND NOT ST_IsEmpty(NEW.{c})) "
        f"BEGIN INSERT OR REPLACE INTO {rt} VALUES ({values}); END",
        f"CREATE TRIGGER {name('update2')} AFTER UPDATE OF {c} ON {t} "
        f"WHEN OLD.{i} = NEW.{i} AND (NEW.{c} ISNULL OR ST_IsEmpty(NEW.{c})) "
        f"BEGIN DELETE FROM {rt} WHERE id = OLD.{i}; END",
        f"CREATE TRIGGER {name('update3')} AFTER UPDATE ON {t} "
        f"WHEN OLD.{i} != NEW.{i} AND (NEW.{c} NOTNULL AND NOT ST_IsEmpty(NEW.{c})) "
        f"BEGIN DELETE FROM {rt} WHERE id = OLD.{i}; INSERT OR REPLACE INTO {rt} VALUES ({values}); END",
        f"CREATE TRIGGER {name('update4')} AFTER UPDATE ON {t} "
        f"WHEN OLD.{i} != NEW.{i} AND (NEW.{c} ISNULL OR ST_IsEmpty(NEW.{c})) "
        f"BEGIN DELETE FROM {rt} WHERE id IN (OLD.{i}, NEW.{i}); END",
        f"CREATE TRIGGER {name('delete')} AFTER DELETE ON {t} WHEN old.{c} NOT NULL "
        f"BEGIN DELETE FROM {rt} WHERE id = OLD.{i}; END",
    ]


def export_entities_to_geopackage(
    entities: Iterable[NetcadEntity],
    output_gpkg_path: str | Path,
    table_name: str = "cadastral_parcels",
    srs_id: Optional[int] = 5254,
    *,
    plan_type: str = "UIP",
    spatial_index: bool = True,
) -> GeoPackageExportResult:
    """Export Netcad entities to a single-table OGC GeoPackage 1.2 file.

    The table stores points, lines and polygons in one ``GEOMETRY`` column
    (``geom``) with the PlanGML/e-Plan attributes of :func:`write_geojson` and
    an ``area_m2`` column for polygons. ``srs_id`` is an EPSG code; bundled codes
    get their full WKT, others are recorded without a definition (``None``
    writes the GeoPackage "undefined cartesian" SRS -1). An existing file at
    ``output_gpkg_path`` is replaced.
    """
    out = Path(output_gpkg_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    table = build_feature_table(entities, plan_type=plan_type)
    srid = int(srs_id) if srs_id else -1
    geom, fid = "geom", "id"

    conn = sqlite3.connect(str(out))
    try:
        cur = conn.cursor()
        cur.execute(f"PRAGMA application_id = {_APPLICATION_ID}")
        cur.execute(f"PRAGMA user_version = {_USER_VERSION}")
        cur.executescript(
            """
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
                last_change DATETIME NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
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
                CONSTRAINT uk_gc_table_name UNIQUE (table_name),
                CONSTRAINT fk_gc_tn FOREIGN KEY (table_name) REFERENCES gpkg_contents(table_name),
                CONSTRAINT fk_gc_srs FOREIGN KEY (srs_id) REFERENCES gpkg_spatial_ref_sys (srs_id)
            );
            CREATE TABLE gpkg_extensions (
                table_name TEXT,
                column_name TEXT,
                extension_name TEXT NOT NULL,
                definition TEXT NOT NULL,
                scope TEXT NOT NULL,
                CONSTRAINT ge_tce UNIQUE (table_name, column_name, extension_name)
            );
            """
        )
        srs_rows: list[tuple[str, int, str, int, str, Optional[str]]] = [
            (
                "Undefined cartesian SRS",
                -1,
                "NONE",
                -1,
                "undefined",
                "undefined cartesian coordinate reference system",
            ),
            (
                "Undefined geographic SRS",
                0,
                "NONE",
                0,
                "undefined",
                "undefined geographic coordinate reference system",
            ),
            (
                "WGS 84 geodetic",
                4326,
                "EPSG",
                4326,
                _WGS84_WKT,
                "longitude/latitude coordinates in decimal degrees on the WGS 84 spheroid",
            ),
        ]
        if srid not in (-1, 0, 4326):
            srs_rows.append(
                (
                    crs_name(srid) or f"EPSG:{srid}",
                    srid,
                    "EPSG",
                    srid,
                    ogc_wkt(srid) or "undefined",
                    None,
                )
            )
        cur.executemany("INSERT INTO gpkg_spatial_ref_sys VALUES (?, ?, ?, ?, ?, ?)", srs_rows)

        column_defs = [
            f"{_quote(fid)} INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL",
            f"{_quote(geom)} GEOMETRY",
        ]
        column_defs += [
            f"{_quote(name)} {_SQL_TYPES.get(kind, 'TEXT')}" for name, kind in table.columns
        ]
        column_defs.append(f"{_quote('area_m2')} DOUBLE")
        cur.execute(f"CREATE TABLE {_quote(table_name)} ({', '.join(column_defs)})")

        bbox = table.bbox or (None, None, None, None)
        cur.execute(
            "INSERT INTO gpkg_contents (table_name, data_type, identifier, min_x, min_y, max_x, max_y, srs_id) "
            "VALUES (?, 'features', ?, ?, ?, ?, ?, ?)",
            (table_name, table_name, *bbox, srid),
        )
        cur.execute(
            "INSERT INTO gpkg_geometry_columns VALUES (?, ?, 'GEOMETRY', ?, ?, 0)",
            (table_name, geom, srid, 1 if table.has_z else 0),
        )

        names = [geom] + [name for name, _ in table.columns] + ["area_m2"]
        insert = (
            f"INSERT INTO {_quote(table_name)} ({', '.join(_quote(n) for n in names)}) "
            f"VALUES ({', '.join('?' for _ in names)})"
        )
        rows = []
        for feature in table.features:
            area = (
                abs(ring_signed_area(feature.coordinates[0]))
                if feature.geometry_type == "Polygon"
                else None
            )
            rows.append(
                [_gpkg_blob(feature, srid, table.has_z)]
                + [feature.properties[name] for name, _ in table.columns]
                + [area]
            )
        cur.executemany(insert, rows)

        if spatial_index:
            rtree = _quote(f"rtree_{table_name}_{geom}")
            cur.execute(f"CREATE VIRTUAL TABLE {rtree} USING rtree(id, minx, maxx, miny, maxy)")
            for feature, (rowid,) in zip(
                table.features,
                cur.execute(
                    f"SELECT {_quote(fid)} FROM {_quote(table_name)} ORDER BY 1"
                ).fetchall(),
            ):
                vertices = feature.vertices()
                xs = [p[0] for p in vertices]
                ys = [p[1] for p in vertices]
                conn.execute(
                    f"INSERT INTO {rtree} VALUES (?, ?, ?, ?, ?)",
                    (rowid, min(xs), max(xs), min(ys), max(ys)),
                )
            for statement in _rtree_triggers(table_name, geom, fid):
                cur.execute(statement)
            cur.execute(
                "INSERT INTO gpkg_extensions VALUES (?, ?, 'gpkg_rtree_index', "
                "'http://www.geopackage.org/spec120/#extension_rtree', 'write-only')",
                (table_name, geom),
            )
        conn.commit()
    finally:
        conn.close()

    return GeoPackageExportResult(
        output_path=str(out),
        total_features_written=len(table.features),
        table_name=table_name,
        srs_id=srid,
        file_size_bytes=out.stat().st_size,
    )
