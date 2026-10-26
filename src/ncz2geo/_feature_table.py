# -*- coding: utf-8 -*-
"""Shared feature table behind the binary vector exporters.

Every exporter (FlatGeobuf, GeoParquet, Shapefile, DXF) starts from the same
PlanGML-aware GeoJSON FeatureCollection that :func:`write_geojson` produces, so
all formats carry identical geometry and attributes. This module turns that
collection into a typed table: an ordered column schema, simple geometries and
an overall bounding box, plus an OGC WKB encoder.
"""

from __future__ import annotations

import json
import math
import struct
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from .geojson import entities_to_feature_collection
from .ncz_engine.model import NetcadEntity

# Column kinds shared by every writer.
INT = "int"
FLOAT = "float"
BOOL = "bool"
STRING = "string"

GEOMETRY_TYPES = ("Point", "LineString", "Polygon")


@dataclass
class Feature:
    """One feature: a GeoJSON geometry type, its vertices and attribute values."""

    geometry_type: str  # "Point", "LineString" or "Polygon"
    # Point: [(x, y, z)]; LineString: vertices; Polygon: rings (exterior first).
    coordinates: list[Any]
    properties: dict[str, Any]

    def vertices(self) -> list[tuple[float, float, float]]:
        """Return every vertex of the geometry as ``(x, y, z)``."""
        if self.geometry_type == "Polygon":
            return [pt for ring in self.coordinates for pt in ring]
        return list(self.coordinates)


@dataclass
class FeatureTable:
    """Typed, column-ordered view of an exported FeatureCollection."""

    features: list[Feature]
    columns: list[tuple[str, str]]  # (name, kind) in first-seen order
    has_z: bool
    bbox: Optional[tuple[float, float, float, float]]
    geometry_types: list[str] = field(default_factory=list)


def _point(raw: Any) -> tuple[float, float, float]:
    """Normalise a GeoJSON position to a float ``(x, y, z)`` triple."""
    x, y = float(raw[0]), float(raw[1])
    z = float(raw[2]) if len(raw) > 2 and raw[2] is not None else 0.0
    return x, y, z if math.isfinite(z) else 0.0


def _value_kind(value: Any) -> str:
    """Return the column kind a single non-null value needs."""
    if isinstance(value, bool):
        return BOOL
    if isinstance(value, int):
        return INT
    if isinstance(value, float):
        return FLOAT
    return STRING


def _merge_kind(current: Optional[str], new: str) -> str:
    """Widen a column kind so it can hold both ``current`` and ``new`` values."""
    if current is None or current == new:
        return new
    if {current, new} == {INT, FLOAT}:
        return FLOAT
    return STRING


def coerce(value: Any, kind: str) -> Any:
    """Convert a property value to the Python type of its column (None stays None)."""
    if value is None:
        return None
    if kind == BOOL:
        return bool(value)
    if kind == INT:
        return int(value)
    if kind == FLOAT:
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def build_feature_table(
    entities: Iterable[NetcadEntity], *, plan_type: str = "UIP"
) -> FeatureTable:
    """Convert entities into a :class:`FeatureTable` via the GeoJSON exporter."""
    collection = entities_to_feature_collection(entities, plan_type=plan_type)
    features: list[Feature] = []
    kinds: dict[str, Optional[str]] = {}
    min_x = min_y = math.inf
    max_x = max_y = -math.inf
    has_z = False
    seen_types: list[str] = []

    for raw in collection["features"]:
        geometry = raw["geometry"]
        gtype = geometry["type"]
        if gtype == "Point":
            coords: list[Any] = [_point(geometry["coordinates"])]
        elif gtype == "LineString":
            coords = [_point(p) for p in geometry["coordinates"]]
        elif gtype == "Polygon":
            coords = [[_point(p) for p in ring] for ring in geometry["coordinates"]]
        else:  # pragma: no cover - entities_to_feature_collection emits only the three above
            continue
        feature = Feature(gtype, coords, dict(raw["properties"]))
        vertices = feature.vertices()
        if not vertices:
            continue
        for x, y, z in vertices:
            min_x, min_y = min(min_x, x), min(min_y, y)
            max_x, max_y = max(max_x, x), max(max_y, y)
            has_z = has_z or z != 0.0
        for key, value in feature.properties.items():
            if key not in kinds:
                kinds[key] = None
            if value is not None:
                kinds[key] = _merge_kind(kinds[key], _value_kind(value))
        if gtype not in seen_types:
            seen_types.append(gtype)
        features.append(feature)

    columns = [(name, kind or STRING) for name, kind in kinds.items()]
    for feature in features:
        feature.properties = {
            name: coerce(feature.properties.get(name), kind) for name, kind in columns
        }
    bbox = (min_x, min_y, max_x, max_y) if features else None
    return FeatureTable(features, columns, has_z, bbox, seen_types)


def ring_signed_area(ring: list[tuple[float, float, float]]) -> float:
    """Shoelace signed area of a ring (positive when counter-clockwise)."""
    area = 0.0
    for (x1, y1, _), (x2, y2, _) in zip(ring, ring[1:]):
        area += x1 * y2 - x2 * y1
    return area / 2.0


def to_wkb(feature: Feature, has_z: bool) -> bytes:
    """Encode a feature geometry as little-endian ISO WKB (Z types use the +1000 codes)."""
    base = {"Point": 1, "LineString": 2, "Polygon": 3}[feature.geometry_type]
    out = bytearray(struct.pack("<BI", 1, base + (1000 if has_z else 0)))
    fmt = "<ddd" if has_z else "<dd"

    def put(pt: tuple[float, float, float]) -> None:
        out.extend(struct.pack(fmt, *(pt if has_z else pt[:2])))

    if feature.geometry_type == "Point":
        put(feature.coordinates[0])
    elif feature.geometry_type == "LineString":
        out.extend(struct.pack("<I", len(feature.coordinates)))
        for pt in feature.coordinates:
            put(pt)
    else:
        out.extend(struct.pack("<I", len(feature.coordinates)))
        for ring in feature.coordinates:
            out.extend(struct.pack("<I", len(ring)))
            for pt in ring:
                put(pt)
    return bytes(out)
