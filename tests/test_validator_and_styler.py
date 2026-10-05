# -*- coding: utf-8 -*-
"""Unit tests for NCZ2Geo validator and styler modules."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ncz2geo import (
    NetcadReader,
    export_mapbox_style,
    export_plan_styles,
    export_qml,
    export_sld,
    validate_plan,
)
from ncz2geo.cli import main as cli_main
from tests import ncz_fixtures as fx


def _planning_drawing() -> bytes:
    return b"".join(
        [
            fx.version_block(),
            fx.layer_table_block([b"PL_GELISME_KONUT", b"HAT_OTOYOL", b"TEXT"]),
            fx.color_table_block([(255, 0, 0), (0, 128, 0), (0, 0, 255)]),
            fx.projection_block(),
            fx.epsg_block(),
            fx.polyline_block(layer=0, closed=True),
            fx.line_block(layer=1),
            fx.text_block(layer=2),
        ]
    )


class TestValidatorAndStyler(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.source = Path(self.temp_dir.name) / "fixture.ncz"
        self.source.write_bytes(_planning_drawing())

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_validator_compliance_report(self) -> None:
        reader = NetcadReader(self.source).index()
        report = validate_plan(reader, plan_type="UIP")

        self.assertEqual(report.plan_type, "UIP")
        self.assertEqual(report.total_layers, 3)
        self.assertGreaterEqual(report.matched_layers, 2)
        self.assertIsInstance(report.quality_score, float)
        self.assertGreater(report.quality_score, 0.0)

        # Check dictionary and markdown export
        d = report.to_dict()
        self.assertIn("quality_score", d)
        self.assertIn("issues", d)

        md = report.to_markdown()
        self.assertIn("# PlanGML & e-Plan Compliance Report", md)

    def test_sld_export(self) -> None:
        layers = ["PL_GELISME_KONUT", "HAT_OTOYOL", "TEXT"]
        sld_xml = export_sld(layers, plan_type="UIP")

        self.assertIn("<StyledLayerDescriptor", sld_xml)
        self.assertIn("<PolygonSymbolizer>", sld_xml)
        self.assertIn("PL_GELISME_KONUT", sld_xml)

    def test_qml_export(self) -> None:
        layers = ["PL_GELISME_KONUT", "HAT_OTOYOL"]
        qml_xml = export_qml(layers, plan_type="UIP")

        self.assertIn("<!DOCTYPE qgis", qml_xml)
        self.assertIn("renderer-v2", qml_xml)
        self.assertIn("PL_GELISME_KONUT", qml_xml)

    def test_mapbox_style_export(self) -> None:
        layers = ["PL_GELISME_KONUT", "HAT_OTOYOL"]
        layers_json = export_mapbox_style(layers, plan_type="UIP")

        self.assertEqual(len(layers_json), 3)  # fill, line, point
        self.assertEqual(layers_json[0]["type"], "fill")
        self.assertEqual(layers_json[1]["type"], "line")
        self.assertEqual(layers_json[2]["type"], "circle")

    def test_export_plan_styles_all(self) -> None:
        out_dir = Path(self.temp_dir.name) / "styles"
        paths = export_plan_styles(out_dir, ["PL_GELISME_KONUT", "HAT_OTOYOL"])

        self.assertTrue(paths["sld"].exists())
        self.assertTrue(paths["qml"].exists())
        self.assertTrue(paths["mapbox"].exists())

    def test_cli_validate_and_style(self) -> None:
        ret_val = cli_main(["validate", str(self.source), "--plan-type", "UIP", "--json"])
        self.assertIn(ret_val, (0, 1))

        ret_val_md = cli_main(["validate", str(self.source), "--plan-type", "UIP", "--markdown"])
        self.assertIn(ret_val_md, (0, 1))

        styles_dir = Path(self.temp_dir.name) / "cli_styles"
        ret_style = cli_main(["style", str(self.source), "--out-dir", str(styles_dir)])
        self.assertEqual(ret_style, 0)
        self.assertTrue((styles_dir / "eplan_style.sld").exists())
