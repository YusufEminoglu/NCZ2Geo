# -*- coding: utf-8 -*-
"""OGC SLD, QGIS QML, and Mapbox GL style exporters based on e-Plan / PlanGML catalog."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Iterable

from .plangml import LayerClassification, classify_layer


def export_sld(
    layer_names: Iterable[str],
    plan_type: str = "UIP",
    title: str = "e-Plan Styled Layer Descriptor",
) -> str:
    """Generate an OGC SLD (Styled Layer Descriptor 1.0.0 XML) for the given layer names.

    Args:
        layer_names: List or set of Netcad/PlanGML layer names.
        plan_type: Target plan type ('UIP', 'NIP', 'CDP').
        title: User style title in SLD header.

    Returns:
        XML string compliant with OGC SLD standard.
    """
    rules_xml: list[str] = []
    seen = set()

    for name in layer_names:
        if name in seen:
            continue
        seen.add(name)

        c: LayerClassification = classify_layer(name, plan_type=plan_type)
        fill_color = "#999999"
        stroke_color = "#333333"
        fill_opacity = 0.8
        stroke_width = 1.0
        label = name

        if c.style:
            fill_color = c.style.get("fill", fill_color)
            fill_opacity = float(c.style.get("fill_opacity", fill_opacity))
            label = c.style.get("label", name)
        elif c.identity:
            label = f"{c.identity.fonksiyon_adi} ({c.identity.tabaka})"

        safe_name = html.escape(name)
        safe_label = html.escape(label)
        safe_fill = html.escape(str(fill_color))
        safe_stroke = html.escape(str(stroke_color))

        rule = f"""    <Rule>
      <Name>{safe_name}</Name>
      <Title>{safe_label}</Title>
      <ogc:Filter xmlns:ogc="http://www.opengis.net/ogc">
        <ogc:PropertyIsEqualTo>
          <ogc:PropertyName>layer_name</ogc:PropertyName>
          <ogc:Literal>{safe_name}</ogc:Literal>
        </ogc:PropertyIsEqualTo>
      </ogc:Filter>
      <PolygonSymbolizer>
        <Fill>
          <CssParameter name="fill">{safe_fill}</CssParameter>
          <CssParameter name="fill-opacity">{fill_opacity:.2f}</CssParameter>
        </Fill>
        <Stroke>
          <CssParameter name="stroke">{safe_stroke}</CssParameter>
          <CssParameter name="stroke-width">{stroke_width:.1f}</CssParameter>
        </Stroke>
      </PolygonSymbolizer>
      <LineSymbolizer>
        <Stroke>
          <CssParameter name="stroke">{safe_fill}</CssParameter>
          <CssParameter name="stroke-width">2.0</CssParameter>
        </Stroke>
      </LineSymbolizer>
      <PointSymbolizer>
        <Graphic>
          <Mark>
            <WellKnownName>circle</WellKnownName>
            <Fill>
              <CssParameter name="fill">{safe_fill}</CssParameter>
            </Fill>
            <Stroke>
              <CssParameter name="stroke">{safe_stroke}</CssParameter>
              <CssParameter name="stroke-width">1.0</CssParameter>
            </Stroke>
          </Mark>
          <Size>8</Size>
        </Graphic>
      </PointSymbolizer>
    </Rule>"""
        rules_xml.append(rule)

    joined_rules = "\n".join(rules_xml)
    safe_title = html.escape(title)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor version="1.0.0"
  xsi:schemaLocation="http://www.opengis.net/sld StyledLayerDescriptor.xsd"
  xmlns="http://www.opengis.net/sld"
  xmlns:ogc="http://www.opengis.net/ogc"
  xmlns:xlink="http://www.w3.org/1999/xlink"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <NamedLayer>
    <Name>{safe_title}</Name>
    <UserStyle>
      <Title>{safe_title}</Title>
      <FeatureTypeStyle>
{joined_rules}
      </FeatureTypeStyle>
    </UserStyle>
  </NamedLayer>
</StyledLayerDescriptor>
"""


def export_qml(
    layer_names: Iterable[str],
    plan_type: str = "UIP",
    layer_title: str = "e-Plan Categorized Layer",
) -> str:
    """Generate a QGIS 3.x categorized renderer QML style file XML."""
    categories_xml: list[str] = []
    symbols_xml: list[str] = []
    seen = set()

    for idx, name in enumerate(layer_names):
        if name in seen:
            continue
        seen.add(name)

        c = classify_layer(name, plan_type=plan_type)
        fill_hex = "#999999"
        label = name
        if c.style:
            fill_hex = c.style.get("fill", fill_hex)
            label = c.style.get("label", name)
        elif c.identity:
            label = c.identity.fonksiyon_adi

        # Convert hex #RRGGBB to R,G,B
        clean_hex = fill_hex.lstrip("#")
        if len(clean_hex) == 6:
            r = int(clean_hex[0:2], 16)
            g = int(clean_hex[2:4], 16)
            b = int(clean_hex[4:6], 16)
        else:
            r, g, b = 150, 150, 150

        safe_name = html.escape(name)
        safe_label = html.escape(label)

        cat = f'      <category symbol="{idx}" value="{safe_name}" label="{safe_label}" render="true"/>'
        categories_xml.append(cat)

        sym = f"""    <symbol alpha="0.85" clip_to_extent="1" type="fill" name="{idx}">
      <layer class="SimpleFill" locked="0" pass="0" enabled="1">
        <prop k="color" v="{r},{g},{b},255"/>
        <prop k="outline_color" v="50,50,50,255"/>
        <prop k="outline_style" v="solid"/>
        <prop k="outline_width" v="0.26"/>
        <prop k="style" v="solid"/>
      </layer>
    </symbol>"""
        symbols_xml.append(sym)

    joined_cats = "\n".join(categories_xml)
    joined_syms = "\n".join(symbols_xml)

    return f"""<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.28.0" styleCategories="AllStyleCategories">
  <renderer-v2 type="categorizedSymbol" attr="layer_name" enableorderby="0">
    <categories>
{joined_cats}
    </categories>
    <symbols>
{joined_syms}
    </symbols>
  </renderer-v2>
</qgis>
"""


def export_mapbox_style(
    layer_names: Iterable[str],
    plan_type: str = "UIP",
    source_name: str = "ncz_plan",
    source_layer: str = "default",
) -> list[dict[str, Any]]:
    """Generate Mapbox GL / MapLibre Style Specification layer objects with match expressions."""
    color_match: list[Any] = ["match", ["get", "layer_name"]]
    seen = set()

    for name in layer_names:
        if name in seen:
            continue
        seen.add(name)
        c = classify_layer(name, plan_type=plan_type)
        color = "#888888"
        if c.style:
            color = c.style.get("fill", color)
        color_match.extend([name, color])

    color_match.append("#aaaaaa")  # Fallback default

    return [
        {
            "id": f"{source_name}_fills",
            "type": "fill",
            "source": source_name,
            "source-layer": source_layer,
            "filter": ["==", ["geometry-type"], "Polygon"],
            "paint": {
                "fill-color": color_match,
                "fill-opacity": 0.75,
                "fill-outline-color": "#222222",
            },
        },
        {
            "id": f"{source_name}_lines",
            "type": "line",
            "source": source_name,
            "source-layer": source_layer,
            "filter": ["==", ["geometry-type"], "LineString"],
            "paint": {
                "line-color": color_match,
                "line-width": 2.0,
            },
        },
        {
            "id": f"{source_name}_points",
            "type": "circle",
            "source": source_name,
            "source-layer": source_layer,
            "filter": ["==", ["geometry-type"], "Point"],
            "paint": {
                "circle-color": color_match,
                "circle-radius": 5,
                "circle-stroke-color": "#ffffff",
                "circle-stroke-width": 1,
            },
        },
    ]


def export_plan_styles(
    output_dir: str | Path,
    layer_names: Iterable[str],
    plan_type: str = "UIP",
    base_filename: str = "eplan_style",
) -> dict[str, Path]:
    """Export all style representations (SLD, QML, Mapbox JSON) to output_dir."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    sld_path = out / f"{base_filename}.sld"
    qml_path = out / f"{base_filename}.qml"
    mb_path = out / f"{base_filename}_mapbox.json"

    sld_path.write_text(export_sld(layer_names, plan_type=plan_type), encoding="utf-8")
    qml_path.write_text(export_qml(layer_names, plan_type=plan_type), encoding="utf-8")
    mb_path.write_text(
        json.dumps(export_mapbox_style(layer_names, plan_type=plan_type), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return {"sld": sld_path, "qml": qml_path, "mapbox": mb_path}
