import pandas as pd
from pathlib import Path

# Project folder
BASE_DIR = Path(__file__).resolve().parent.parent

# Input dataset
INPUT_FILE = (
    BASE_DIR
    / "data"
    / "raw"
    / "Global_Landslide_Catalog_Export_rows.csv"
)

# Output folder and file
OUTPUT_DIR = BASE_DIR / "data" / "processed"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = OUTPUT_DIR / "landslide_events_clean.csv"

# Read the real landslide dataset
df = pd.read_csv(INPUT_FILE)

print("Original dataset:", df.shape)

# Keep the important columns
df = df[["event_date", "latitude", "longitude"]].copy()

# Convert columns to the correct formats
df["event_date"] = pd.to_datetime(
    df["event_date"],
    errors="coerce"
)

df["latitude"] = pd.to_numeric(
    df["latitude"],
    errors="coerce"
)

df["longitude"] = pd.to_numeric(
    df["longitude"],
    errors="coerce"
)

# Remove missing or invalid locations and dates
df = df.dropna(
    subset=["event_date", "latitude", "longitude"]
)

df = df[
    df["latitude"].between(-90, 90)
    & df["longitude"].between(-180, 180)
]

# Remove exact duplicate records
df = df.drop_duplicates()

# Save the cleaned dataset
df.to_csv(OUTPUT_FILE, index=False)

print("Cleaned dataset:", df.shape)
print("Saved to:", OUTPUT_FILE)
print("\nFirst five records:")
print(df.head().to_string(index=False))