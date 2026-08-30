# -*- coding: utf-8 -*-
"""Urban Land-Use Balance, Density & FAR (EMSAL) Capacity Calculator for NCZ2Geo."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from .ncz_engine.model import NetcadEntity
from .plangml import LayerClassification, classify_layer


@dataclass
class ParcelCapacityItem:
    layer_name: str
    function_name: str
    net_area_m2: float
    taks_max: float  # Base ground area coefficient (TAKS)
    kaks_emsal_max: float  # Floor area ratio (KAKS / EMSAL)
    max_building_height_m: float  # Yençok
    footprint_area_m2: float
    total_construction_area_m2: float
    estimated_dwellings: int
    estimated_residents: int
    required_parking_spaces: int


@dataclass
class ZoningCapacityReport:
    plan_type: str
    total_plan_area_m2: float
    total_residential_area_m2: float
    total_commercial_area_m2: float
    total_open_green_area_m2: float
    total_road_network_area_m2: float
    total_construction_area_m2: float
    total_estimated_residents: int
    gross_density_persons_per_ha: float
    total_required_parking_spaces: int
    parcels: list[ParcelCapacityItem]

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_type": self.plan_type,
            "total_plan_area_ha": round(self.total_plan_area_m2 / 10000.0, 2),
            "total_construction_area_m2": round(self.total_construction_area_m2, 1),
            "total_estimated_residents": self.total_estimated_residents,
            "gross_density_persons_per_ha": round(self.gross_density_persons_per_ha, 1),
            "total_parking_spaces": self.total_required_parking_spaces,
            "green_area_per_resident_m2": round(
                self.total_open_green_area_m2 / max(1, self.total_estimated_residents), 2
            ),
        }


def _calc_entity_area(entity: NetcadEntity) -> float:
    coords = entity.coordinates
    n = len(coords)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += coords[i].x * coords[j].y - coords[j].x * coords[i].y
    return abs(area) / 2.0


def calculate_zoning_capacity(
    entities: Iterable[NetcadEntity],
    plan_type: str = "UIP",
    default_taks: float = 0.40,
    default_emsal: float = 1.50,
    average_household_size: float = 3.2,
    dwelling_unit_size_m2: float = 120.0,
) -> ZoningCapacityReport:
    """Calculate demographic capacity, construction floor area (EMSAL), and parking requirements from Netcad entities."""
    parcels: list[ParcelCapacityItem] = []
    tot_plan_area = 0.0
    tot_res_area = 0.0
    tot_com_area = 0.0
    tot_green_area = 0.0
    tot_road_area = 0.0
    tot_const_area = 0.0
    tot_residents = 0
    tot_parking = 0

    for e in entities:
        if not e.coordinates or len(e.coordinates) < 3:
            continue
        area = _calc_entity_area(e)
        if area <= 1e-3:
            continue

        tot_plan_area += area
        c = classify_layer(e.layer_name, plan_type=plan_type)
        fn_name = c.identity.fonksiyon_adi if c.identity else e.layer_name
        upper_fn = fn_name.upper()

        is_residential = "KONUT" in upper_fn or "GELISME" in upper_fn or "MESKEN" in upper_fn
        is_commercial = "TICARET" in upper_fn or "TURIZM" in upper_fn or "OFIZ" in upper_fn
        is_green = "PARK" in upper_fn or "YESIL" in upper_fn or "REKREASYON" in upper_fn
        is_road = "YOL" in upper_fn or "SOKAK" in upper_fn or "CADDE" in upper_fn or "MEYDAN" in upper_fn

        if is_residential:
            tot_res_area += area
            taks = default_taks
            emsal = default_emsal
            const_area = area * emsal
            dwellings = int(const_area / dwelling_unit_size_m2)
            residents = int(dwellings * average_household_size)
            parking = int(dwellings * 1.0)  # 1 parking per dwelling (Otopark Yonetmeligi)
            tot_const_area += const_area
            tot_residents += residents
            tot_parking += parking
        elif is_commercial:
            tot_com_area += area
            taks = 0.50
            emsal = default_emsal * 1.2
            const_area = area * emsal
            dwellings = 0
            residents = 0
            parking = int(const_area / 40.0)  # 1 parking per 40m2 commercial
            tot_const_area += const_area
            tot_parking += parking
        elif is_green:
            tot_green_area += area
            taks = 0.05
            emsal = 0.05
            const_area = 0.0
            dwellings = 0
            residents = 0
            parking = 0
        elif is_road:
            tot_road_area += area
            taks = 0.0
            emsal = 0.0
            const_area = 0.0
            dwellings = 0
            residents = 0
            parking = 0
        else:
            taks = default_taks
            emsal = default_emsal
            const_area = area * emsal
            dwellings = 0
            residents = 0
            parking = int(const_area / 100.0)

        parcels.append(
            ParcelCapacityItem(
                layer_name=e.layer_name,
                function_name=fn_name,
                net_area_m2=area,
                taks_max=taks,
                kaks_emsal_max=emsal,
                max_building_height_m=emsal * 3.5,
                footprint_area_m2=area * taks,
                total_construction_area_m2=const_area,
                estimated_dwellings=dwellings,
                estimated_residents=residents,
                required_parking_spaces=parking,
            )
        )

    plan_ha = tot_plan_area / 10000.0
    gross_density = tot_residents / max(0.01, plan_ha)

    return ZoningCapacityReport(
        plan_type=plan_type,
        total_plan_area_m2=tot_plan_area,
        total_residential_area_m2=tot_res_area,
        total_commercial_area_m2=tot_com_area,
        total_open_green_area_m2=tot_green_area,
        total_road_network_area_m2=tot_road_area,
        total_construction_area_m2=tot_const_area,
        total_estimated_residents=tot_residents,
        gross_density_persons_per_ha=gross_density,
        total_required_parking_spaces=tot_parking,
        parcels=parcels,
    )
