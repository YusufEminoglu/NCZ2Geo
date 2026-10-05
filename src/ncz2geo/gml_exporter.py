# -*- coding: utf-8 -*-
"""OGC PlanGML GML 3.2.1 & CityGML Exporter for NCZ2Geo."""

from __future__ import annotations

import html
import uuid
from pathlib import Path
from typing import Iterable

from .ncz_engine.model import NetcadEntity
from .plangml import LayerClassification, classify_layer


def export_plangml_gml(
    entities: Iterable[NetcadEntity],
    plan_type: str = "UIP",
    srs_name: str = "EPSG:5254",
    plan_name: str = "Imar Plani",
) -> str:
    """Generate an OGC GML 3.2.1 compliant XML document for PlanGML datasets.

    Args:
        entities: List of decoded NetcadEntity instances.
        plan_type: 'UIP', 'NIP', or 'CDP'.
        srs_name: Coordinate Reference System URI (e.g. 'EPSG:5254').
        plan_name: Name of the urban plan.

    Returns:
        XML string compliant with OGC GML 3.2.1 schema.
    """
    feature_members_xml: list[str] = []

    for idx, entity in enumerate(entities):
        if not entity.coordinates:
            continue

        c: LayerClassification = classify_layer(entity.layer_name, plan_type=plan_type)
        fid = f"PlanFeature_{idx+1}_{uuid.uuid4().hex[:6]}"
        safe_layer = html.escape(entity.layer_name)
        safe_tabaka = html.escape(c.identity.tabaka if c.identity else entity.layer_name)
        safe_fonk_kod = html.escape(c.identity.fonksiyon_kodu if c.identity else "")
        safe_fonk_adi = html.escape(c.identity.fonksiyon_adi if c.identity else (c.style.get("label", "") if c.style else ""))
        safe_ust_grup = html.escape(c.identity.ust_grup_adi if c.identity else "")

        # Format coordinates according to geometry type
        coords = entity.coordinates
        pos_list_str = " ".join(f"{pt.x:.3f} {pt.y:.3f}" for pt in coords)

        if entity.geometry_kind == "POLYGON" or (entity.is_closed and len(coords) >= 3):
            # Ensure closed ring
            if coords[0].x != coords[-1].x or coords[0].y != coords[-1].y:
                pos_list_str += f" {coords[0].x:.3f} {coords[0].y:.3f}"

            geom_xml = f"""        <plangml:geometri>
          <gml:Polygon gml:id="poly_{fid}" srsName="{srs_name}">
            <gml:exterior>
              <gml:LinearRing>
                <gml:posList srsDimension="2">{pos_list_str}</gml:posList>
              </gml:LinearRing>
            </gml:exterior>
          </gml:Polygon>
        </plangml:geometri>"""
        elif entity.geometry_kind in ("LINE", "POLYLINE"):
            geom_xml = f"""        <plangml:geometri>
          <gml:LineString gml:id="line_{fid}" srsName="{srs_name}">
            <gml:posList srsDimension="2">{pos_list_str}</gml:posList>
          </gml:LineString>
        </plangml:geometri>"""
        else:
            pt = coords[0]
            geom_xml = f"""        <plangml:geometri>
          <gml:Point gml:id="pt_{fid}" srsName="{srs_name}">
            <gml:pos srsDimension="2">{pt.x:.3f} {pt.y:.3f}</gml:pos>
          </gml:Point>
        </plangml:geometri>"""

        member_xml = f"""    <gml:featureMember>
      <plangml:PlanNesnesi gml:id="{fid}">
        <plangml:tabaka>{safe_tabaka}</plangml:tabaka>
        <plangml:katmanAdi>{safe_layer}</plangml:katmanAdi>
        <plangml:planTuru>{plan_type}</plangml:planTuru>
        <plangml:fonksiyonKodu>{safe_fonk_kod}</plangml:fonksiyonKodu>
        <plangml:fonksiyonAdi>{safe_fonk_adi}</plangml:fonksiyonAdi>
        <plangml:ustGrupAdi>{safe_ust_grup}</plangml:ustGrupAdi>
{geom_xml}
      </plangml:PlanNesnesi>
    </gml:featureMember>"""
        feature_members_xml.append(member_xml)

    joined_members = "\n".join(feature_members_xml)
    safe_plan_name = html.escape(plan_name)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<plangml:PlanFeatureCollection xmlns:gml="http://www.opengis.net/gml/3.2"
  xmlns:plangml="http://www.csb.gov.tr/plangml/1.0"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  gml:id="Plan_{uuid.uuid4().hex[:8]}">
  <gml:name>{safe_plan_name}</gml:name>
{joined_members}
</plangml:PlanFeatureCollection>
"""


def export_citygml_lods(
    entities: Iterable[NetcadEntity],
    output_path: str | Path,
    default_height: float = 9.0,
    srs_name: str = "urn:ogc:def:crs:EPSG::5254",
) -> Path:
    """Export Netcad building/land-use polygon entities to CityGML 2.0 LOD1 XML file."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    city_objects: list[str] = []
    for idx, e in enumerate(entities):
        if not e.coordinates or len(e.coordinates) < 3:
            continue
        c = classify_layer(e.layer_name)

        bldg_id = f"bldg_{idx+1}"
        pts = e.coordinates
        # Ground points z=0, Roof points z=default_height
        ground_pts_str = " ".join(f"{p.x:.3f} {p.y:.3f} 0.000" for p in pts)
        roof_pts_str = " ".join(f"{p.x:.3f} {p.y:.3f} {default_height:.3f}" for p in pts)

        obj_xml = f"""    <core:cityObjectMember>
      <bldg:Building gml:id="{bldg_id}">
        <bldg:class>1000</bldg:class>
        <bldg:function>{html.escape(c.identity.fonksiyon_adi if c.identity else e.layer_name)}</bldg:function>
        <bldg:measuredHeight uom="urn:ogc:def:uom:UCUM::m">{default_height:.1f}</bldg:measuredHeight>
        <bldg:lod1Solid>
          <gml:Solid>
            <gml:exterior>
              <gml:CompositeSurface>
                <gml:surfaceMember>
                  <gml:Polygon gml:id="p_ground_{bldg_id}">
                    <gml:exterior>
                      <gml:LinearRing>
                        <gml:posList srsDimension="3">{ground_pts_str}</gml:posList>
                      </gml:LinearRing>
                    </gml:exterior>
                  </gml:Polygon>
                </gml:surfaceMember>
                <gml:surfaceMember>
                  <gml:Polygon gml:id="p_roof_{bldg_id}">
                    <gml:exterior>
                      <gml:LinearRing>
                        <gml:posList srsDimension="3">{roof_pts_str}</gml:posList>
                      </gml:LinearRing>
                    </gml:exterior>
                  </gml:Polygon>
                </gml:surfaceMember>
              </gml:CompositeSurface>
            </gml:exterior>
          </gml:Solid>
        </bldg:lod1Solid>
      </bldg:Building>
    </core:cityObjectMember>"""
        city_objects.append(obj_xml)

    joined = "\n".join(city_objects)
    full_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<core:CityModel xmlns:core="http://www.opengis.net/citygml/2.0"
  xmlns:bldg="http://www.opengis.net/citygml/building/2.0"
  xmlns:gml="http://www.opengis.net/gml"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <gml:name>CityGML Model</gml:name>
{joined}
</core:CityModel>
"""
    out.write_text(full_xml, encoding="utf-8")
    return out
