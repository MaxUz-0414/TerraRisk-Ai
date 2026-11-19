"""Composite risk score and hazard cards (moved here from the old analysis/services/pipeline.py)."""
from . import ml

# How much each model counts in the composite score when the landslide model is available.
FLOOD_WEIGHT = 0.5
LANDSLIDE_WEIGHT = 0.5


def _level(score):
    return "high" if score >= 65 else "medium" if score >= 40 else "low"


def build_hazards(f, landslide_score=None):
    """Dashboard cards derived from the features."""
    slope, dist = f["upstream_slope_deg"], f["dist_to_river_m"]
    cards = [
        {
            "label": "Upstream Slope",
            "value": f"{slope}°",
            "note": "Severe flash flood potential" if slope >= 30 else "Elevated runoff speed" if slope >= 20 else "Gentle terrain",
            "level": "high" if slope >= 30 else "medium" if slope >= 20 else "low",
        },
        {
            "label": "Distance to Riverbed",
            "value": f"{dist} m",
            "note": "High risk zone" if dist < 500 else "Watch zone" if dist < 1500 else "Safe distance",
            "level": "high" if dist < 500 else "medium" if dist < 1500 else "low",
        },
        {
            "label": "Nearby Active Siltation",
            "value": f["siltation"],
            "note": "Sediment build-up near channels",
            "level": {"High": "high", "Moderate": "medium"}.get(f["siltation"], "low"),
        },
        {
            "label": "Soil Saturation",
            "value": f["soil_saturation"],
            "note": "Ability of the ground to absorb more rain",
            "level": {"Extreme": "high", "High": "high", "Moderate": "medium"}.get(f["soil_saturation"], "low"),
        },
    ]
    if landslide_score is not None:
        level = _level(landslide_score)
        cards.append({
            "label": "Landslide Susceptibility",
            "value": f"{landslide_score}%",
            "note": {"high": "Similar to past landslide sites", "medium": "Some landslide-prone conditions",
                     "low": "Unlike past landslide sites"}[level] + " (AI model)",
            "level": level,
        })
    return cards


def score_features(features):
    """(composite, flood part, landslide part) for a feature dict. Also used by the stress scenarios."""
    flood_score = ml.predict_risk(features)
    landslide_score = ml.predict_landslide(features.get("landslide_inputs"))
    if landslide_score is None:
        return flood_score, flood_score, None
    return int(round(FLOOD_WEIGHT * flood_score + LANDSLIDE_WEIGHT * landslide_score)), flood_score, landslide_score
