"""GeoJSON export helpers with PlanGML/e-Plan metadata."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .ncz_engine.model import NetcadEntity
from .plangml import LayerClassification, classification_properties, classify_entity


def entities_to_feature_collection(
    entities: Iterable[NetcadEntity],
    *,
    plan_type: str = "UIP",
) -> dict:
    """Convert supported Netcad entities to a PlanGML-aware GeoJSON FeatureCollection."""
    features = []
    for entity in entities:
        geometry = _entity_geometry(entity)
        if geometry is None:
            continue
        classification = classify_entity(entity, plan_type=plan_type)
        features.append(
            {
                "type": "Feature",
                "properties": _entity_properties(entity, classification),
                "geometry": geometry,
            }
        )
    return {"type": "FeatureCollection", "features": features}


def write_geojson(
    entities: Iterable[NetcadEntity],
    path: str | Path,
    *,
    plan_type: str = "UIP",
    srid: int | None = None,
) -> dict:
    """Write entities as styled GeoJSON and return the FeatureCollection.

    RFC 7946 GeoJSON is WGS 84 by definition, but Netcad drawings are usually
    projected. Pass ``srid`` (e.g. 5254) to add the GeoJSON 2008 ``crs`` member,
    which GDAL and QGIS read, so the plan lands in the right place.
    """
    collection = entities_to_feature_collection(entities, plan_type=plan_type)
    if srid and int(srid) != 4326:
        collection = {
            "type": "FeatureCollection",
            "crs": {"type": "name", "properties": {"name": f"urn:ogc:def:crs:EPSG::{int(srid)}"}},
            "features": collection["features"],
        }
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(collection, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return collection


def _entity_geometry(entity: NetcadEntity) -> dict | None:
    """Build a GeoJSON geometry for an entity, or None when it has no vertices."""
    coords = [[coord.x, coord.y, coord.z] for coord in entity.coordinates]
    kind = entity.geometry_kind.lower()
    if not coords:
        return None
    # A single vertex is a point whatever the kind: circles carry only their centre
    # (the radius stays in the properties), and a one-position LineString is invalid.
    if kind in {"point", "symbol", "text", "smartobject"} or len(coords) == 1:
        return {"type": "Point", "coordinates": coords[0]}
    if kind in {"polygon", "rectangle", "circle"} or entity.is_closed:
        ring = coords[:]
        if ring[0] != ring[-1]:
            ring.append(ring[0])
        if len(ring) < 4:
            return {"type": "LineString", "coordinates": coords}
        return {"type": "Polygon", "coordinates": [ring]}
    return {"type": "LineString", "coordinates": coords}


def _entity_properties(entity: NetcadEntity, classification: LayerClassification) -> dict:
    """Flatten CAD attributes and classification data into GeoJSON properties."""
    return {
        "geometry_kind": entity.geometry_kind,
        "layer_code": entity.layer_code,
        "layer_name": entity.layer_name,
        "color_argb": entity.color_argb,
        "name": entity.name,
        "label_text": entity.label_text,
        "text_height": entity.text_height,
        "rotation_degrees": entity.rotation_degrees,
        "box_width": entity.box_width,
        "box_height": entity.box_height,
        "scale": entity.scale,
        "grid_x": entity.grid_x,
        "grid_y": entity.grid_y,
        "radius": entity.radius,
        "start_angle": entity.start_angle,
        "end_angle": entity.end_angle,
        "is_closed": entity.is_closed,
        **classification_properties(classification),
    }
