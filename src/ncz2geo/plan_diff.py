# -*- coding: utf-8 -*-
"""Plan-to-Plan Spatial Difference & Zoning Amendment Engine for NCZ2Geo."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .ncz_engine.model import NetcadEntity, NetcadParseResult
from .plangml import LayerClassification, classify_layer
from .reader import NetcadReader, parse_netcad


@dataclass
class ZoningChangeItem:
    """Represents an altered, added, or removed zoning feature between two plan versions."""

    change_type: str  # 'ADDED', 'REMOVED', 'MODIFIED', 'RECLASSIFIED'
    layer_name_old: str
    layer_name_new: str
    function_old: str
    function_new: str
    area_delta_m2: float
    centroid_x: float
    centroid_y: float


@dataclass
class PlanDiffResult:
    """Master comparison scorecard between two urban zoning plans."""

    plan_type: str
    total_features_v1: int
    total_features_v2: int
    added_features_count: int
    removed_features_count: int
    reclassified_features_count: int
    net_area_change_by_function: dict[str, float]
    changes: list[ZoningChangeItem]

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_type": self.plan_type,
            "total_features_v1": self.total_features_v1,
            "total_features_v2": self.total_features_v2,
            "added_features_count": self.added_features_count,
            "removed_features_count": self.removed_features_count,
            "reclassified_features_count": self.reclassified_features_count,
            "net_area_change_by_function": {k: round(v, 2) for k, v in self.net_area_change_by_function.items()},
            "changes_count": len(self.changes),
        }


def _calc_area_and_centroid(coords: list[Any]) -> tuple[float, float, float]:
    n = len(coords)
    if n < 3:
        return 0.0, (coords[0].x if n > 0 else 0.0), (coords[0].y if n > 0 else 0.0)
    area = 0.0
    cx_sum = 0.0
    cy_sum = 0.0
    for i in range(n):
        j = (i + 1) % n
        cross = coords[i].x * coords[j].y - coords[j].x * coords[i].y
        area += cross
        cx_sum += (coords[i].x + coords[j].x) * cross
        cy_sum += (coords[i].y + coords[j].y) * cross
    area = abs(area) / 2.0
    if area > 1e-4:
        factor = 1.0 / (6.0 * (area if area > 0 else 1.0))
        return area, cx_sum * factor, cy_sum * factor
    return 0.0, coords[0].x, coords[0].y


def compare_plans(
    plan_v1: str | Path | list[NetcadEntity],
    plan_v2: str | Path | list[NetcadEntity],
    plan_type: str = "UIP",
    match_distance_threshold: float = 5.0,
) -> PlanDiffResult:
    """Compare two versions of an urban plan to detect zoning amendments and modifications."""
    entities1 = (
        parse_netcad(plan_v1).entities
        if isinstance(plan_v1, (str, Path))
        else list(plan_v1)
    )
    entities2 = (
        parse_netcad(plan_v2).entities
        if isinstance(plan_v2, (str, Path))
        else list(plan_v2)
    )

    # Compute centroids and properties
    props1 = []
    for e in entities1:
        if e.coordinates:
            area, cx, cy = _calc_area_and_centroid(e.coordinates)
            c = classify_layer(e.layer_name, plan_type=plan_type)
            fn_name = c.identity.fonksiyon_adi if c.identity else e.layer_name
            props1.append({"entity": e, "area": area, "cx": cx, "cy": cy, "fn": fn_name, "matched": False})

    props2 = []
    for e in entities2:
        if e.coordinates:
            area, cx, cy = _calc_area_and_centroid(e.coordinates)
            c = classify_layer(e.layer_name, plan_type=plan_type)
            fn_name = c.identity.fonksiyon_adi if c.identity else e.layer_name
            props2.append({"entity": e, "area": area, "cx": cx, "cy": cy, "fn": fn_name, "matched": False})

    changes: list[ZoningChangeItem] = []
    added_count = 0
    removed_count = 0
    reclassified_count = 0
    net_area_by_fn: dict[str, float] = {}

    # Match v1 to v2
    for p1 in props1:
        best_p2 = None
        best_dist = float("inf")
        for p2 in props2:
            if not p2["matched"]:
                dist = math.hypot(p1["cx"] - p2["cx"], p1["cy"] - p2["cy"])
                if dist < best_dist and dist <= match_distance_threshold:
                    best_dist = dist
                    best_p2 = p2

        if best_p2 is not None:
            p1["matched"] = True
            best_p2["matched"] = True
            area_delta = best_p2["area"] - p1["area"]

            if p1["fn"] != best_p2["fn"]:
                reclassified_count += 1
                changes.append(
                    ZoningChangeItem(
                        change_type="RECLASSIFIED",
                        layer_name_old=p1["entity"].layer_name,
                        layer_name_new=best_p2["entity"].layer_name,
                        function_old=p1["fn"],
                        function_new=best_p2["fn"],
                        area_delta_m2=area_delta,
                        centroid_x=best_p2["cx"],
                        centroid_y=best_p2["cy"],
                    )
                )
                net_area_by_fn[p1["fn"]] = net_area_by_fn.get(p1["fn"], 0.0) - p1["area"]
                net_area_by_fn[best_p2["fn"]] = net_area_by_fn.get(best_p2["fn"], 0.0) + best_p2["area"]
            elif abs(area_delta) > 1.0:
                changes.append(
                    ZoningChangeItem(
                        change_type="MODIFIED",
                        layer_name_old=p1["entity"].layer_name,
                        layer_name_new=best_p2["entity"].layer_name,
                        function_old=p1["fn"],
                        function_new=best_p2["fn"],
                        area_delta_m2=area_delta,
                        centroid_x=best_p2["cx"],
                        centroid_y=best_p2["cy"],
                    )
                )
                net_area_by_fn[p1["fn"]] = net_area_by_fn.get(p1["fn"], 0.0) + area_delta
        else:
            removed_count += 1
            changes.append(
                ZoningChangeItem(
                    change_type="REMOVED",
                    layer_name_old=p1["entity"].layer_name,
                    layer_name_new="",
                    function_old=p1["fn"],
                    function_new="",
                    area_delta_m2=-p1["area"],
                    centroid_x=p1["cx"],
                    centroid_y=p1["cy"],
                )
            )
            net_area_by_fn[p1["fn"]] = net_area_by_fn.get(p1["fn"], 0.0) - p1["area"]

    # Remaining unmatched in v2 are added
    for p2 in props2:
        if not p2["matched"]:
            added_count += 1
            changes.append(
                ZoningChangeItem(
                    change_type="ADDED",
                    layer_name_old="",
                    layer_name_new=p2["entity"].layer_name,
                    function_old="",
                    function_new=p2["fn"],
                    area_delta_m2=p2["area"],
                    centroid_x=p2["cx"],
                    centroid_y=p2["cy"],
                )
            )
            net_area_by_fn[p2["fn"]] = net_area_by_fn.get(p2["fn"], 0.0) + p2["area"]

    return PlanDiffResult(
        plan_type=plan_type,
        total_features_v1=len(entities1),
        total_features_v2=len(entities2),
        added_features_count=added_count,
        removed_features_count=removed_count,
        reclassified_features_count=reclassified_count,
        net_area_change_by_function=net_area_by_fn,
        changes=changes,
    )
