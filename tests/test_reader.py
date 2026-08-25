# -*- coding: utf-8 -*-
# Copyright (C) 2026 Yusuf Eminoğlu
# SPDX-License-Identifier: GPL-2.0-or-later
"""Public API tests for V2-only Netcad inspection and decoding."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ncz2geo import NetcadReader, inspect_source, parse_netcad
from ncz2geo.ncz_engine.v2 import cache as ncz_cache
from ncz2geo.ncz_engine.v2.parser import parse_bytes
from tests import ncz_fixtures as fx


class TestReader(unittest.TestCase):
    def _write(self, data: bytes) -> Path:
        descriptor, path = tempfile.mkstemp(suffix=".ncz", dir=Path(__file__).resolve().parent)
        os.close(descriptor)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        out = Path(path)
        out.write_bytes(data)
        return out

    def test_parse_netcad_uses_v2_backend(self) -> None:
        result = parse_netcad(self._write(fx.full_drawing()))

        self.assertEqual(result.parser_backend, "pure-python-v2")
        self.assertEqual(result.version_name, "NCZ-TEST-1.0")
        self.assertEqual(result.epsg, "EPSG:5254")
        self.assertGreaterEqual(len(result.entities), 8)
        self.assertTrue(result.entities[0].coordinates)

    def test_inspect_source_lists_layers_without_full_decode(self) -> None:
        path = self._write(fx.full_drawing())
        summaries = inspect_source(path)

        self.assertTrue(summaries)
        self.assertIn(1, {summary.layer_code for summary in summaries})
        self.assertTrue(all(summary.record_count > 0 for summary in summaries))

    def test_decode_layers_returns_selected_layer_only(self) -> None:
        path = self._write(fx.full_drawing())
        reader = NetcadReader(path).index()
        selected = reader.decode_layers([1])
        every = reader.parse().entities

        self.assertTrue(selected)
        self.assertLess(len(selected), len(every))
        self.assertTrue(all(entity.layer_code == 1 for entity in selected))

    def test_parse_bytes_is_safe_for_malformed_inputs(self) -> None:
        for data in (b"", b"\x15", b"@TAB", bytes(range(256))):
            with self.subTest(length=len(data)):
                payload = parse_bytes(data)
                self.assertEqual(payload["parser_backend"], "pure-python-v2")
                self.assertEqual(payload["entities"], [])

    def test_index_cache_can_be_disabled_by_package_env(self) -> None:
        cache_dir = Path(
            tempfile.mkdtemp(prefix="ncz2geo-cache-", dir=Path(__file__).resolve().parent)
        )
        self.addCleanup(lambda: _rmtree(cache_dir))
        with mock.patch.object(ncz_cache, "_cache_root", return_value=cache_dir):
            path = self._write(fx.full_drawing())
            NetcadReader(path).index()
            self.assertGreaterEqual(ncz_cache.clear(), 1)
            with mock.patch.dict(os.environ, {"NCZ2GEO_NCZ_CACHE_DISABLE": "1"}):
                NetcadReader(path).index()
                again = NetcadReader(path).index()
                self.assertFalse(again.from_cache)


def _rmtree(path: Path) -> None:
    import shutil

    shutil.rmtree(path, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
