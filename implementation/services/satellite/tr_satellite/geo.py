"""Small geometry helpers (no GIS libraries needed)."""
import math


def validate_geometry(geometry):
    """Raise ValueError unless this is a sane GeoJSON Point or Polygon."""
    if not isinstance(geometry, dict) or geometry.get("type") not in ("Point", "Polygon"):
        raise ValueError("Geometry must be a GeoJSON Point or Polygon.")
    coords = geometry.get("coordinates")
    points = [coords] if geometry["type"] == "Point" else (coords[0] if coords else [])
    if geometry["type"] == "Polygon" and len(points) < 4:
        raise ValueError("A polygon needs at least 3 corners.")
    for pt in points:
        if len(pt) < 2 or not (-180 <= pt[0] <= 180 and -90 <= pt[1] <= 90):
            raise ValueError("Coordinates are outside the valid longitude/latitude range.")


def _points(geometry):
    if geometry["type"] == "Point":
        return [geometry["coordinates"]]
    ring = geometry["coordinates"][0]
    return ring[:-1] if len(ring) > 1 and ring[0] == ring[-1] else ring


def centroid(geometry):
    """Return (lat, lng) as the average of the corners."""
    pts = _points(geometry)
    lng = sum(p[0] for p in pts) / len(pts)
    lat = sum(p[1] for p in pts) / len(pts)
    return lat, lng


def area_ha(geometry):
    """Approximate polygon area in hectares (flat-earth approximation, fine for parcels)."""
    if geometry["type"] != "Polygon":
        return None
    pts = _points(geometry)
    lat0 = math.radians(sum(p[1] for p in pts) / len(pts))
    xy = [(p[0] * 111_320 * math.cos(lat0), p[1] * 110_540) for p in pts]
    s = sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(xy, xy[1:] + xy[:1]))
    return round(abs(s) / 2 / 10_000, 2)


# --------------------------------------------------------------------------- web-mercator helpers (for map frames)
EARTH_R = 6378137.0


def to_mercator(lng, lat):
    lat = max(-85.0, min(85.0, lat))
    return EARTH_R * math.radians(lng), EARTH_R * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def from_mercator(x, y):
    return math.degrees(x / EARTH_R), math.degrees(2 * math.atan(math.exp(y / EARTH_R)) - math.pi / 2)


def ring_points(geometry):
    """All corner points of a Point/Polygon as (lng, lat)."""
    return [tuple(p[:2]) for p in _points(geometry)]
