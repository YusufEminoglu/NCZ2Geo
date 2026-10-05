# -*- coding: utf-8 -*-
# Copyright (C) 2026 Yusuf Eminoğlu
# SPDX-License-Identifier: GPL-2.0-or-later
"""Stable data contract shared by the NCZ Engine v2 reader and exporters.

The engine decodes an NCZ drawing into these dataclasses and the exporters
consume them; nothing outside this module constructs the engine's output
shape. Two consequences follow.

The field names are public. They are what a caller writes in a column map
and what the on-disk index cache stores, so renaming a field is a
cache-invalidating change and not a private tidy-up.

The field order is public too. It is the order the coordinate and attribute
readers fill, and the order a positional consumer expects, so fields are
appended at the end rather than inserted.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class NetcadCoordinate:
    """One vertex, already in map order: ``x`` is the easting."""

    x: float
    y: float
    z: float = 0.0


@dataclass
class NetcadEntity:
    """One drawing feature, whatever its geometry type.

    Netcad has a separate record for every kind of thing a drawing can
    hold. The decoder flattens them all into this one record and lets
    ``geometry_kind`` say which it was, so a consumer switches on the kind
    once instead of on a class hierarchy.
    """

    # What the feature is, and the drawing layer it sits on.
    geometry_kind: str
    layer_code: int
    layer_name: str = ""

    # Netcad colours are pen indices into the colour table; the decoder
    # resolves one to ARGB, or leaves it None when the index resolves to
    # nothing.
    color_argb: Optional[int] = None

    # Anything that carries text: the label, and the size and angle it is
    # drawn at. Block and symbol records name themselves through these too.
    name: str = ""
    label_text: str = ""
    text_height: float = 0.0
    rotation_degrees: float = 0.0

    # Footprints that are stored as a size and an angle rather than as
    # corners: plan boxes, map sheets, smart objects. A smart object also
    # carries the repetition grid its planning modules step along.
    box_width: float = 0.0
    box_height: float = 0.0
    scale: float = 0.0
    grid_x: float = 0.0
    grid_y: float = 0.0

    # Curve parameters, for the kinds the geometry layer has to approximate.
    radius: float = 0.0
    start_angle: float = 0.0
    end_angle: float = 0.0

    # Whether a polyline comes back to the vertex it started from.
    is_closed: bool = False

    # The vertices, in draw order.
    coordinates: list[NetcadCoordinate] = field(default_factory=list)


@dataclass
class NetcadAttributeRow:
    """One row of a Netcad ``@TAB`` attribute table.

    The columns are whatever the table's rows happened to set, so this is a
    name-to-value bag rather than a fixed record.
    """

    row_index: int
    columns: dict[str, object] = field(default_factory=dict)


@dataclass
class NetcadAttributeTable:
    """An ``@TAB`` table, keyed by the reference the drawing gives it."""

    table_ref: str
    rows: list[NetcadAttributeRow] = field(default_factory=list)


@dataclass
class NetcadParseResult:
    """One whole decoded drawing."""

    entities: list[NetcadEntity] = field(default_factory=list)
    attribute_tables: list[NetcadAttributeTable] = field(default_factory=list)

    # The drawing's own layer table, in the order the file declares it, with
    # each layer's colour already resolved to ARGB.
    layer_names: list[str] = field(default_factory=list)
    layer_colors: list[int] = field(default_factory=list)

    # Which decoder produced this result, so a caller never has to guess.
    parser_backend: str = ""

    # Drawing-level metadata read from the header blocks.
    version_name: str = ""
    epsg: str = ""
    projection_text: str = ""

    # Geometry types the decoder met but cannot build, mapped to how many
    # records carried them. A thin decode can say why it is thin.
    unsupported_geometry_types: dict[int, int] = field(default_factory=dict)
