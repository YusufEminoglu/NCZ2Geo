# -*- coding: utf-8 -*-
"""Cadastral Land Consolidation, Share Re-allotment & Parcellation Optimizer for NCZ2Geo."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Sequence
from .ncz_engine.model import NetcadCoordinate, NetcadEntity


@dataclass
class OwnershipShare:
    owner_id: str
    pre_consolidation_area_m2: float
    land_value_index: float = 1.0  # Toprak derecelendirme endeksi (0.1 - 1.0)
    allocated_parcel_id: str = ""
    post_consolidation_area_m2: float = 0.0
    deduction_ratio_pct: float = 0.0  # Düzenleme Ortaklık Payı (DOP)


@dataclass
class ConsolidatedParcel:
    parcel_id: str
    gross_area_m2: float
    net_area_m2: float
    owner_ids: list[str]
    road_frontage_m: float
    shape_regularity_score: float  # 0.0 to 1.0 (compactness)
    boundary_polygon: list[tuple[float, float]]


@dataclass
class LandConsolidationReport:
    total_pre_area_m2: float
    total_post_allocated_m2: float
    total_public_deduction_m2: float  # DOP alanı
    dop_rate_pct: float  # e.g. 40.0%
    number_of_owners: int
    number_of_consolidated_parcels: int
    parcels: list[ConsolidatedParcel]
    owner_shares: list[OwnershipShare]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_pre_area_m2": round(self.total_pre_area_m2, 2),
            "total_post_allocated_m2": round(self.total_post_allocated_m2, 2),
            "dop_rate_pct": round(self.dop_rate_pct, 2),
            "number_of_owners": self.number_of_owners,
            "number_of_parcels": self.number_of_consolidated_parcels,
        }


def optimize_land_consolidation(
    owner_inputs: Sequence[OwnershipShare | dict[str, Any]],
    target_dop_rate_pct: float = 40.0,
    target_parcel_min_width_m: float = 20.0,
) -> LandConsolidationReport:
    """Perform cadastral land consolidation, apply DOP public deductions, and optimize rectangular parcellation."""
    shares: list[OwnershipShare] = []
    tot_pre_area = 0.0

    for item in owner_inputs:
        if isinstance(item, dict):
            s = OwnershipShare(
                owner_id=str(item.get("owner_id", "OWNER")),
                pre_consolidation_area_m2=float(item.get("area_m2", 1000.0)),
                land_value_index=float(item.get("value_index", 1.0)),
            )
        else:
            s = item
        shares.append(s)
        tot_pre_area += s.pre_consolidation_area_m2

    dop_frac = target_dop_rate_pct / 100.0
    tot_dop_area = tot_pre_area * dop_frac
    tot_post_area = tot_pre_area - tot_dop_area

    parcels: list[ConsolidatedParcel] = []
    curr_x = 0.0
    curr_y = 0.0
    parcel_depth = 50.0  # standard 50m parcel depth

    for idx, s in enumerate(shares):
        net_area = s.pre_consolidation_area_m2 * (1.0 - dop_frac) * s.land_value_index
        s.post_consolidation_area_m2 = net_area
        s.deduction_ratio_pct = target_dop_rate_pct
        pid = f"PARCEL_{idx+101}"
        s.allocated_parcel_id = pid

        # Calculate rectangular geometry along frontage
        p_width = max(target_parcel_min_width_m, net_area / parcel_depth)
        poly = [
            (curr_x, curr_y),
            (curr_x + p_width, curr_y),
            (curr_x + p_width, curr_y + parcel_depth),
            (curr_x, curr_y + parcel_depth),
            (curr_x, curr_y),
        ]

        # Compactness ratio 4*pi*A / P^2
        perimeter = 2 * (p_width + parcel_depth)
        compactness = (4 * math.pi * (p_width * parcel_depth)) / (perimeter ** 2)

        parcels.append(
            ConsolidatedParcel(
                parcel_id=pid,
                gross_area_m2=s.pre_consolidation_area_m2,
                net_area_m2=net_area,
                owner_ids=[s.owner_id],
                road_frontage_m=p_width,
                shape_regularity_score=min(1.0, compactness),
                boundary_polygon=poly,
            )
        )
        curr_x += p_width + 10.0  # with 10m road interval

    return LandConsolidationReport(
        total_pre_area_m2=tot_pre_area,
        total_post_allocated_m2=tot_post_area,
        total_public_deduction_m2=tot_dop_area,
        dop_rate_pct=target_dop_rate_pct,
        number_of_owners=len(shares),
        number_of_consolidated_parcels=len(parcels),
        parcels=parcels,
        owner_shares=shares,
    )
