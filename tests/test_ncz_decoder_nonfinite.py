# -*- coding: utf-8 -*-
# Copyright (C) 2026 Yusuf Eminoğlu
# SPDX-License-Identifier: GPL-2.0-or-later
"""Non-finite field values must never leak NaN/inf into decoded geometry."""

from __future__ import annotations

import json
import math
import struct
import unittest

from ncz2geo.ncz_engine.v2.binary import Cursor
from ncz2geo.ncz_engine.v2.geometry import (
    GeometryRecord,
    decode_arc,
    decode_box,
    decode_circle,
    decode_polyline,
    decode_smart_object,
)

NAN = float("nan")
INF = float("inf")
ORIGIN = [("<d", 8, 4500000.0), ("<d", 16, 500000.0)]


def _record(fields: list[tuple[str, int, float]], size: int = 400) -> GeometryRecord:
    """Build a GIS-layout (shift 0) record with the given packed fields."""
    buffer = bytearray(size)
    for fmt, offset, value in fields:
        struct.pack_into(fmt, buffer, offset, value)
    return GeometryRecord(Cursor(bytes(buffer)), 0, size - 1, 0)


def _assert_strict_json(test: unittest.TestCase, entity: dict | None) -> dict:
    test.assertIsNotNone(entity)
    assert entity is not None
    json.dumps(entity, allow_nan=False)
    return entity


class TestNonFiniteFields(unittest.TestCase):
    def test_box_with_nan_rotation_keeps_finite_ring(self) -> None:
        entity = _assert_strict_json(
            self,
            decode_box(
                _record(ORIGIN + [("<d", 104, 4500010.0), ("<d", 112, 500020.0), ("<f", 120, NAN)])
            ),
        )
        self.assertEqual(entity["rotation_degrees"], 0.0)
        self.assertEqual(entity["box_width"], 10.0)

    def test_smart_object_nan_size_falls_back_to_corner(self) -> None:
        entity = _assert_strict_json(
            self,
            decode_smart_object(
                _record(
                    ORIGIN
                    + [
                        ("<d", 169, NAN),
                        ("<d", 177, 5.0),
                        ("<d", 66, 4500010.0),
                        ("<d", 74, 500005.0),
                    ]
                )
            ),
        )
        self.assertEqual((entity["box_width"], entity["box_height"]), (10.0, 5.0))

    def test_circle_and_arc_infinite_radius(self) -> None:
        circle = _assert_strict_json(self, decode_circle(_record(ORIGIN + [("<d", 50, INF)])))
        self.assertEqual(circle["radius"], 0.0)
        arc = _assert_strict_json(
            self,
            decode_arc(_record(ORIGIN + [("<d", 86, NAN), ("<d", 104, INF), ("<d", 112, 1.5)])),
        )
        self.assertEqual((arc["radius"], arc["start_angle"], arc["end_angle"]), (0.0, 0.0, 1.5))

    def test_polyline_skips_nonfinite_vertices(self) -> None:
        # Three 24-byte vertices starting at offset 113: valid, NaN x, valid with NaN z.
        entity = _assert_strict_json(
            self,
            decode_polyline(
                _record(
                    [
                        ("<d", 113, 1.0),
                        ("<d", 121, 2.0),
                        ("<d", 137, NAN),
                        ("<d", 145, 1.0),
                        ("<d", 161, 3.0),
                        ("<d", 169, 4.0),
                        ("<d", 177, NAN),
                    ],
                    size=113 + 3 * 24,
                )
            ),
        )
        coords = entity["coordinates"]
        self.assertEqual(len(coords), 2)
        self.assertTrue(all(math.isfinite(v) for p in coords for v in p.values()))
        self.assertEqual(coords[-1], {"x": 4.0, "y": 3.0, "z": 0.0})


if __name__ == "__main__":
    unittest.main()
