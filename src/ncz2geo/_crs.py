# -*- coding: utf-8 -*-
"""Bundled coordinate reference system definitions for the file exporters.

``crs_definitions.json`` holds PROJJSON, OGC WKT1 and ESRI WKT for the EPSG codes Netcad
drawings in Turkey normally use (TUREF/ITRF96 and ED50 3-degree TM zones, UTM
35N-38N, WGS 84, Web Mercator). It was generated from the PROJ database with
``projinfo EPSG:<code> -o PROJJSON|WKT1_GDAL|WKT1_ESRI``, so exporters can write complete
CRS metadata without pyproj or GDAL.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib import resources
from typing import Any, Optional


@lru_cache(maxsize=1)
def _definitions() -> dict[str, dict[str, Any]]:
    """Load the bundled CRS table once."""
    text = resources.files("ncz2geo").joinpath("crs_definitions.json").read_text(encoding="utf-8")
    return json.loads(text)


def supported_epsg_codes() -> list[int]:
    """Return the EPSG codes with bundled definitions, sorted."""
    return sorted(int(code) for code in _definitions())


def projjson(srid: Optional[int]) -> Optional[dict[str, Any]]:
    """Return the PROJJSON definition of an EPSG code, or None when not bundled."""
    if not srid:
        return None
    entry = _definitions().get(str(int(srid)))
    return json.loads(json.dumps(entry["projjson"])) if entry else None


def esri_wkt(srid: Optional[int]) -> Optional[str]:
    """Return the ESRI WKT (``.prj`` text) of an EPSG code, or None when not bundled."""
    if not srid:
        return None
    entry = _definitions().get(str(int(srid)))
    return entry["esri_wkt"] if entry else None


def ogc_wkt(srid: Optional[int]) -> Optional[str]:
    """Return the OGC WKT1 definition of an EPSG code, or None when not bundled."""
    if not srid:
        return None
    entry = _definitions().get(str(int(srid)))
    return entry["ogc_wkt"] if entry else None


def crs_name(srid: Optional[int]) -> Optional[str]:
    """Return the CRS name of a bundled EPSG code (e.g. ``"TUREF / TM30"``)."""
    if not srid:
        return None
    entry = _definitions().get(str(int(srid)))
    return entry["name"] if entry else None


def parse_epsg(text: object) -> Optional[int]:
    """Extract an EPSG code from values such as ``"EPSG:5254"``, ``"5254"`` or ``5254``."""
    match = re.search(r"(\d{4,6})", str(text or ""))
    return int(match.group(1)) if match else None
