"""
MEMBER B OWNS THIS FILE  (advice text). Part of the `advisory` microservice.

generate_advice(features, score, persona) -> (items, source, note)
    items  : [{"label": "Immediate Action", "text": "..."}, ...]
    source : "gemini" or "template"
    note   : why templates were used (empty when Gemini answered)
Uses the Gemini API when GEMINI_API_KEY is set, otherwise (or on any error) built-in templates.
"""
import logging

import requests
from tr_common.config import env_str

PERSONA_GROUP = {"farmer": "farmer", "homebuyer": "homebuyer", "investor": "investor", "developer": "investor", "analyst": "investor"}

logger = logging.getLogger(__name__)

LABELS = ["Immediate Action", "Action Item", "Advisory", "Advisory"]


def generate_advice(features, score, persona):
    group = PERSONA_GROUP.get(persona, "investor")
    note = ""
    if env_str("GEMINI_API_KEY"):
        try:
            items = _gemini_advice(features, score, group)
            if items:
                return items, "gemini", ""
            note = "Gemini returned no usable lines."
        except Exception as exc:  # never let the LLM break an analysis
            logger.exception("Gemini advice failed; using template advice instead")
            note = f"Gemini request failed ({type(exc).__name__})."
    else:
        note = "GEMINI_API_KEY is not set."
    return _template_advice(features, score, group), "template", note


FOCUS = {
    "farmer": "Focus on crops and soil: drought-tolerant seed varieties, swales or contour ditches, irrigation and water storage, erosion.",
    "homebuyer": ("Focus on living there: ask about flood history and drainage before signing, "
                  "expected cooling costs in summer, insurance quotes. Do not quote percentage savings or costs you were not given."),
    "investor": ("Focus on the asset: alternative logistics routes, reinforced drainage, insurance exclusions, "
                 "stress-testing the business case. Land subsidence is not measured, do not claim it."),
}


def _extra_sentence(features):
    """Optional satellite metrics (older parcels may not have them)."""
    bits = []
    for key, text in (
        ("rain_anomaly_pct", "Rain over the last 12 months versus normal: {:+.0f}%."),
        ("ndwi_change", "Plant water content change: {:+.2f}."),
        ("built_up_pct", "Built-up land nearby: {:.0f}%."),
        ("hand_m", "Height above the nearest drainage channel: {:.1f} m."),
        ("lst_anomaly_c", "Summer land temperature versus earlier years: {:+.1f} C."),
    ):
        value = features.get(key)
        if isinstance(value, (int, float)) and value == value:
            bits.append(text.format(value))
    return (" ".join(bits) + "\n") if bits else ""


def _gemini_advice(features, score, group):
    prompt = (
        f"You are a land climate-risk advisor speaking to a {group}.\n{FOCUS.get(group, '')}\n"
        f"Composite risk score: {score}%. Upstream slope: {features['upstream_slope_deg']} degrees. "
        f"Distance to river: {features['dist_to_river_m']} m. 5-year vegetation change: {features['ndvi_trend_pct']}%. "
        f"Peak summer land temperature: {features['lst_peak_c']} C. Soil moisture change: {features['soil_moisture_change_pct']}%.\n"
        f"{_parts_sentence(features)}{_extra_sentence(features)}"
        "Reply with exactly 4 lines, each formatted 'Label: advice'. Labels in order: "
        "Immediate Action, Action Item, Advisory, Advisory. Each advice is one plain sentence under 25 words. No markdown."
    )
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{env_str('GEMINI_MODEL') or 'gemini-3.5-flash-lite'}:generateContent"
    resp = requests.post(
        url,
        headers={"x-goog-api-key": env_str("GEMINI_API_KEY"), "Content-Type": "application/json"},
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=20,
    )
    resp.raise_for_status()
    text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    items = []
    for line in text.splitlines():
        if ":" in line:
            label, advice = line.split(":", 1)
            items.append({"label": label.strip(" *-"), "text": advice.strip()})
    return items[:4]


def _parts_sentence(features):
    """Tell Gemini how the score splits into flood-type and landslide parts (when the landslide model ran)."""
    parts = features.get("score_parts") or {}
    if parts.get("landslide") is None:
        return ""
    return (f"Flood-type score: {parts.get('flood')}%. Landslide susceptibility score: {parts['landslide']}% "
            "(AI model, a relative index). Mention landslide risk when it is the larger part.\n")


def _template_advice(f, score, group):
    slope, dist, lst = f["upstream_slope_deg"], f["dist_to_river_m"], f["lst_peak_c"]
    rain = f.get("rain_anomaly_pct")
    if group == "farmer":
        texts = [
            "Reinforce terrace boundaries and add perimeter swales to slow upstream runoff."
            if slope >= 25 else "Keep drainage channels clear before the next rainy season.",
            "Check downstream erosion points inside the buffer zone after each major storm.",
            f"Reassess crop insurance premiums based on a {score}% risk score.",
            "Limit fertilizer application during high-probability rain events.",
        ]
        if isinstance(rain, (int, float)) and rain <= -15:
            texts[3] = "Rain is well below normal: choose drought-tolerant seeds and secure water storage early."
    elif group == "homebuyer":
        texts = [
            f"Ask for the flood history: the nearest runoff path is about {dist} m away."
            if dist < 800 else "Ask the seller about past water damage and local drainage upgrades.",
            f"Budget for higher cooling costs; peak summer land temperature reaches {lst} C.",
            "Check regional stormwater infrastructure before signing a lease or mortgage.",
            f"Compare insurance quotes, since the composite risk score is {score}%.",
        ]
    else:
        texts = [
            "Commission a slope-stability survey of the upstream access corridor."
            if slope >= 30 else "Inspect access roads and culverts upstream before committing capital.",
            "Plan secondary logistics routes and reinforced drainage channels.",
            f"Stress-test the business case against a {score}% climate risk score.",
            "Review insurance exclusions for flood and landslide events.",
        ]
    return [{"label": label, "text": text} for label, text in zip(LABELS, texts)]
