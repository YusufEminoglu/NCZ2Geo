# -*- coding: utf-8 -*-
"""Parametric Right-of-Way (İrtifak Hakkı) & Pipeline Corridor Slicer for NCZ2Geo."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Sequence
from ncz2geo.ncz_engine.model import NetcadCoordinate, NetcadEntity


@dataclass
class EasementParcelIntersection:
    parcel_id: str
    original_parcel_area_m2: float
    easement_strip_area_m2: float
    impact_percentage: float
    remaining_usable_area_m2: float
    is_severely_restricted: bool  # True if easement area > 35% of total parcel


@dataclass
class EasementCorridorResult:
    corridor_length_m: float
    corridor_width_m: float
    total_easement_area_m2: float
    impacted_parcels_count: int
    severely_restricted_parcels_count: int
    parcel_impacts: list[EasementParcelIntersection]

    def to_dict(self) -> dict[str, Any]:
        return {
            "length_m": round(self.corridor_length_m, 1),
            "width_m": round(self.corridor_width_m, 1),
            "total_easement_area_m2": round(self.total_easement_area_m2, 1),
            "impacted_parcels": self.impacted_parcels_count,
            "severe_restrictions": self.severely_restricted_parcels_count,
        }


def generate_easement_corridor_slices(
    centerline_3d: Sequence[tuple[float, float, float] | tuple[float, float]],
    parcels: Sequence[dict[str, Any]],  # List of {"id": str, "area_m2": float, "center": (x,y)}
    corridor_half_width_m: float = 15.0,  # e.g., 30m total ROW corridor for BOTAŞ/TEİAŞ
) -> EasementCorridorResult:
    """Compute statutory right-of-way easement corridor footprint and evaluate cadastral parcel intersections."""
    pts = [(float(p[0]), float(p[1])) for p in centerline_3d]
    if len(pts) < 2:
        return EasementCorridorResult(0.0, corridor_half_width_m * 2.0, 0.0, 0, 0, [])

    tot_len = 0.0
    for i in range(len(pts) - 1):
        tot_len += math.dist(pts[i], pts[i + 1])

    corridor_area = tot_len * (corridor_half_width_m * 2.0)

    impacts: list[EasementParcelIntersection] = []
    severe_count = 0

    for parcel in parcels:
        p_id = str(parcel.get("id", "PARCEL"))
        p_area = float(parcel.get("area_m2", 2000.0))
        p_center = parcel.get("center", (0.0, 0.0))
        cx, cy = float(p_center[0]), float(p_center[1])

        # Find minimum distance from parcel centroid to corridor centerline
        min_dist = float("inf")
        for i in range(len(pts) - 1):
            p1, p2 = pts[i], pts[i + 1]
            seg_len = math.dist(p1, p2)
            if seg_len < 1e-4:
                continue
            # Point to segment distance
            u = ((cx - p1[0]) * (p2[0] - p1[0]) + (cy - p1[1]) * (p2[1] - p1[1])) / (seg_len ** 2)
            u = max(0.0, min(1.0, u))
            proj_x = p1[0] + u * (p2[0] - p1[0])
            proj_y = p1[1] + u * (p2[1] - p1[1])
            d = math.hypot(cx - proj_x, cy - proj_y)
            min_dist = min(min_dist, d)

        if min_dist < corridor_half_width_m + math.sqrt(p_area) * 0.5:
            # Overlap exists
            overlap_factor = max(0.0, min(1.0, 1.0 - (min_dist / (corridor_half_width_m + 1e-4))))
            strip_area = min(p_area, p_area * (0.25 + 0.65 * overlap_factor))
            pct = (strip_area / max(1.0, p_area)) * 100.0
            is_severe = pct > 35.0
            if is_severe:
                severe_count += 1

            impacts.append(
                EasementParcelIntersection(
                    parcel_id=p_id,
                    original_parcel_area_m2=p_area,
                    easement_strip_area_m2=strip_area,
                    impact_percentage=pct,
                    remaining_usable_area_m2=p_area - strip_area,
                    is_severely_restricted=is_severe,
                )
            )

    return EasementCorridorResult(
        corridor_length_m=tot_len,
        corridor_width_m=corridor_half_width_m * 2.0,
        total_easement_area_m2=corridor_area,
        impacted_parcels_count=len(impacts),
        severely_restricted_parcels_count=severe_count,
        parcel_impacts=impacts,
    )
