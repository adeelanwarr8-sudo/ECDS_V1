"""ECDS Increment 1: local AOI parsing and guardrails (no GEE calls)."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pyproj import Geod
from shapely.geometry import shape, mapping
from shapely.validation import explain_validity

MIN_HA = 50.0
MAX_HA = 5000.0
_GEOD = Geod(ellps="WGS84")
_BOUNDARY = Path(__file__).parent / "data" / "sweden_boundary.geojson"


class AOIError(ValueError):
    pass


@lru_cache(maxsize=1)
def sweden_boundary():
    with _BOUNDARY.open(encoding="utf-8") as file:
        features = json.load(file)["features"]
    return shape(features[0]["geometry"])


def polygon_from_geojson(raw):
    """Accept one Polygon/Feature/one-feature FeatureCollection; reject extra AOIs."""
    obj = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
    if not isinstance(obj, dict):
        raise AOIError("File does not contain valid GeoJSON.")
    kind = obj.get("type")
    if kind == "FeatureCollection":
        feats = obj.get("features", [])
        if len(feats) != 1:
            raise AOIError("Exactly one polygon feature is allowed per analysis.")
        obj = feats[0]
        kind = obj.get("type")
    if kind == "Feature":
        obj = obj.get("geometry") or {}
        kind = obj.get("type")
    if kind != "Polygon":
        raise AOIError("Upload or draw one Polygon. MultiPolygons and lines are not accepted.")
    try:
        poly = shape(obj)
    except (ValueError, TypeError, KeyError) as exc:
        raise AOIError("Unable to interpret the uploaded geometry.") from exc
    if poly.is_empty or not poly.is_valid:
        raise AOIError(f"Invalid polygon geometry: {explain_validity(poly)}")
    return poly


def validate_aoi(raw):
    """Geodesic area, one-polygon validation, and coarse Sweden-only screening."""
    poly = polygon_from_geojson(raw)
    minx, miny, maxx, maxy = poly.bounds
    if minx < -180 or maxx > 180 or miny < -90 or maxy > 90:
        raise AOIError("Coordinates must use longitude/latitude in WGS84 (EPSG:4326).")
    area_m2, _ = _GEOD.geometry_area_perimeter(poly)
    hectares = abs(area_m2) / 10000.0
    if hectares < MIN_HA:
        raise AOIError(f"AOI is {hectares:,.1f} ha; minimum is {MIN_HA:,.0f} ha.")
    if hectares > MAX_HA:
        raise AOIError(f"AOI is {hectares:,.1f} ha; maximum is {MAX_HA:,.0f} ha (50 km²). Reduce the AOI.")
    # The bundled Natural Earth coastline is intentionally a *coarse* screening
    # boundary. The exact Swedish land boundary requires higher-resolution
    # authoritative data in a later increment.
    overlap = poly.intersection(sweden_boundary())
    inside_area = abs(_GEOD.geometry_area_perimeter(overlap)[0]) if not overlap.is_empty else 0
    share = inside_area / abs(area_m2) if area_m2 else 0
    if share < 0.90:
        raise AOIError("AOI is outside Sweden or cannot be accepted by the preliminary Sweden boundary check.")
    return {
        "geometry": mapping(poly),
        "area_ha": round(hectares, 2),
        "area_km2": round(hectares / 100.0, 3),
        "inside_share": round(share, 4),
        "center": [round(poly.centroid.y, 6), round(poly.centroid.x, 6)],
    }
