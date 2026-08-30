# -*- coding: utf-8 -*-
"""7-Parameter 3D Helmert Datum Transformation & 2D Affine Alignment Engine for NCZ2Geo."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from .ncz_engine.model import NetcadCoordinate, NetcadEntity


@dataclass(frozen=True)
class Helmert7Params:
    """7-parameter Helmert 3D Bursa-Wolf datum transformation parameters."""

    dx: float  # Shift X (meters)
    dy: float  # Shift Y (meters)
    dz: float  # Shift Z (meters)
    rx_arcsec: float  # Rotation X in arc-seconds
    ry_arcsec: float  # Rotation Y in arc-seconds
    rz_arcsec: float  # Rotation Z in arc-seconds
    scale_ppm: float  # Scale factor in parts-per-million (ppm)


# Standard Turkey ED50 <-> ITRF96 / WGS84 7-parameter sets (Bursa-Wolf)
DATUM_PARAMS: dict[str, Helmert7Params] = {
    "ED50_TO_ITRF96_TR": Helmert7Params(
        dx=-84.1,
        dy=-101.8,
        dz=-129.7,
        rx_arcsec=0.0,
        ry_arcsec=0.0,
        rz_arcsec=0.54,
        scale_ppm=-2.26,
    ),
    "ITRF96_TO_ED50_TR": Helmert7Params(
        dx=84.1,
        dy=101.8,
        dz=129.7,
        rx_arcsec=0.0,
        ry_arcsec=0.0,
        rz_arcsec=-0.54,
        scale_ppm=2.26,
    ),
}


def helmert_7parameter_transform(
    x: float,
    y: float,
    z: float,
    params: Helmert7Params,
) -> tuple[float, float, float]:
    """Transform a 3D coordinate using the 7-parameter Bursa-Wolf formula."""
    # Convert rotation arcseconds to radians
    sec_to_rad = math.pi / (180.0 * 3600.0)
    rx = params.rx_arcsec * sec_to_rad
    ry = params.ry_arcsec * sec_to_rad
    rz = params.rz_arcsec * sec_to_rad
    s = 1.0 + (params.scale_ppm * 1e-6)

    # Matrix multiplication: X_new = [dX, dY, dZ] + s * [1, -rz, ry; rz, 1, -rx; -ry, rx, 1] * X
    x_new = params.dx + s * (x - rz * y + ry * z)
    y_new = params.dy + s * (rz * x + y - rx * z)
    z_new = params.dz + s * (-ry * x + rx * y + z)

    return x_new, y_new, z_new


def affine_transform_2d(
    x: float,
    y: float,
    a: float = 1.0,
    b: float = 0.0,
    c: float = 0.0,
    d: float = 1.0,
    tx: float = 0.0,
    ty: float = 0.0,
) -> tuple[float, float]:
    """Apply 2D 6-parameter affine transformation: [x', y'] = [a*x + b*y + tx, c*x + d*y + ty]."""
    x_new = a * x + b * y + tx
    y_new = c * x + d * y + ty
    return x_new, y_new


def transform_entities(
    entities: Iterable[NetcadEntity],
    transformation_type: str = "helmert",
    helmert_params: Helmert7Params | str = "ED50_TO_ITRF96_TR",
    affine_coeffs: tuple[float, float, float, float, float, float] | None = None,
) -> list[NetcadEntity]:
    """Transform all entity coordinates in a drawing using Helmert or 2D Affine models."""
    if isinstance(helmert_params, str):
        h_params = DATUM_PARAMS.get(helmert_params, DATUM_PARAMS["ED50_TO_ITRF96_TR"])
    else:
        h_params = helmert_params

    transformed: list[NetcadEntity] = []

    for entity in entities:
        new_coords: list[NetcadCoordinate] = []
        for pt in entity.coordinates:
            if transformation_type == "helmert":
                nx, ny, nz = helmert_7parameter_transform(pt.x, pt.y, pt.z, h_params)
            elif transformation_type == "affine" and affine_coeffs is not None:
                a, b, c, d, tx, ty = affine_coeffs
                nx, ny = affine_transform_2d(pt.x, pt.y, a, b, c, d, tx, ty)
                nz = pt.z
            else:
                nx, ny, nz = pt.x, pt.y, pt.z

            new_coords.append(NetcadCoordinate(x=nx, y=ny, z=nz))

        transformed.append(
            NetcadEntity(
                geometry_kind=entity.geometry_kind,
                layer_code=entity.layer_code,
                layer_name=entity.layer_name,
                color_argb=entity.color_argb,
                name=entity.name,
                label_text=entity.label_text,
                text_height=entity.text_height,
                rotation_degrees=entity.rotation_degrees,
                box_width=entity.box_width,
                box_height=entity.box_height,
                scale=entity.scale,
                grid_x=entity.grid_x,
                grid_y=entity.grid_y,
                radius=entity.radius,
                start_angle=entity.start_angle,
                end_angle=entity.end_angle,
                is_closed=entity.is_closed,
                coordinates=new_coords,
            )
        )

    return transformed
