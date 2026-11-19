"""
"What if" stress tests for the investor page.

Each scenario changes ONE input of the existing models (hotter summers, less vegetation, drier soil),
runs the same scoring as a normal analysis and reports how far the score moves.
These show how sensitive the score is. They are not forecasts.
"""
import copy
import logging

from .scoring import score_features
from .risk import risk_level

logger = logging.getLogger(__name__)


def _hotter(f):
    # Only the flood side reacts. The landslide model's temperature input reflects regional climate in its training
    # data (hotter = drier = fewer landslides), so pushing it up would give a misleading "hotter is safer" result.
    f["lst_peak_c"] += 2


def _greener_loss(f):
    f["ndvi_trend_pct"] -= 10
    inputs = f.get("landslide_inputs") or {}
    if inputs.get("ndvi") is not None:
        inputs["ndvi"] = round(inputs["ndvi"] * 0.9, 3)


def _drier(f):
    f["soil_moisture_change_pct"] -= 10
    inputs = f.get("landslide_inputs") or {}
    if inputs.get("soil_moisture") is not None:
        inputs["soil_moisture"] = round(inputs["soil_moisture"] * 0.9, 3)


SCENARIOS = [
    ("Summers 2 °C hotter", "Peak land temperature +2 °C", _hotter),
    ("Vegetation declines", "Plant cover trend 10 points worse", _greener_loss),
    ("Soil dries out", "Soil moisture change 10 points lower", _drier),
]


def stress_scenarios(features, base_score):
    """[{label, detail, score, delta, level}] or [] when the features are incomplete."""
    results = []
    for label, detail, change in SCENARIOS:
        try:
            changed = copy.deepcopy(features)
            change(changed)
            score = score_features(changed)[0]
        except Exception:  # missing keys on very old parcels: just skip the scenario
            logger.info("Scenario %r skipped", label, exc_info=True)
            continue
        results.append({"label": label, "detail": detail, "score": score,
                        "delta": score - base_score, "level": risk_level(score)})
    return results
