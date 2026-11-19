"""The persona-specific headline metric shown under the gauge (pure functions)."""
from .persona_view import drought_index, heat_index
from .risk import PERSONA_GROUP, risk_level


def _clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


GRADES = [(10, "A"), (20, "A-"), (30, "B+"), (40, "B"), (50, "B-"), (60, "C+"), (70, "C"), (80, "D")]


def persona_headline(features, score, persona):
    """Return {"label", "value", "note", "level"} for this persona."""
    group = PERSONA_GROUP.get(persona, "investor")
    if group == "farmer":
        moisture = features["soil_moisture_change_pct"]
        value = drought_index(features) or 0
        return {
            "label": "Drought Vulnerability",
            "value": f"{value}%",
            "level": risk_level(value),
            "note": f"Soil moisture {moisture:+.0f}% against the 5-year average",
        }
    if group == "homebuyer":
        lst = features["lst_peak_c"]
        value = heat_index(features) or 0
        return {
            "label": "Urban Heat Vulnerability",
            "value": f"{value}/100",
            "level": risk_level(value),
            "note": f"Peak summer land temperature reaches {lst} °C",
        }
    grade = next((g for limit, g in GRADES if score < limit), "F")
    return {
        "label": "Climate Resilience Grade",
        "value": grade,
        "level": risk_level(score),
        "note": "Based on the composite risk score",
    }
