# -*- coding: utf-8 -*-
"""Google Earth 3D Volumetric Extrusion and KMZ Exporter for NCZ2Geo."""

from __future__ import annotations

import html
import io
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from .ncz_engine.model import NetcadEntity


@dataclass
class KMLStyleConfig:
    line_color_abgr: str = "ff00aaff"  # Alpha-Blue-Green-Red hex
    line_width: float = 2.0
    fill_color_abgr: str = "7f00aaff"
    extrude_3d: bool = True
    altitude_mode: str = "relativeToGround"  # clampToGround, relativeToGround, absolute
    default_height_m: float = 12.0


@dataclass
class KMLExportResult:
    kml_string: str
    feature_count: int
    kmz_bytes: bytes

    def save_kml(self, output_path: str | Path) -> Path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(self.kml_string, encoding="utf-8")
        return out

    def save_kmz(self, output_path: str | Path) -> Path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(self.kmz_bytes)
        return out


def export_to_kml_kmz(
    entities: Sequence[NetcadEntity],
    document_name: str = "Netcad Cadastral Plan",
    style_config: KMLStyleConfig | None = None,
) -> KMLExportResult:
    """Convert NetCAD entities into standard OGC KML 2.2 and zipped KMZ format with 3D extrusions."""
    cfg = style_config or KMLStyleConfig()
    placemarks: list[str] = []
    count = 0

    for idx, ent in enumerate(entities):
        if not ent.coordinates:
            continue

        name = html.escape(ent.layer_name or f"Entity_{idx}")
        desc = f"Layer: {name}<br>Geometry: {ent.geometry_kind}<br>Points: {len(ent.coordinates)}"

        # Format coordinates as: lon,lat,altitude
        coords_kml_list = []
        for pt in ent.coordinates:
            # NetCAD standard X=Easting(Lon), Y=Northing(Lat), Z=Elevation
            h = cfg.default_height_m if cfg.extrude_3d else pt.z
            coords_kml_list.append(f"{pt.x:.6f},{pt.y:.6f},{h:.2f}")

        coords_str = " ".join(coords_kml_list)

        if ent.geometry_kind in ("POLYGON", "PARCEL", "CLOSED_POLYLINE") or (ent.is_closed and len(ent.coordinates) >= 3):
            # Ensure closed ring
            if ent.coordinates[0] != ent.coordinates[-1]:
                coords_str += f" {coords_kml_list[0]}"

            geom_xml = f"""      <Polygon>
        <extrude>{1 if cfg.extrude_3d else 0}</extrude>
        <altitudeMode>{cfg.altitude_mode}</altitudeMode>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>{coords_str}</coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>"""
        elif ent.geometry_kind in ("POINT", "TEXT"):
            pt0 = ent.coordinates[0]
            geom_xml = f"""      <Point>
        <altitudeMode>{cfg.altitude_mode}</altitudeMode>
        <coordinates>{pt0.x:.6f},{pt0.y:.6f},{pt0.z:.2f}</coordinates>
      </Point>"""
        else:
            geom_xml = f"""      <LineString>
        <extrude>{1 if cfg.extrude_3d else 0}</extrude>
        <altitudeMode>{cfg.altitude_mode}</altitudeMode>
        <coordinates>{coords_str}</coordinates>
      </LineString>"""

        placemark_xml = f"""    <Placemark id="pm_{idx}">
      <name>{name}</name>
      <description><![CDATA[{desc}]]></description>
      <styleUrl>#defaultStyle</styleUrl>
{geom_xml}
    </Placemark>"""
        placemarks.append(placemark_xml)
        count += 1

    kml_doc = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>{html.escape(document_name)}</name>
    <Style id="defaultStyle">
      <LineStyle>
        <color>{cfg.line_color_abgr}</color>
        <width>{cfg.line_width}</width>
      </LineStyle>
      <PolyStyle>
        <color>{cfg.fill_color_abgr}</color>
        <outline>1</outline>
      </PolyStyle>
    </Style>
{chr(10).join(placemarks)}
  </Document>
</kml>"""

    # Build KMZ in-memory zip
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("doc.kml", kml_doc.encode("utf-8"))

    return KMLExportResult(
        kml_string=kml_doc,
        feature_count=count,
        kmz_bytes=zip_buf.getvalue(),
    )
