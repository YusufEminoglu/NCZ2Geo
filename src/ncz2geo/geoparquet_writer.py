# -*- coding: utf-8 -*-
"""Cloud-Native GeoParquet 1.1 Exporter for NCZ2Geo.

Writes a real Apache Parquet file (pure Python, no pyarrow) with a WKB
``geometry`` column, one typed column per PlanGML/e-Plan attribute and the
GeoParquet 1.1 ``geo`` file metadata. The result opens in GeoPandas, DuckDB,
GDAL/OGR, QGIS and any Arrow-based reader.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence

from ncz2geo._crs import projjson
from ncz2geo._feature_table import BOOL, FLOAT, INT, build_feature_table, to_wkb
from ncz2geo._parquet import BOOLEAN, BYTE_ARRAY, DOUBLE, INT64, Column, write_parquet
from ncz2geo.ncz_engine.model import NetcadEntity

_PHYSICAL = {BOOL: BOOLEAN, INT: INT64, FLOAT: DOUBLE}


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
        """Return the GeoParquet export result as a JSON-serializable dictionary."""
        return {
            "feature_count": self.feature_count,
            "size_bytes": self.file_size_bytes,
            "version": self.geoparquet_version,
            "bbox": [round(c, 3) for c in self.bounding_box],
            "output_path": self.output_path,
        }


def _crs_entry(srid: Optional[int], crs: Optional[dict[str, Any]]) -> tuple[bool, Any]:
    """Return ``(include, value)`` for the GeoParquet ``crs`` member.

    GeoParquet requires full PROJJSON; an absent ``crs`` means OGC:CRS84
    (lon/lat), so EPSG:4326 data in lon/lat order is written without ``crs``.
    Bundled EPSG codes (see :func:`ncz2geo._crs.supported_epsg_codes`) get their
    PROJJSON; any other code is written as ``null`` (unknown) rather than as an
    invalid partial definition. ``crs`` overrides all of this.
    """
    if crs is not None:
        return True, crs
    if srid and int(srid) == 4326:
        return False, None
    return True, projjson(srid)


def export_entities_to_geoparquet(
    entities: Sequence[NetcadEntity],
    output_path: str | Path,
    srid: Optional[int] = 4326,
    *,
    plan_type: str = "UIP",
    crs: Optional[dict[str, Any]] = None,
) -> GeoParquetExportResult:
    """Export Netcad entities to a GeoParquet 1.1 file.

    Attributes are the same PlanGML/e-Plan properties as :func:`write_geojson`;
    geometries are ISO WKB (with Z when any vertex has an elevation). ``srid`` is
    the EPSG code of the coordinates (``None`` marks the CRS unknown); pass
    ``crs`` to embed a full PROJJSON definition instead.
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    table = build_feature_table(entities, plan_type=plan_type)

    columns = [
        Column(
            "geometry",
            BYTE_ARRAY,
            [to_wkb(f, table.has_z) for f in table.features],
            nullable=False,
        )
    ]
    for name, kind in table.columns:
        columns.append(
            Column(
                name,
                _PHYSICAL.get(kind, BYTE_ARRAY),
                [f.properties[name] for f in table.features],
                utf8=kind not in _PHYSICAL,
            )
        )

    bbox = list(table.bbox) if table.bbox else [0.0, 0.0, 0.0, 0.0]
    suffix = " Z" if table.has_z else ""
    geometry_meta: dict[str, Any] = {
        "encoding": "WKB",
        "geometry_types": [g + suffix for g in table.geometry_types],
    }
    if table.bbox:
        geometry_meta["bbox"] = bbox
    include_crs, crs_value = _crs_entry(srid, crs)
    if include_crs:
        geometry_meta["crs"] = crs_value
    meta = GeoParquetMetadata(columns={"geometry": geometry_meta})
    geo = {"version": meta.version, "primary_column": meta.primary_column, "columns": meta.columns}

    write_parquet(str(out), columns, {"geo": json.dumps(geo, ensure_ascii=False)})

    return GeoParquetExportResult(
        feature_count=len(table.features),
        file_size_bytes=out.stat().st_size,
        geometry_column_name="geometry",
        geoparquet_version=meta.version,
        bounding_box=bbox,
        output_path=str(out),
    )
