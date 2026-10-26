# -*- coding: utf-8 -*-
"""Pure-Python conversion of bundled projected/geographic CRSs to WGS 84 lon/lat.

Used by exporters whose format fixes the CRS to WGS 84 (KML/KMZ). Supported:

* Transverse Mercator CRSs (TUREF and ED50 3-degree TM zones, UTM): inverse
  Krüger series to 4th order in ``n``, sub-millimetre inside a zone.
* Web Mercator (EPSG:3857).
* Geographic CRSs (WGS 84, TUREF, ED50).

Datum: TUREF (ITRF96-based) is treated as WGS 84 (they agree to a few
centimetres). ED50 uses the position-vector Helmert transformation PROJ selects
for Turkey (EPSG dataset "ED50 to WGS 84", tx -84.1 ty -101.8 tz -129.7 m,
rz 0.468", scale 1.05 ppm), so results match ``cs2cs``.
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Callable, Optional

from ._crs import projjson

LonLat = tuple[float, float]

_ED50_TO_WGS84 = (
    -84.1,
    -101.8,
    -129.7,
    0.0,
    0.0,
    0.468,
    1.05,
)  # tx, ty, tz (m), rx, ry, rz ("), s (ppm)
_WGS84 = (6378137.0, 1 / 298.257223563)


def _ellipsoid(definition: dict) -> tuple[float, float]:
    """Return ``(a, f)`` of the ellipsoid of a PROJJSON CRS."""
    base = definition.get("base_crs", definition)
    datum = base.get("datum") or base.get("datum_ensemble") or {}
    ellipsoid = datum["ellipsoid"]
    return float(ellipsoid["semi_major_axis"]), 1.0 / float(ellipsoid["inverse_flattening"])


def _is_ed50(definition: dict) -> bool:
    """True when the CRS sits on the ED50 datum."""
    base = definition.get("base_crs", definition)
    return str(base.get("name", "")).upper().startswith("ED50")


def _helmert_ed50(lon: float, lat: float, a: float, f: float) -> LonLat:
    """Shift an ED50 lon/lat (h = 0) to WGS 84 via geocentric Helmert."""
    tx, ty, tz, rx, ry, rz, s = _ED50_TO_WGS84
    phi, lam = math.radians(lat), math.radians(lon)
    e2 = f * (2 - f)
    n_rad = a / math.sqrt(1 - e2 * math.sin(phi) ** 2)
    x = n_rad * math.cos(phi) * math.cos(lam)
    y = n_rad * math.cos(phi) * math.sin(lam)
    z = n_rad * (1 - e2) * math.sin(phi)
    arcsec = math.pi / (180 * 3600)
    rx, ry, rz, m = rx * arcsec, ry * arcsec, rz * arcsec, 1 + s * 1e-6
    x2 = tx + m * (x - rz * y + ry * z)
    y2 = ty + m * (rz * x + y - rx * z)
    z2 = tz + m * (-ry * x + rx * y + z)
    wa, wf = _WGS84
    we2 = wf * (2 - wf)
    p = math.hypot(x2, y2)
    lat2 = math.atan2(z2, p * (1 - we2))
    for _ in range(6):
        n2 = wa / math.sqrt(1 - we2 * math.sin(lat2) ** 2)
        h = p / math.cos(lat2) - n2
        lat2 = math.atan2(z2, p * (1 - we2 * n2 / (n2 + h)))
    return math.degrees(math.atan2(y2, x2)), math.degrees(lat2)


def _tm_inverse(definition: dict) -> Callable[[float, float], LonLat]:
    """Build an inverse Transverse Mercator function from a PROJJSON definition."""
    params = {p["name"]: float(p["value"]) for p in definition["conversion"]["parameters"]}
    lat0 = params.get("Latitude of natural origin", 0.0)
    if lat0 != 0.0:
        raise ValueError("only Transverse Mercator with latitude of origin 0 is supported")
    lon0 = math.radians(params["Longitude of natural origin"])
    k0 = params["Scale factor at natural origin"]
    fe, fn = params["False easting"], params["False northing"]
    a, f = _ellipsoid(definition)
    n = f / (2 - f)
    big_a = a / (1 + n) * (1 + n**2 / 4 + n**4 / 64)
    beta = (
        n / 2 - 2 * n**2 / 3 + 37 * n**3 / 96 - n**4 / 360,
        n**2 / 48 + n**3 / 15 - 437 * n**4 / 1440,
        17 * n**3 / 480 - 37 * n**4 / 840,
        4397 * n**4 / 161280,
    )
    delta = (
        2 * n - 2 * n**2 / 3 - 2 * n**3 + 116 * n**4 / 45,
        7 * n**2 / 3 - 8 * n**3 / 5 - 227 * n**4 / 45,
        56 * n**3 / 15 - 136 * n**4 / 35,
        4279 * n**4 / 630,
    )

    def inverse(easting: float, northing: float) -> LonLat:
        xi = (northing - fn) / (k0 * big_a)
        eta = (easting - fe) / (k0 * big_a)
        xi_p, eta_p = xi, eta
        for j, b in enumerate(beta, start=1):
            xi_p -= b * math.sin(2 * j * xi) * math.cosh(2 * j * eta)
            eta_p -= b * math.cos(2 * j * xi) * math.sinh(2 * j * eta)
        chi = math.asin(math.sin(xi_p) / math.cosh(eta_p))
        phi = chi + sum(d * math.sin(2 * j * chi) for j, d in enumerate(delta, start=1))
        lam = lon0 + math.atan2(math.sinh(eta_p), math.cos(xi_p))
        return math.degrees(lam), math.degrees(phi)

    return inverse


@lru_cache(maxsize=None)
def _converter(srid: int) -> Callable[[float, float], LonLat]:
    """Return a ``(x, y) -> (lon, lat)`` WGS 84 converter for a bundled EPSG code."""
    definition = projjson(srid)
    if definition is None:
        raise ValueError(
            f"EPSG:{srid} has no bundled definition; supported codes are listed by supported_epsg_codes()"
        )
    ed50 = _is_ed50(definition)
    a, f = _ellipsoid(definition)

    if definition["type"] == "GeographicCRS":
        base: Callable[[float, float], LonLat] = lambda x, y: (x, y)  # noqa: E731
    else:
        method = definition["conversion"]["method"]["name"]
        if method == "Transverse Mercator":
            base = _tm_inverse(definition)
        elif method == "Popular Visualisation Pseudo Mercator":
            radius = a

            def base(x: float, y: float) -> LonLat:
                return math.degrees(x / radius), math.degrees(
                    2 * math.atan(math.exp(y / radius)) - math.pi / 2
                )

        else:  # pragma: no cover - every bundled projected CRS is TM or Web Mercator
            raise ValueError(f"unsupported projection method: {method}")

    if not ed50:
        return base

    def shifted(x: float, y: float) -> LonLat:
        lon, lat = base(x, y)
        return _helmert_ed50(lon, lat, a, f)

    return shifted


def to_wgs84(x: float, y: float, srid: Optional[int]) -> LonLat:
    """Convert a coordinate in EPSG ``srid`` (easting/northing or lon/lat order) to WGS 84 lon/lat."""
    if not srid or int(srid) == 4326:
        return x, y
    return _converter(int(srid))(x, y)
