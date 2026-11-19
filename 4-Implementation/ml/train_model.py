"""
MEMBER B: train and export the model.   Run from the project root:  python ml/train_model.py

Right now the labels come from the rule-based formula plus noise, because there is no
ready-made dataset that maps these features to a risk score. Replace `make_dataset()` with
real data (e.g. sampled GEE features at known flood/landslide locations) when you have it,
and say honestly in your report how the labels were created.
"""
import sys
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import r2_score
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parent.parent
# The models belong to the `risk` microservice (services/risk). Its code needs the shared library next to it.
sys.path[:0] = [str(ROOT / "services" / "common"), str(ROOT / "services" / "risk")]
from tr_risk.ml import FEATURE_ORDER, rule_based_score  # noqa: E402

RANGES = {
    "upstream_slope_deg": (0, 45),
    "dist_to_river_m": (50, 3000),
    "ndvi_trend_pct": (-30, 10),
    "lst_peak_c": (20, 45),
    "soil_moisture_change_pct": (-30, 10),
}


def make_dataset(n=4000, seed=42):
    rng = np.random.default_rng(seed)
    X = np.column_stack([rng.uniform(*RANGES[k], n) for k in FEATURE_ORDER])
    y = np.array([rule_based_score(dict(zip(FEATURE_ORDER, row))) for row in X], dtype=float)
    y = np.clip(y + rng.normal(0, 4, n), 0, 100)
    return X, y


if __name__ == "__main__":
    X, y = make_dataset()
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = RandomForestRegressor(n_estimators=100, max_depth=8, random_state=42).fit(X_train, y_train)
    print(f"R^2 on held-out data: {r2_score(y_test, model.predict(X_test)):.3f}")
    out = ROOT / "services" / "risk" / "tr_risk" / "models" / "hazard_model.pkl"
    out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, out)
    print(f"Saved {out}")
    print("Rebuild the risk image (docker compose up -d --build risk) so the service uses the new file.")
