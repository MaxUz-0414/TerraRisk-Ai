"""
MEMBER B OWNS THIS FILE  (machine learning). Part of the `risk` microservice.

Two scores:

predict_risk(features) -> int 0-100
    Flood-type risk. Uses services/risk/tr_risk/models/hazard_model.pkl when it exists; otherwise a
    transparent rule-based formula (also used by ml/train_model.py to create training labels).

predict_landslide(inputs) -> int 0-100 or None
    Landslide susceptibility from the trained model in services/risk/tr_risk/models/landslide_model.pkl
    (built by ml/build_dataset.py + ml/train_landslide_model.py). Returns None when the model
    file is missing or broken, so the site keeps working without it.
    The score is 100 x P(landslide). The model was trained on equal numbers of recorded
    landslides and random nearby control points, so treat it as a relative index.
"""
import logging
import math
from pathlib import Path

from tr_common.config import env_str

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).resolve().parent / "models"

# The flood model is trained on exactly these columns, in this order.
FEATURE_ORDER = [
    "upstream_slope_deg",
    "dist_to_river_m",
    "ndvi_trend_pct",
    "lst_peak_c",
    "soil_moisture_change_pct",
]

# Default input order of the landslide model (the saved bundle's own "features" list wins).
LANDSLIDE_FEATURES = ["ndvi", "lst_peak_c", "soil_moisture", "slope", "elevation"]

_model = None
_landslide = {"bundle": None, "mtime": None}


def _clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


def rule_based_score(f):
    """Transparent 0-100 score. Weights add up to 100."""
    score = (
        35 * _clamp(f["upstream_slope_deg"] / 40)
        + 25 * _clamp(1 - f["dist_to_river_m"] / 2000)
        + 15 * _clamp(-f["ndvi_trend_pct"] / 25)
        + 10 * _clamp((f["lst_peak_c"] - 25) / 15)
        + 15 * _clamp(-f["soil_moisture_change_pct"] / 25)
    )
    return int(round(score))


def _flood_path():
    return Path(env_str("FLOOD_MODEL_PATH") or MODELS_DIR / "hazard_model.pkl")


def _load_model():
    global _model
    path = _flood_path()
    if _model is None and path.exists():
        import joblib

        try:
            _model = joblib.load(path)
            logger.info("Loaded ML model from %s", path)
        except Exception:
            logger.exception("Could not load flood model from %s; using the formula", path)
    return _model


def predict_risk(features):
    model = _load_model()
    if model is None:
        return rule_based_score(features)
    row = [[features[k] for k in FEATURE_ORDER]]
    return int(max(0, min(100, round(float(model.predict(row)[0])))))


# --------------------------------------------------------------------------- landslide model
def _landslide_path():
    return Path(env_str("LANDSLIDE_MODEL_PATH") or MODELS_DIR / "landslide_model.pkl")


def _load_landslide():
    """Load the landslide bundle; reload automatically when the file is retrained."""
    path = _landslide_path()
    if not path.exists():
        _landslide.update(bundle=None, mtime=None)
        return None
    mtime = path.stat().st_mtime
    if _landslide["mtime"] != mtime:
        try:
            import joblib

            bundle = joblib.load(path)
            if not isinstance(bundle, dict):  # a bare estimator was saved
                bundle = {"model": bundle}
            if not hasattr(bundle.get("model"), "predict_proba"):
                raise ValueError("saved object has no predict_proba()")
            bundle.setdefault("features", LANDSLIDE_FEATURES)
            _landslide.update(bundle=bundle, mtime=mtime)
            logger.info("Loaded landslide model from %s (AUC %s)", path, bundle.get("auc"))
        except Exception:
            logger.exception("Could not load landslide model from %s", path)
            _landslide.update(bundle=None, mtime=mtime)
    return _landslide["bundle"]


def flood_model_info():
    """"trained" when hazard_model.pkl loaded, otherwise "formula"."""
    return {"kind": "trained" if _load_model() is not None else "formula"}


def landslide_model_info():
    """{"auc": float|None, "features": [...]} or None. Handy for the admin console."""
    bundle = _load_landslide()
    if bundle is None:
        return None
    return {"auc": bundle.get("auc"), "features": list(bundle["features"])}


def _to_float(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return math.nan
    return number if math.isfinite(number) else math.nan


def predict_landslide(inputs):
    """inputs: dict with the model's feature names. Missing values are allowed (the model fills them)."""
    bundle = _load_landslide()
    if bundle is None or not inputs:
        return None
    names = list(bundle["features"])
    values = [_to_float(inputs.get(name)) for name in names]
    if all(math.isnan(v) for v in values):
        return None
    try:
        try:
            import pandas as pd

            row = pd.DataFrame([values], columns=names)  # same column names the model was trained with
        except ImportError:
            row = [values]
        model = bundle["model"]
        classes = list(getattr(model, "classes_", [0, 1]))
        positive = classes.index(1) if 1 in classes else len(classes) - 1
        probability = float(model.predict_proba(row)[0][positive])
    except Exception:
        logger.exception("Landslide prediction failed")
        return None
    return int(round(_clamp(probability) * 100))
