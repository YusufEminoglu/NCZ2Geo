"""GeoJSON export helpers with PlanGML/e-Plan metadata."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .ncz_engine.model import NetcadEntity
from .plangml import classification_properties, classify_entity


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
) -> dict:
    """Write entities as styled GeoJSON and return the FeatureCollection."""
    collection = entities_to_feature_collection(entities, plan_type=plan_type)
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(collection, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return collection


def _entity_geometry(entity: NetcadEntity) -> dict | None:
    coords = [[coord.x, coord.y, coord.z] for coord in entity.coordinates]
    kind = entity.geometry_kind.lower()
    if not coords:
        return None
    if kind in {"point", "symbol", "text", "smartobject"}:
        return {"type": "Point", "coordinates": coords[0]}
    if kind in {"polygon", "rectangle", "circle"} or entity.is_closed:
        ring = coords[:]
        if ring[0] != ring[-1]:
            ring.append(ring[0])
        if len(ring) < 4:
            return {"type": "LineString", "coordinates": coords}
        return {"type": "Polygon", "coordinates": [ring]}
    if len(coords) == 1:
        return {"type": "Point", "coordinates": coords[0]}
    return {"type": "LineString", "coordinates": coords}


def _entity_properties(entity: NetcadEntity, classification) -> dict:
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
