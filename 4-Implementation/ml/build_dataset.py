"""
TerraRisk AI - Landslide Satellite Dataset Builder

Collects historical landslide locations and environmental measurements
from Google Earth Engine.

Labels:
    1 = Recorded landslide location
    0 = Candidate control location (not confirmed landslide-free)

Features per point:
    ndvi            MODIS MOD13Q1 vegetation index (mean over lookback window)
    lst_peak_c      MODIS MOD11A1 daytime land surface temperature, deg C
    soil_moisture   ERA5-Land volumetric soil water, top layer
    slope           SRTM slope in degrees (mean within 500 m)
    elevation       SRTM elevation in metres (mean within 500 m)

IMPORTANT:
Random control locations are not verified non-landslide locations.
The resulting dataset is suitable for a prototype, not validated
real-world landslide prediction.
"""

from pathlib import Path
import math
import random
import time

import ee
import pandas as pd


# --------------------------------------------------
# PROJECT CONFIGURATION
# --------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent

INPUT_FILE = ROOT / "data" / "processed" / "landslide_events_clean.csv"
OUTPUT_FILE = ROOT / "data" / "processed" / "landslide_satellite_features.csv"

GEE_PROJECT = "terrarisk-ai"

MAX_EVENTS = 300
LOOKBACK_DAYS = 60
POINT_RADIUS_M = 500     # area around each point for fine-resolution data
MAX_RETRIES = 3          # retry Earth Engine calls that fail temporarily

FEATURE_COLUMNS = [
    "ndvi",
    "lst_peak_c",
    "soil_moisture",
    "slope",
    "elevation",
]

random.seed(42)


# --------------------------------------------------
# INITIALIZE GOOGLE EARTH ENGINE
# --------------------------------------------------

def initialize_earth_engine():
    ee.Initialize(project=GEE_PROJECT)
    print("Google Earth Engine connected successfully.")


# --------------------------------------------------
# LOAD LANDSLIDE EVENTS
# --------------------------------------------------

def load_events():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Dataset not found: {INPUT_FILE}")

    df = pd.read_csv(INPUT_FILE)

    required = {"event_date", "latitude", "longitude"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")

    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce", utc=True)
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")

    df = df.dropna(subset=["event_date", "latitude", "longitude"]).copy()
    df = df[
        df["latitude"].between(-90, 90)
        & df["longitude"].between(-180, 180)
    ]

    df = df.head(MAX_EVENTS).copy()

    if df.empty:
        raise ValueError("No valid landslide events found.")

    print(f"Loaded {len(df)} landslide locations.")
    return df


# --------------------------------------------------
# EARTH ENGINE HELPERS
# --------------------------------------------------

def mean_or_empty(collection, band):
    """
    Mean of one band over a collection.

    If the collection is empty, return a fully masked image instead of
    failing, so the value simply comes back as missing (None).
    """
    empty = ee.Image.constant(0).rename(band).updateMask(ee.Image.constant(0))
    return ee.Image(
        ee.Algorithms.If(
            collection.size().gt(0),
            collection.select(band).mean(),
            empty,
        )
    ).rename(band)


def reduce_mean(image, point, scale):
    """
    Average an image around a point.

    The area is at least one pixel wide. For coarse data such as
    ERA5-Land (about 11 km pixels), a 500 m circle often contains no
    pixel centre at all, which returns no value. Using a radius of at
    least one pixel fixes that.
    """
    radius = max(POINT_RADIUS_M, scale)
    return image.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=point.buffer(radius),
        scale=scale,
        bestEffort=True,
        maxPixels=1_000_000,
    )


# --------------------------------------------------
# COLLECT SATELLITE FEATURES
# --------------------------------------------------

def get_satellite_features(latitude, longitude, event_date):
    point = ee.Geometry.Point([float(longitude), float(latitude)])

    event_day = pd.Timestamp(event_date).strftime("%Y-%m-%d")
    start_date = (
        pd.Timestamp(event_date) - pd.Timedelta(days=LOOKBACK_DAYS)
    ).strftime("%Y-%m-%d")

    # Exclusive end date: one day after the event, so the event day is included.
    end_date = ee.Date(event_day).advance(1, "day")

    # 1. NDVI - vegetation (MODIS 250 m, scale factor 0.0001)
    ndvi_image = mean_or_empty(
        ee.ImageCollection("MODIS/061/MOD13Q1")
        .filterBounds(point)
        .filterDate(start_date, end_date),
        "NDVI",
    ).multiply(0.0001)

    # 2. Land surface temperature (MODIS 1 km, Kelvin * 50 -> deg C)
    lst_image = mean_or_empty(
        ee.ImageCollection("MODIS/061/MOD11A1")
        .filterBounds(point)
        .filterDate(start_date, end_date),
        "LST_Day_1km",
    ).multiply(0.02).subtract(273.15)

    # 3. Soil moisture (ERA5-Land, about 11 km)
    soil_image = mean_or_empty(
        ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR")
        .filterBounds(point)
        .filterDate(start_date, end_date),
        "volumetric_soil_water_layer_1",
    )

    # 4. Terrain: slope and elevation (SRTM 30 m, covers 60N to 56S)
    dem = ee.Image("USGS/SRTMGL1_003")
    terrain_image = dem.rename("elevation").addBands(
        ee.Terrain.slope(dem).rename("slope")
    )

    # One request to Earth Engine for all features (much faster than one per feature).
    results = ee.Dictionary({
        "ndvi": reduce_mean(ndvi_image, point, 250),
        "lst": reduce_mean(lst_image, point, 1000),
        "soil": reduce_mean(soil_image, point, 11132),
        "terrain": reduce_mean(terrain_image, point, 30),
    }).getInfo()

    ndvi = results["ndvi"].get("NDVI")
    lst_c = results["lst"].get("LST_Day_1km")
    soil_moisture = results["soil"].get("volumetric_soil_water_layer_1")
    slope = results["terrain"].get("slope")
    elevation = results["terrain"].get("elevation")

    print(
        f"  NDVI: {ndvi}, LST: {lst_c}, Soil moisture: {soil_moisture}, "
        f"Slope: {slope}, Elevation: {elevation}"
    )

    return {
        "ndvi": ndvi,
        "lst_peak_c": lst_c,
        "soil_moisture": soil_moisture,
        "slope": slope,
        "elevation": elevation,
        "satellite_window_start": start_date,
        "satellite_window_end": event_day,
    }


def get_features_with_retry(latitude, longitude, event_date):
    """Retry temporary Earth Engine errors (timeouts, too many requests)."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return get_satellite_features(latitude, longitude, event_date)
        except ee.EEException as exc:
            if attempt == MAX_RETRIES:
                raise
            wait = 5 * attempt
            print(f"  Earth Engine error ({exc}). Retrying in {wait} s...")
            time.sleep(wait)


# --------------------------------------------------
# GENERATE CANDIDATE CONTROL LOCATION
# --------------------------------------------------

def random_nearby_point(latitude, longitude, min_km=10, max_km=50):
    distance = random.uniform(min_km, max_km) / 111.0
    angle = random.uniform(0, 2 * math.pi)

    new_lat = latitude + distance * math.sin(angle)
    new_lon = longitude + distance * math.cos(angle) / max(
        math.cos(math.radians(latitude)), 0.1
    )

    new_lat = max(-90, min(90, new_lat))
    new_lon = ((new_lon + 180) % 360) - 180

    return new_lat, new_lon


# --------------------------------------------------
# MAIN DATASET BUILDER
# --------------------------------------------------

def main():
    initialize_earth_engine()
    events = load_events()

    rows = []
    total_events = len(events)

    for index, (_, event) in enumerate(events.iterrows(), start=1):
        latitude = float(event["latitude"])
        longitude = float(event["longitude"])
        event_date = event["event_date"]

        print(f"\nProcessing event {index}/{total_events}")

        # Positive sample: recorded landslide
        try:
            features = get_features_with_retry(latitude, longitude, event_date)
            rows.append({
                "event_id": index,
                "event_date": event_date.isoformat(),
                "latitude": latitude,
                "longitude": longitude,
                "landslide": 1,
                "sample_type": "recorded_landslide",
                **features,
            })
        except Exception as exc:
            print(f"  Could not process landslide point: {exc}")

        # Candidate control sample: random point 10-50 km away, same date
        try:
            no_lat, no_lon = random_nearby_point(latitude, longitude)
            features = get_features_with_retry(no_lat, no_lon, event_date)
            rows.append({
                "event_id": index,
                "event_date": event_date.isoformat(),
                "latitude": no_lat,
                "longitude": no_lon,
                "landslide": 0,
                "sample_type": "candidate_control",
                **features,
            })
        except Exception as exc:
            print(f"  Could not process control point: {exc}")

    # Save dataset
    if not rows:
        raise RuntimeError("No satellite records collected. Check the errors above.")

    output = pd.DataFrame(rows)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(OUTPUT_FILE, index=False)

    # Results
    print("\n===================================")
    print("DATASET COLLECTION FINISHED")
    print("===================================")
    print(f"Records saved: {len(output)}")
    print(f"Output file: {OUTPUT_FILE}")

    print("\nLabel distribution:")
    print(output["landslide"].value_counts())

    print("\nMissing environmental measurements:")
    print(output[FEATURE_COLUMNS].isna().sum())

    print("\nFirst five records:")
    print(output.head().to_string(index=False))


# --------------------------------------------------
# RUN SCRIPT
# --------------------------------------------------

if __name__ == "__main__":
    main()