# -*- coding: utf-8 -*-
# Copyright (C) 2026 Yusuf Eminoğlu
# SPDX-License-Identifier: GPL-2.0-or-later
"""PlanGML classification, GeoJSON, and CLI behavior tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from netcad2plangml import classify_layer, parse_netcad
from netcad2plangml.cli import main
from netcad2plangml.geojson import entities_to_feature_collection, write_geojson
from tests import ncz_fixtures as fx


class TestPlanGmlGeoJsonAndCli(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(
            tempfile.mkdtemp(prefix="netcad2plangml-", dir=Path(__file__).resolve().parent)
        )
        self.addCleanup(lambda: _rmtree(self.tmp))
        self.source = self.tmp / "fixture.ncz"
        self.source.write_bytes(_planning_drawing())

    def test_classify_layer_resolves_mpyy_identity_and_eplan_style(self) -> None:
        classification = classify_layer("PL_GELISME_KONUT", plan_type="UIP")

        self.assertTrue(classification.matched)
        self.assertIsNotNone(classification.identity)
        self.assertEqual(classification.identity.tabaka, "PL_GELISME_KONUT")
        self.assertEqual(classification.identity.fonksiyon_kodu, "112001")
        self.assertEqual(classification.style_key, "GELISME_KONUT")
        self.assertEqual(classification.style_plan_type, "UIP")
        self.assertIn("style", classification.style)

    def test_entities_to_feature_collection_adds_plangml_and_eplan_properties(self) -> None:
        result = parse_netcad(self.source)
        collection = entities_to_feature_collection(result.entities, plan_type="UIP")
        feature = collection["features"][0]
        props = feature["properties"]

        self.assertEqual(collection["type"], "FeatureCollection")
        self.assertEqual(props["layer_name"], "PL_GELISME_KONUT")
        self.assertEqual(props["plangml_tabaka"], "PL_GELISME_KONUT")
        self.assertEqual(props["plangml_fonksiyon_kodu"], "112001")
        self.assertEqual(props["eplan_style_key"], "GELISME_KONUT")
        self.assertTrue(props["plangml_matched"])

    def test_write_geojson_round_trip(self) -> None:
        out = self.tmp / "out.geojson"
        result = parse_netcad(self.source)
        collection = write_geojson(result.entities, out, plan_type="UIP")

        self.assertTrue(out.exists())
        self.assertEqual(json.loads(out.read_text(encoding="utf-8")), collection)

    def test_cli_inspect_json(self) -> None:
        self.assertEqual(main(["inspect", str(self.source), "--plan-type", "UIP", "--json"]), 0)

    def test_cli_convert_selected_layer(self) -> None:
        out = self.tmp / "selected.geojson"
        self.assertEqual(
            main(["convert", str(self.source), str(out), "--layers", "0", "--plan-type", "UIP"]),
            0,
        )
        payload = json.loads(out.read_text(encoding="utf-8"))

        self.assertEqual(payload["type"], "FeatureCollection")
        self.assertTrue(payload["features"])
        self.assertTrue(
            all(feature["properties"]["layer_code"] == 0 for feature in payload["features"])
        )
        self.assertTrue(
            all(feature["properties"]["plangml_tabaka"] == "PL_GELISME_KONUT"
                for feature in payload["features"])
        )


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


def _rmtree(path: Path) -> None:
    import shutil

    shutil.rmtree(path, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
