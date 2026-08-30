# -*- coding: utf-8 -*-
"""NCZ2Geo Cookbook — GML 3.2.1 export, Helmert Transform & Zoning Capacity."""

import ncz2geo
from ncz2geo.ncz_engine.model import NetcadCoordinate, NetcadEntity

coords = [
    NetcadCoordinate(0.0, 0.0),
    NetcadCoordinate(100.0, 0.0),
    NetcadCoordinate(100.0, 100.0),
    NetcadCoordinate(0.0, 100.0),
    NetcadCoordinate(0.0, 0.0),
]
entity = NetcadEntity(geometry_kind="POLYGON", layer_code=1, layer_name="PL_GELISME_KONUT", is_closed=True, coordinates=coords)

# 1. Zoning Capacity
cap = ncz2geo.calculate_zoning_capacity([entity], plan_type="UIP", default_emsal=2.0)
print(f"Capacity Report: {cap.total_plan_area_m2} m2, Residents: {cap.total_estimated_residents}")

# 2. 7-Parameter Bursa-Wolf Datum Transform
trans_coords = [ncz2geo.helmert_7parameter_transform(p.x, p.y, p.z, ncz2geo.DATUM_PARAMS["ED50_TO_ITRF96_TR"]) for p in coords]
print(f"Transformed Coord 0: {trans_coords[0]}")

# 3. GML 3.2.1 Export
gml_xml = ncz2geo.export_plangml_gml([entity])
print(f"Generated GML (bytes): {len(gml_xml)}")
