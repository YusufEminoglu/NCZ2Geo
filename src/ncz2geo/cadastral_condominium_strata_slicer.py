# -*- coding: utf-8 -*-
"""3D Cadastral Condominium & Strata Title Vertical Unit Slicer for NCZ2Geo."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Sequence


@dataclass
class BuildingFloorStrataProfile:
    building_id: str
    number_of_floors: int = 5
    floor_height_m: float = 3.0
    units_per_floor: int = 4
    gross_floor_area_m2: float = 400.0
    common_area_ratio_pct: float = 18.0  # Common stairs, elevators, corridors


@dataclass
class StrataTitleUnitResult:
    building_id: str
    total_strata_units_count: int
    total_net_residential_area_m2: float
    total_common_area_m2: float
    unit_land_share_ratio: float  # Arsa Payı
    strata_units_list: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "building_id": self.building_id,
            "total_units": self.total_strata_units_count,
            "net_area_m2": round(self.total_net_residential_area_m2, 1),
            "common_area_m2": round(self.total_common_area_m2, 1),
            "land_share_per_unit": round(self.unit_land_share_ratio, 4),
        }


def slice_condominium_strata_units(
    building_footprint_polygon: Sequence[tuple[float, float]],
    profile: BuildingFloorStrataProfile | None = None,
    base_elevation_m: float = 0.0,
) -> StrataTitleUnitResult:
    """Generate 3D volumetric strata title cadastre units (Kat Mülkiyeti) and calculate land ownership shares (Arsa Payı)."""
    p = profile or BuildingFloorStrataProfile("Bldg_1")
    poly = list(building_footprint_polygon)
    
    tot_units = p.number_of_floors * p.units_per_floor
    if tot_units == 0:
        return StrataTitleUnitResult(p.building_id, 0, 0.0, 0.0, 0.0, [])

    total_gross = p.number_of_floors * p.gross_floor_area_m2
    common_area = total_gross * (p.common_area_ratio_pct / 100.0)
    net_residential = total_gross - common_area
    area_per_unit = net_residential / float(tot_units)
    land_share = 1.0 / float(tot_units)

    units_data: list[dict[str, Any]] = []

    for f in range(p.number_of_floors):
        floor_num = f + 1
        z_min = base_elevation_m + f * p.floor_height_m
        z_max = z_min + p.floor_height_m

        for u in range(p.units_per_floor):
            unit_no = f * p.units_per_floor + (u + 1)
            unit_id = f"{p.building_id}_F{floor_num}_U{unit_no}"

            units_data.append({
                "unit_id": unit_id,
                "floor_number": floor_num,
                "unit_number": unit_no,
                "z_min_m": round(z_min, 2),
                "z_max_m": round(z_max, 2),
                "net_area_m2": round(area_per_unit, 2),
                "land_share_fraction": f"1/{tot_units}",
                "land_share_pct": round(land_share * 100.0, 2),
            })

    return StrataTitleUnitResult(
        building_id=p.building_id,
        total_strata_units_count=tot_units,
        total_net_residential_area_m2=net_residential,
        total_common_area_m2=common_area,
        unit_land_share_ratio=land_share,
        strata_units_list=units_data,
    )
