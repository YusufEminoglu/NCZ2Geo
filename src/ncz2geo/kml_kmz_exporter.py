# -*- coding: utf-8 -*-
"""Google Earth 3D Volumetric Extrusion and KMZ Exporter for NCZ2Geo.

KML coordinates are always WGS 84 longitude/latitude. Netcad drawings are
usually projected (e.g. TUREF / TM30, EPSG:5254), so pass ``srid`` and the
exporter converts every vertex with :mod:`ncz2geo._projection` (sub-millimetre
agreement with PROJ for the bundled Turkish CRSs).
"""

from __future__ import annotations

import html
import io
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

from ._feature_table import build_feature_table
from ._projection import to_wgs84
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
        """Write the KML document to *output_path* and return the written path."""
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(self.kml_string, encoding="utf-8")
        return out

    def save_kmz(self, output_path: str | Path) -> Path:
        """Write the zipped KMZ payload to *output_path* and return the written path."""
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(self.kmz_bytes)
        return out


def export_to_kml_kmz(
    entities: Sequence[NetcadEntity],
    document_name: str = "Netcad Cadastral Plan",
    style_config: KMLStyleConfig | None = None,
    *,
    srid: Optional[int] = None,
    plan_type: str = "UIP",
) -> KMLExportResult:
    """Convert NetCAD entities into standard OGC KML 2.2 and zipped KMZ format with 3D extrusions.

    ``srid`` is the EPSG code of the drawing coordinates; they are converted to
    WGS 84 lon/lat (``None`` or 4326 means they already are). Projected
    coordinates without ``srid`` raise ``ValueError`` instead of producing a KML
    that places the plan off the globe. Geometry types follow
    :func:`write_geojson` (points, lines and polygons).
    """
    cfg = style_config or KMLStyleConfig()
    table = build_feature_table(entities, plan_type=plan_type)
    if not srid or int(srid) == 4326:
        for feature in table.features:
            if any(abs(x) > 180 or abs(y) > 90 for x, y, _z in feature.vertices()):
                raise ValueError(
                    "coordinates are not longitude/latitude; pass srid=<EPSG code of the drawing>"
                )
    placemarks: list[str] = []
    count = 0

    def kml_coords(points: Sequence[tuple[float, float, float]], extrude: bool) -> str:
        """Format vertices as ``lon,lat,alt`` tuples in WGS 84."""
        out = []
        for x, y, z in points:
            lon, lat = to_wgs84(x, y, srid)
            h = cfg.default_height_m if extrude else z
            out.append(f"{lon:.8f},{lat:.8f},{h:.2f}")
        return " ".join(out)

    for idx, feature in enumerate(table.features):
        props = feature.properties
        layer = str(props.get("layer_name") or "")
        name = html.escape(layer or f"Entity_{idx}")
        desc = (
            f"Layer: {name}<br>Geometry: {html.escape(str(props.get('geometry_kind')))}"
            f"<br>Points: {len(feature.vertices())}"
        )
        if feature.geometry_type == "Polygon":
            rings = [kml_coords(ring, cfg.extrude_3d) for ring in feature.coordinates]
            inner = "".join(
                f"""
        <innerBoundaryIs>
          <LinearRing>
            <coordinates>{ring}</coordinates>
          </LinearRing>
        </innerBoundaryIs>"""
                for ring in rings[1:]
            )
            geom_xml = f"""      <Polygon>
        <extrude>{1 if cfg.extrude_3d else 0}</extrude>
        <altitudeMode>{cfg.altitude_mode}</altitudeMode>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>{rings[0]}</coordinates>
          </LinearRing>
        </outerBoundaryIs>{inner}
      </Polygon>"""
        elif feature.geometry_type == "Point":
            geom_xml = f"""      <Point>
        <altitudeMode>{cfg.altitude_mode}</altitudeMode>
        <coordinates>{kml_coords(feature.coordinates, False)}</coordinates>
      </Point>"""
        else:
            geom_xml = f"""      <LineString>
        <extrude>{1 if cfg.extrude_3d else 0}</extrude>
        <altitudeMode>{cfg.altitude_mode}</altitudeMode>
        <coordinates>{kml_coords(feature.coordinates, cfg.extrude_3d)}</coordinates>
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
