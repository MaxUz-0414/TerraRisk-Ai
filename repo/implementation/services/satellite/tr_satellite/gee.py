"""
Google Earth Engine + spatial buffer  (Member A's area).

get_features() returns a dict with exactly these keys. The ML model, the dashboard and the PDF depend on them.

    upstream_slope_deg          float   95th-percentile slope inside the buffer (degrees)
    dist_to_river_m             int     distance from the parcel to the nearest surface water (metres)
    ndvi_trend_pct              float   change in yearly mean vegetation index, first vs last full year (%)
    lst_peak_c                  float   peak monthly land-surface temperature (deg C)
    soil_moisture_change_pct    float   last 12 months of soil moisture vs. the earlier years (%)
    siltation                   str     "Low" | "Moderate" | "High"
    soil_saturation             str     "Low" | "Moderate" | "High" | "Extreme"
    ndvi_series                 dict    {"labels": [12 months], "years": {"2024": [12 floats or None], ...}}
    lst_series                  dict    {"labels": [12 months], "average": [12], "historic": [12]}
    --- optional extras (may be missing on older saved parcels, or None when a dataset has no data there) ---
    rain_12m_mm                 float   rainfall of the last 12 full months (CHIRPS), mm
    rain_anomaly_pct            float   that total versus the average of earlier years, percent
    rain_series                 dict    {"labels": [12 month names], "current": [12], "average": [12]}
    ndwi_now                    float   plant-water index (MODIS NDWI), last full year
    ndwi_change                 float   NDWI now minus 4 years ago (negative = drying)
    built_up_pct                float   share of built-up land within 500 m (ESA WorldCover), percent
    hand_m                      float   height above the nearest drainage channel (MERIT Hydro), metres
    upstream_area_km2           float   catchment area draining into the parcel (MERIT Hydro), km2
    lst_anomaly_c               float   peak summer temperature now minus the older years, deg C
    landslide_inputs            dict    inputs of the landslide model, measured like ml/build_dataset.py:
                                        {"ndvi", "lst_peak_c", "soil_moisture", "slope", "elevation"}
                                        (last 60 days at the parcel centre; values may be None)

USE_FAKE_DATA=True (default) returns deterministic demo values, so the whole app works without GEE.
USE_FAKE_DATA=False runs real queries (needs GEE credentials in .env).
"""
import logging
import math
import random
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone

from tr_common.config import env_bool, env_str

logger = logging.getLogger(__name__)

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def get_features(geometry, buffer_km, center):
    """geometry: GeoJSON dict. buffer_km: 3-5. center: (lat, lng)."""
    if env_bool("USE_FAKE_DATA", True):
        return _fake_features(center, buffer_km)
    return _real_features(geometry, buffer_km, center)


def _derive_labels(slope, dist, moisture):
    siltation = "High" if slope > 25 and dist < 800 else "Moderate" if slope > 15 else "Low"
    saturation = "Extreme" if dist < 500 else "High" if dist < 1200 else "Moderate" if dist < 1800 else "Low"
    if moisture > 5:  # unusually wet soil
        saturation = {"Low": "Moderate", "Moderate": "High"}.get(saturation, saturation)
    return siltation, saturation


# --------------------------------------------------------------------------- demo data
def _fake_features(center, buffer_km):
    lat, lng = center
    rng = random.Random(f"{round(lat, 3)}:{round(lng, 3)}:{buffer_km}")

    slope = round(rng.uniform(6, 38), 1)
    dist = rng.randint(80, 2500)
    ndvi_trend = round(rng.uniform(-25, 4), 1)
    lst = round(rng.uniform(24, 40), 1)
    moisture = round(rng.uniform(-25, 5), 1)

    this_year = date.today().year
    base = rng.uniform(0.35, 0.6)
    years = {
        str(y): [
            round(max(0.0, min(1.0, base + 0.25 * math.sin((m - 3) / 12 * 2 * math.pi)
                                + (y - this_year) * ndvi_trend / 400 + rng.uniform(-0.03, 0.03))), 3)
            for m in range(12)
        ]
        for y in (this_year - 2, this_year - 1, this_year)
    }
    seasonal = [(math.cos((m - 6) / 12 * 2 * math.pi) + 1) / 2 for m in range(12)]  # peaks in July
    average = [round(lst - 12 + 12 * s, 1) for s in seasonal]
    historic = [round(v - 1.5 + rng.uniform(-0.4, 0.4), 1) for v in average]
    siltation, saturation = _derive_labels(slope, dist, moisture)

    # Landslide model inputs (drawn after the values above, so earlier demo results stay the same)
    landslide_inputs = {
        "ndvi": round(max(0.0, min(1.0, base + rng.uniform(-0.08, 0.08))), 3),
        "lst_peak_c": round(lst - rng.uniform(2, 9), 1),
        "soil_moisture": round(rng.uniform(0.15, 0.45), 3),
        "slope": round(slope * rng.uniform(0.35, 0.85), 1),
        "elevation": round(rng.uniform(150, 2800), 1),
    }

    # Extra indicators (drawn last so the demo values above never change)
    rain_labels = _last_12_month_labels(date.today())
    wet_season = [(math.cos((m - 6) / 12 * 2 * math.pi) + 1) / 2 for m in range(12)]
    rain_base = rng.uniform(450, 1700)
    rain_average = [round(rain_base / 12 * (0.45 + 1.1 * w), 1) for w in wet_season]
    rain_anomaly = round(rng.uniform(-30, 25), 1)
    rain_current = [round(v * (1 + rain_anomaly / 100 + rng.uniform(-0.25, 0.25)), 1) for v in rain_average]
    extras = {
        "rain_12m_mm": round(sum(rain_current)),
        "rain_anomaly_pct": rain_anomaly,
        "rain_series": {"labels": [lab for lab, _ in rain_labels], "current": rain_current, "average": rain_average},
        "ndwi_now": round(rng.uniform(-0.05, 0.35), 3),
        "ndwi_change": round(rng.uniform(-0.12, 0.05), 3),
        "built_up_pct": round(rng.choice([rng.uniform(0, 8), rng.uniform(5, 35), rng.uniform(30, 75)]), 1),
        "hand_m": round(rng.choice([rng.uniform(0.3, 6), rng.uniform(4, 25), rng.uniform(20, 90)]), 1),
        "upstream_area_km2": round(10 ** rng.uniform(-1.5, 3.2), 2),
        "lst_anomaly_c": round(max(average) - max(historic), 1),
    }

    return {
        "upstream_slope_deg": slope,
        "dist_to_river_m": dist,
        "ndvi_trend_pct": ndvi_trend,
        "lst_peak_c": lst,
        "soil_moisture_change_pct": moisture,
        "siltation": siltation,
        "soil_saturation": saturation,
        "ndvi_series": {"labels": MONTHS, "years": years},
        "lst_series": {"labels": MONTHS, "average": average, "historic": historic},
        "landslide_inputs": landslide_inputs,
        **extras,
    }


def _last_12_month_labels(today):
    """[(label, (year, month)), ...] for the last 12 FULL months, oldest first."""
    year, month = today.year, today.month
    out = []
    for _ in range(12):
        month -= 1
        if month == 0:
            year, month = year - 1, 12
        out.append((MONTHS[month - 1], (year, month)))
    return out[::-1]


# --------------------------------------------------------------------------- real GEE
_ee = None


def _init_ee():
    """Initialise Earth Engine once per process (service account if configured, else local login)."""
    global _ee
    if _ee is None:
        import ee

        project = env_str("GEE_PROJECT") or None
        account, key_file = env_str("GEE_SERVICE_ACCOUNT"), env_str("GEE_KEY_FILE")
        if account and key_file:
            credentials = ee.ServiceAccountCredentials(account, key_file)
            ee.Initialize(credentials, project=project)
        else:
            ee.Initialize(project=project)
        _ee = ee
    return _ee


def _first(dictionary):
    """First value of an ee reduceRegion result (key names vary by reducer)."""
    for value in (dictionary or {}).values():
        return value
    return None


def _slope(ee, ring):
    slope = ee.Terrain.slope(ee.Image("USGS/SRTMGL1_003"))
    result = slope.reduceRegion(
        reducer=ee.Reducer.percentile([95]), geometry=ring, scale=90, maxPixels=1e9, bestEffort=True
    ).getInfo()
    value = _first(result)
    if value is None:
        raise ValueError("No elevation data for this location (SRTM covers roughly 60N to 56S).")
    return round(float(value), 1)


def _river_distance(ee, parcel, radius_m):
    water = ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select("occurrence").gt(50).selfMask()
    distance = water.distance(ee.Kernel.euclidean(radius_m, "meters"), False)
    result = distance.reduceRegion(
        reducer=ee.Reducer.min(), geometry=parcel, scale=30, maxPixels=1e8, bestEffort=True
    ).getInfo()
    value = _first(result)
    return int(value) if value is not None else int(radius_m)  # no water inside the buffer


def _image_means(ee, collection, to_band, region, scale):
    """Mean of one band over `region` for every image: returns [(epoch_ms, value), ...]."""

    def per_image(img):
        stats = ee.Dictionary(to_band(img).reduceRegion(
            reducer=ee.Reducer.mean(), geometry=region, scale=scale, maxPixels=1e8, bestEffort=True))
        return ee.Feature(None, {"t": img.date().millis(), "v": stats.values().get(0)})

    features = ee.FeatureCollection(collection.map(per_image)).filter(ee.Filter.notNull(["v"])).getInfo()["features"]
    return [(f["properties"]["t"], f["properties"]["v"]) for f in features]


def _monthly(rows):
    """[(epoch_ms, value)] -> {(year, month): mean}"""
    buckets = {}
    for t, v in rows:
        d = datetime.fromtimestamp(t / 1000, tz=timezone.utc)
        buckets.setdefault((d.year, d.month), []).append(v)
    return {k: sum(v) / len(v) for k, v in buckets.items()}


def _mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def _ndvi_rows(ee, region, start, end):
    ic = ee.ImageCollection("MODIS/061/MOD13Q1").filterDate(start, end).select("NDVI")
    return _image_means(ee, ic, lambda i: i.select("NDVI").multiply(0.0001).rename("v"), region, 250)


def _lst_rows(ee, region, start, end):
    ic = ee.ImageCollection("MODIS/061/MOD11A2").filterDate(start, end).select("LST_Day_1km")
    return _image_means(ee, ic, lambda i: i.select("LST_Day_1km").multiply(0.02).subtract(273.15).rename("v"), region, 1000)


def _soil_rows(ee, region, start, end):
    ic = ee.ImageCollection("ECMWF/ERA5_LAND/MONTHLY_AGGR").filterDate(start, end).select("volumetric_soil_water_layer_1")
    return _image_means(ee, ic, lambda i: i.select("volumetric_soil_water_layer_1").rename("v"), region, 11132)


LANDSLIDE_LOOKBACK_DAYS = 60   # same window as ml/build_dataset.py
LANDSLIDE_RADIUS_M = 500


def _landslide_inputs(ee, center):
    """The 5 landslide-model inputs at the parcel centre, measured exactly like ml/build_dataset.py
    (MODIS NDVI and LST, ERA5-Land soil moisture over the last 60 days; SRTM slope and elevation).
    Never raises: on any problem the values are None and the model fills them in."""
    empty = {"ndvi": None, "lst_peak_c": None, "soil_moisture": None, "slope": None, "elevation": None}
    try:
        lat, lng = center
        point = ee.Geometry.Point([float(lng), float(lat)])
        end = ee.Date(date.today().isoformat()).advance(1, "day")
        start = end.advance(-(LANDSLIDE_LOOKBACK_DAYS + 1), "day")

        def mean_or_empty(collection_id, band):
            ic = ee.ImageCollection(collection_id).filterBounds(point).filterDate(start, end).select(band)
            blank = ee.Image.constant(0).rename(band).updateMask(ee.Image.constant(0))
            return ee.Image(ee.Algorithms.If(ic.size().gt(0), ic.mean(), blank)).rename(band)

        def around(image, scale):
            return image.reduceRegion(reducer=ee.Reducer.mean(), geometry=point.buffer(max(LANDSLIDE_RADIUS_M, scale)),
                                      scale=scale, bestEffort=True, maxPixels=1_000_000)

        dem = ee.Image("USGS/SRTMGL1_003")
        result = ee.Dictionary({
            "ndvi": around(mean_or_empty("MODIS/061/MOD13Q1", "NDVI").multiply(0.0001), 250),
            "lst": around(mean_or_empty("MODIS/061/MOD11A1", "LST_Day_1km").multiply(0.02).subtract(273.15), 1000),
            "soil": around(mean_or_empty("ECMWF/ERA5_LAND/DAILY_AGGR", "volumetric_soil_water_layer_1"), 11132),
            "terrain": around(dem.rename("elevation").addBands(ee.Terrain.slope(dem).rename("slope")), 30),
        }).getInfo()

        def rounded(value, digits):
            return round(float(value), digits) if value is not None else None

        return {
            "ndvi": rounded(result["ndvi"].get("NDVI"), 3),
            "lst_peak_c": rounded(result["lst"].get("LST_Day_1km"), 1),
            "soil_moisture": rounded(result["soil"].get("volumetric_soil_water_layer_1"), 3),
            "slope": rounded(result["terrain"].get("slope"), 1),
            "elevation": rounded(result["terrain"].get("elevation"), 1),
        }
    except Exception:
        logger.exception("Could not read landslide model inputs from Earth Engine")
        return empty


def _safe(name, function, *args):
    """Run one OPTIONAL satellite metric. A failure returns None instead of breaking the whole analysis."""
    try:
        return function(*args)
    except Exception:
        logger.exception("Optional satellite metric '%s' failed", name)
        return None


def _monthly_sum(rows):
    """[(epoch_ms, value)] -> {(year, month): sum}"""
    buckets = {}
    for t, v in rows:
        d = datetime.fromtimestamp(t / 1000, tz=timezone.utc)
        buckets[(d.year, d.month)] = buckets.get((d.year, d.month), 0.0) + v
    return buckets


def _rain(ee, region, today):
    """Rainfall (CHIRPS, 5-day totals): last 12 full months versus the average of earlier years."""
    start, end = f"{today.year - 6}-01-01", today.isoformat()
    ic = ee.ImageCollection("UCSB-CHG/CHIRPS/PENTAD").filterDate(start, end).select("precipitation")
    sums = _monthly_sum(_image_means(ee, ic, lambda i: i.select("precipitation").rename("v"), region, 5566))
    window = _last_12_month_labels(today)
    window_keys = {key for _, key in window}
    current, average = [], []
    for label, (year, month) in window:
        earlier = [v for (y, m), v in sums.items() if m == month and (y, m) not in window_keys]
        if (year, month) not in sums or len(earlier) < 2:
            return None  # not enough history to say anything honest
        current.append(round(sums[(year, month)], 1))
        average.append(round(sum(earlier) / len(earlier), 1))
    total, normal = sum(current), sum(average)
    return {
        "rain_12m_mm": round(total),
        "rain_anomaly_pct": round((total - normal) / normal * 100, 1) if normal > 0 else None,
        "rain_series": {"labels": [label for label, _ in window], "current": current, "average": average},
    }


def _ndwi(ee, region, today):
    """Plant water content (MODIS NDWI = (NIR - SWIR) / (NIR + SWIR)): last full year and change versus 4 years ago."""
    start = f"{today.year - 4}-01-01"
    ic = ee.ImageCollection("MODIS/061/MOD09A1").filterDate(start, today.isoformat())
    rows = _image_means(ee, ic, lambda i: i.normalizedDifference(["sur_refl_b02", "sur_refl_b06"]).rename("v"), region, 500)
    monthly = _monthly(rows)
    yearly = {y: _mean([monthly.get((y, m)) for m in range(1, 13)]) for y in range(today.year - 4, today.year + 1)}
    yearly = {y: v for y, v in yearly.items() if v is not None}
    complete = [y for y in sorted(yearly) if y < today.year] or sorted(yearly)
    if not complete:
        return None
    return {"ndwi_now": round(yearly[complete[-1]], 3), "ndwi_change": round(yearly[complete[-1]] - yearly[complete[0]], 3)}


def _built_up(ee, parcel):
    """Share of built-up land (ESA WorldCover 2021, class 50) within 500 m of the parcel, in percent."""
    built = ee.ImageCollection("ESA/WorldCover/v200").first().select("Map").eq(50).rename("built")
    value = built.reduceRegion(reducer=ee.Reducer.mean(), geometry=parcel.buffer(500), scale=30,
                               maxPixels=1e9, bestEffort=True).get("built").getInfo()
    return None if value is None else round(float(value) * 100, 1)


def _hydro(ee, parcel):
    """MERIT Hydro: height above the nearest drainage channel (m) and the catchment area draining in (km2)."""
    near = parcel.buffer(300)
    image = ee.Image("MERIT/Hydro/v1_0_1")
    hand = image.select("hnd").reduceRegion(reducer=ee.Reducer.mean(), geometry=near, scale=90,
                                            maxPixels=1e8, bestEffort=True).get("hnd").getInfo()
    upa = image.select("upa").reduceRegion(reducer=ee.Reducer.max(), geometry=near, scale=90,
                                           maxPixels=1e8, bestEffort=True).get("upa").getInfo()
    return {
        "hand_m": None if hand is None else round(float(hand), 1),
        "upstream_area_km2": None if upa is None else round(float(upa), 2),
    }


def _real_features(geometry, buffer_km, center):
    ee = _init_ee()
    parcel = ee.Geometry(geometry)
    radius_m = buffer_km * 1000
    ring = parcel.buffer(radius_m)
    near = parcel.buffer(300)  # small pad so tiny plots still cover a satellite pixel

    this_year = date.today().year
    start, end = f"{this_year - 4}-01-01", date.today().isoformat()

    today = date.today()
    with ThreadPoolExecutor(max_workers=8) as pool:
        jobs = {
            "slope": pool.submit(_slope, ee, ring),
            "river": pool.submit(_river_distance, ee, parcel, radius_m),
            "ndvi": pool.submit(_ndvi_rows, ee, near, start, end),
            "lst": pool.submit(_lst_rows, ee, near, start, end),
            "soil": pool.submit(_soil_rows, ee, ring, start, end),
            "landslide": pool.submit(_landslide_inputs, ee, center),
            # Optional extras: a failure here only hides that card, it never fails the analysis.
            "rain": pool.submit(_safe, "rain", _rain, ee, ring, today),
            "ndwi": pool.submit(_safe, "ndwi", _ndwi, ee, near, today),
            "built": pool.submit(_safe, "built-up", _built_up, ee, parcel),
            "hydro": pool.submit(_safe, "hydrology", _hydro, ee, parcel),
        }
        results = {name: job.result() for name, job in jobs.items()}  # re-raises any GEE error of the core jobs

    # --- NDVI: last 3 years by month + trend between first and last full year
    ndvi = _monthly(results["ndvi"])
    yearly = {y: _mean([ndvi.get((y, m)) for m in range(1, 13)]) for y in range(this_year - 4, this_year + 1)}
    yearly = {y: v for y, v in yearly.items() if v is not None}
    if not yearly:
        raise ValueError("No vegetation data available for this location.")
    complete = [y for y in sorted(yearly) if y < this_year] or sorted(yearly)
    first, last = yearly[complete[0]], yearly[complete[-1]]
    ndvi_trend = round((last - first) / first * 100, 1) if abs(first) > 1e-6 else 0.0
    ndvi_years = {
        str(y): [round(ndvi[(y, m)], 3) if (y, m) in ndvi else None for m in range(1, 13)]
        for y in range(this_year - 2, this_year + 1)
    }

    # --- LST: monthly average over all years, "historic" = the older half of the years
    lst = {k: v for k, v in _monthly(results["lst"]).items() if -60 < v < 80}
    years = sorted({y for y, _ in lst})
    if not years:
        raise ValueError("No land-surface temperature data available for this location.")
    older = years[: max(1, len(years) // 2)]
    average = [_mean([lst.get((y, m)) for y in years]) for m in range(1, 13)]
    historic = [_mean([lst.get((y, m)) for y in older]) for m in range(1, 13)]
    lst_peak = max(v for v in average if v is not None)

    # --- Soil moisture: last 12 months vs. earlier months
    soil = _monthly(results["soil"])
    ordered = [soil[k] for k in sorted(soil)]
    if len(ordered) >= 18 and _mean(ordered[:-12]):
        moisture = round((_mean(ordered[-12:]) - _mean(ordered[:-12])) / _mean(ordered[:-12]) * 100, 1)
    else:
        moisture = 0.0

    slope, dist = results["slope"], results["river"]
    siltation, saturation = _derive_labels(slope, dist, moisture)
    r1 = lambda values: [round(v, 1) if v is not None else None for v in values]  # noqa: E731
    return {
        "upstream_slope_deg": slope,
        "dist_to_river_m": dist,
        "ndvi_trend_pct": ndvi_trend,
        "lst_peak_c": round(lst_peak, 1),
        "soil_moisture_change_pct": moisture,
        "siltation": siltation,
        "soil_saturation": saturation,
        "ndvi_series": {"labels": MONTHS, "years": ndvi_years},
        "lst_series": {"labels": MONTHS, "average": r1(average), "historic": r1(historic)},
        "landslide_inputs": results["landslide"],
        **_real_extras(results, lst_peak, historic),
    }


def _real_extras(results, lst_peak, historic):
    """Merge the optional metrics; anything missing simply stays None."""
    extras = {
        "rain_12m_mm": None, "rain_anomaly_pct": None, "rain_series": None,
        "ndwi_now": None, "ndwi_change": None,
        "built_up_pct": results["built"],
        "hand_m": None, "upstream_area_km2": None,
        "lst_anomaly_c": None,
    }
    for key in ("rain", "ndwi", "hydro"):
        extras.update(results[key] or {})
    old_peaks = [v for v in historic if v is not None]
    if old_peaks:
        extras["lst_anomaly_c"] = round(lst_peak - max(old_peaks), 1)
    return extras
