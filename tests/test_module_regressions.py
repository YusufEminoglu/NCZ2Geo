# -*- coding: utf-8 -*-
# Copyright (C) 2026 Yusuf Eminoğlu
# SPDX-License-Identifier: GPL-2.0-or-later
"""Regressions and edge cases for the CLI, zoning capacity and transformer modules."""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ncz2geo
from ncz2geo.cli import main
from ncz2geo.ncz_engine.model import NetcadCoordinate, NetcadEntity
from ncz2geo.transformer import (
    DATUM_PARAMS,
    helmert_7parameter_transform,
    transform_entities,
)
from ncz2geo.zoning_density import calculate_zoning_capacity
from tests import ncz_fixtures as fx

_SQUARE = [
    NetcadCoordinate(0.0, 0.0),
    NetcadCoordinate(100.0, 0.0),
    NetcadCoordinate(100.0, 100.0),
    NetcadCoordinate(0.0, 100.0),
]


def _parcel(layer_name: str) -> NetcadEntity:
    return NetcadEntity("Polygon", 1, layer_name=layer_name, is_closed=True, coordinates=_SQUARE)


class TestZoningCapacity(unittest.TestCase):
    def test_turkish_catalog_function_names_are_classified(self) -> None:
        # Regression: catalog names such as "TİCARET ALANI" and "PASİF YEŞİL
        # ALAN" never matched the ASCII keywords, so commercial and green
        # parcels fell through to the generic "other" branch.
        report = calculate_zoning_capacity(
            [_parcel("PL_TICARET"), _parcel("PL_PASIF_YESIL")], default_emsal=1.5
        )
        self.assertEqual(report.total_commercial_area_m2, 10000.0)
        self.assertEqual(report.total_open_green_area_m2, 10000.0)
        commercial, green = report.parcels
        self.assertAlmostEqual(commercial.kaks_emsal_max, 1.8)
        self.assertEqual(commercial.required_parking_spaces, 450)
        self.assertEqual(green.total_construction_area_m2, 0.0)

    def test_raw_office_layer_is_commercial(self) -> None:
        report = calculate_zoning_capacity([_parcel("MERKEZ_OFIS")])
        self.assertEqual(report.total_commercial_area_m2, 10000.0)

    def test_residential_road_and_other_branches(self) -> None:
        report = calculate_zoning_capacity(
            [_parcel("PL_GELISME_KONUT"), _parcel("ANA CADDE"), _parcel("ZZZ_UNKNOWN")],
            dwelling_unit_size_m2=100.0,
            average_household_size=3.0,
        )
        residential, road, other = report.parcels
        self.assertEqual(residential.estimated_dwellings, 150)
        self.assertEqual(residential.estimated_residents, 450)
        self.assertEqual(road.total_construction_area_m2, 0.0)
        self.assertEqual(report.total_road_network_area_m2, 10000.0)
        self.assertEqual(other.required_parking_spaces, 150)
        self.assertAlmostEqual(report.gross_density_persons_per_ha, 450 / 3.0)


class TestTransformer(unittest.TestCase):
    def test_named_parameter_sets_round_trip_approximately(self) -> None:
        x, y, z = 4200000.0, 2300000.0, 4100000.0
        forward = helmert_7parameter_transform(x, y, z, DATUM_PARAMS["ED50_TO_ITRF96_TR"])
        back = helmert_7parameter_transform(*forward, DATUM_PARAMS["ITRF96_TO_ED50_TR"])
        for original, restored in zip((x, y, z), back):
            self.assertAlmostEqual(original, restored, delta=0.1)

    def test_transform_entities_modes(self) -> None:
        entity = NetcadEntity("Point", 0, coordinates=[NetcadCoordinate(10.0, 20.0, 5.0)])
        helmert = transform_entities([entity], helmert_params="ITRF96_TO_ED50_TR")[0]
        expected = helmert_7parameter_transform(10.0, 20.0, 5.0, DATUM_PARAMS["ITRF96_TO_ED50_TR"])
        coord = helmert.coordinates[0]
        self.assertEqual((coord.x, coord.y, coord.z), expected)

        affine = transform_entities(
            [entity], transformation_type="affine", affine_coeffs=(2.0, 0.0, 0.0, 2.0, 1.0, -1.0)
        )[0].coordinates[0]
        self.assertEqual((affine.x, affine.y, affine.z), (21.0, 39.0, 5.0))

        # Affine without coefficients (or an unknown type) leaves points alone.
        for kwargs in ({"transformation_type": "affine"}, {"transformation_type": "none"}):
            with self.subTest(**kwargs):
                same = transform_entities([entity], **kwargs)[0].coordinates[0]
                self.assertEqual((same.x, same.y, same.z), (10.0, 20.0, 5.0))
        self.assertIsNot(transform_entities([entity])[0], entity)


class TestCli(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.source = self.tmp / "drawing.ncz"
        self.source.write_bytes(fx.full_drawing())
        self.env = dict(os.environ, NCZ2GEO_NCZ_CACHE_DISABLE="1")
        self._env = mock.patch.dict(os.environ, {"NCZ2GEO_NCZ_CACHE_DISABLE": "1"})
        self._env.start()

    def tearDown(self) -> None:
        self._env.stop()
        self._tmp.cleanup()

    def _run(self, argv: list[str]) -> tuple[int, str]:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = main(argv)
        return code, buffer.getvalue()

    def test_output_to_a_narrow_encoding_does_not_crash(self) -> None:
        # Regression: redirected stdout on Windows uses the ANSI code page;
        # a layer name decoded to U+0081 or the report's emoji raised
        # UnicodeEncodeError instead of printing the report.
        odd = self.tmp / "odd.ncz"
        odd.write_bytes(fx.layer_table_block([b"R\x81AD"]) + fx.point_block(layer=0))
        src = str(Path(ncz2geo.__file__).resolve().parents[1])
        env = dict(
            self.env,
            PYTHONIOENCODING="cp1254",
            PYTHONPATH=os.pathsep.join([src, self.env.get("PYTHONPATH", "")]),
        )
        script = "import sys; from ncz2geo.cli import main; sys.exit(main(sys.argv[1:]))"
        for argv, code in ((["inspect", str(odd)], 0), (["validate", str(odd), "--markdown"], 1)):
            with self.subTest(argv=argv[0]):
                done = subprocess.run(
                    [sys.executable, "-c", script, *argv],
                    env=env,
                    capture_output=True,
                    timeout=120,
                )
                self.assertEqual(done.returncode, code, done.stderr.decode("cp1254", "replace"))
                self.assertNotIn(b"UnicodeEncodeError", done.stderr)

    def test_inspect_text_listing(self) -> None:
        code, out = self._run(["inspect", str(self.source), "--plan-type", "NIP"])
        self.assertEqual(code, 0)
        self.assertIn("Plan type: NIP", out)
        self.assertIn("Version: NCZ-TEST-1.0", out)
        self.assertIn("CRS: EPSG:5254", out)
        self.assertIn("Layers:", out)

    def test_inspect_empty_drawing(self) -> None:
        empty = self.tmp / "empty.ncz"
        empty.write_bytes(b"")
        code, out = self._run(["inspect", str(empty)])
        self.assertEqual(code, 0)
        self.assertIn("No supported Netcad geometry layers found.", out)

    def test_convert_selected_layers(self) -> None:
        output = self.tmp / "layers.geojson"
        code, _ = self._run(["convert", str(self.source), str(output), "--layers", "1,"])
        self.assertEqual(code, 0)
        features = json.loads(output.read_text(encoding="utf-8"))["features"]
        self.assertTrue(features)

    def test_validate_text_report(self) -> None:
        code, out = self._run(["validate", str(self.source)])
        self.assertIn("PlanGML Compliance:", out)
        self.assertIn("Total Entities:", out)
        self.assertIn(code, (0, 1))

    def test_style_single_formats_print_documents(self) -> None:
        for fmt, marker in (("sld", "<"), ("qml", "<"), ("mapbox", "[")):
            with self.subTest(fmt=fmt):
                code, out = self._run(["style", str(self.source), "--format", fmt])
                self.assertEqual(code, 0)
                self.assertTrue(out.lstrip().startswith(marker))
        code, out = self._run(["style", str(self.source), "--out-dir", str(self.tmp / "styles")])
        self.assertEqual(code, 0)
        self.assertTrue((self.tmp / "styles" / "eplan_style.sld").exists())


if __name__ == "__main__":
    unittest.main()
