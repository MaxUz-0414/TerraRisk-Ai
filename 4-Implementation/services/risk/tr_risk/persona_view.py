"""
Persona-specific results page: what each kind of user sees after an analysis.

Everything here is computed from the stored `parcel.features` at display time, so it needs no database
migration and old saved parcels keep working (new satellite metrics are optional and may be missing).
Pure Python on purpose: no Django imports, so it is easy to test and to read.

build_persona_view(features, score, persona) returns a dict with:
    group       "farmer" | "homebuyer" | "investor"
    question    the question this page answers for that person
    verdict     {level, title, text}               one plain-language conclusion
    cards       [{label, value, level, note}]      the persona's own metrics
    factors     [{label, value, level, help}]      "why this score", strongest first
    checklist   {title, subtitle, items}           what to do / ask / check
    flags       [{level, flag, evidence, action}]  investor due-diligence table (empty for others)
    charts      ["ndvi", "rain", ...]              which charts to draw
    notes       [str]                              honest data caveats
"""
import math

from .risk import PERSONA_GROUP, risk_level


# --------------------------------------------------------------------------- small helpers
def _clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


def _num(features, key):
    """A feature as a float, or None when it is missing (older parcels) or not a number."""
    value = features.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    return float(value)


def _blend(parts):
    """Weighted average of (weight, 0..1 value) pairs, skipping missing values. Returns 0..100 or None."""
    parts = [(w, v) for w, v in parts if v is not None]
    total = sum(w for w, _ in parts)
    if not total:
        return None
    return round(100 * sum(w * v for w, v in parts) / total)


def _level(index):
    return risk_level(index)


def ndvi_now(features):
    """Average greenness (NDVI) of the most recent year in the stored monthly series, or None."""
    years = (features.get("ndvi_series") or {}).get("years") or {}
    for year in sorted(years, reverse=True):
        values = [v for v in years[year] if isinstance(v, (int, float))]
        if values:
            return round(sum(values) / len(values), 2)
    return None


# --------------------------------------------------------------------------- indices (0 = no concern, 100 = severe)
def drought_index(features):
    """Dry-land vulnerability: drying soil, fading vegetation, missing rain, falling plant water."""
    moisture = _num(features, "soil_moisture_change_pct")
    trend = _num(features, "ndvi_trend_pct")
    rain = _num(features, "rain_anomaly_pct")
    ndwi = _num(features, "ndwi_change")
    return _blend([
        (0.35, _clamp(-moisture / 25) if moisture is not None else None),
        (0.25, _clamp(-trend / 25) if trend is not None else None),
        (0.25, _clamp(-rain / 35) if rain is not None else None),
        (0.15, _clamp(-ndwi / 0.10) if ndwi is not None else None),
    ])


def runoff_index(features):
    """How hard water rushes down onto the land: steep ground, a big catchment above, a wet year."""
    slope = _num(features, "upstream_slope_deg")
    area = _num(features, "upstream_area_km2")
    rain = _num(features, "rain_anomaly_pct")
    return _blend([
        (0.55, _clamp((slope - 8) / 27) if slope is not None else None),
        (0.30, _clamp(math.log10(1 + max(area, 0)) / 3.2) if area is not None else None),
        (0.15, _clamp(rain / 40) if rain is not None else None),
    ])


def flood_exposure_index(features):
    """Flooding: how close the river is and how low the ground sits above the nearest channel."""
    dist = _num(features, "dist_to_river_m")
    hand = _num(features, "hand_m")
    return _blend([
        (0.6 if hand is not None else 1.0, _clamp((1500 - dist) / 1400) if dist is not None else None),
        (0.4, _clamp((15 - hand) / 14) if hand is not None else None),
    ])


def heat_index(features):
    """Heat stress: hot summers, getting hotter, lots of concrete, little greenery."""
    lst = _num(features, "lst_peak_c")
    anomaly = _num(features, "lst_anomaly_c")
    built = _num(features, "built_up_pct")
    green = ndvi_now(features)
    return _blend([
        (0.50, _clamp((lst - 25) / 15) if lst is not None else None),
        (0.15, _clamp(anomaly / 3) if anomaly is not None else None),
        (0.25, _clamp(built / 60) if built is not None else None),
        (0.10, _clamp((0.5 - green) / 0.4) if green is not None else None),
    ])


def landslide_index(features):
    """The AI landslide score when the model ran, otherwise a rough slope-only estimate."""
    parts = features.get("score_parts") or {}
    if isinstance(parts.get("landslide"), (int, float)):
        return int(parts["landslide"]), True
    slope = _num(features, "upstream_slope_deg")
    if slope is None:
        return None, False
    return round(100 * _clamp((slope - 10) / 25)), False


# --------------------------------------------------------------------------- factors ("why this score")
def build_factors(features):
    """Every concern on one 0-100 scale, strongest first, with a one-line explanation."""
    slide, from_model = landslide_index(features)
    rows = [
        ("flood", "Flooding", flood_exposure_index(features), "Closeness to the river and how low the ground is."),
        ("landslide", "Landslides", slide,
         "AI model trained on past landslides." if from_model else "Rough estimate from the slope only."),
        ("heat", "Summer heat", heat_index(features), "Hot summers, concrete and lack of greenery."),
        ("drought", "Dryness", drought_index(features), "Drying soil, fading plants and low rainfall."),
        ("runoff", "Runoff from above", runoff_index(features), "Steep ground and a large catchment uphill."),
    ]
    factors = [
        {"key": key, "label": label, "value": value, "level": _level(value), "help": hint}
        for key, label, value, hint in rows if value is not None
    ]
    factors.sort(key=lambda f: f["value"], reverse=True)
    return factors


def _driver_phrase(key, features):
    dist, lst = _num(features, "dist_to_river_m"), _num(features, "lst_peak_c")
    moisture = _num(features, "soil_moisture_change_pct")
    slide, _ = landslide_index(features)
    return {
        "flood": f"flooding (the river is about {int(dist)} m away)" if dist is not None else "flooding",
        "landslide": f"landslides (susceptibility {slide}%)" if slide is not None else "landslides",
        "heat": f"summer heat (peaks near {lst:.0f} °C)" if lst is not None else "summer heat",
        "drought": f"dry conditions (soil moisture {moisture:+.0f}% vs earlier years)" if moisture is not None else "dry conditions",
        "runoff": "fast runoff from higher ground",
    }[key]


# --------------------------------------------------------------------------- verdict
VERDICT_TITLES = {
    "farmer": {"low": "Good conditions for farming", "medium": "Farmable, with water and runoff to manage",
               "high": "High risk for crops and soil"},
    "homebuyer": {"low": "A comfortable place to live", "medium": "Livable with precautions",
                  "high": "Think twice before buying here"},
    "investor": {"low": "Low physical climate risk", "medium": "Investable with conditions",
                 "high": "High physical risk: price it in"},
}
QUESTIONS = {
    "farmer": "Is this land safe for my crops and soil?",
    "homebuyer": "Is it safe and comfortable to live here?",
    "investor": "How much physical climate risk does this asset carry?",
}


def build_verdict(group, score, factors, features):
    level = _level(score)
    strong = [f for f in factors if f["value"] >= 40]
    if not strong:
        text = "No single risk stands out. The score is driven by small contributions from several factors."
    else:
        first = _driver_phrase(strong[0]["key"], features)
        second = f" Next: {_driver_phrase(strong[1]['key'], features)}." if len(strong) > 1 else ""
        if level == "low" and strong[0]["value"] >= 65:
            text = f"The overall score is low, but one thing stands out: {first}.{second}"
        else:
            text = f"The biggest concern is {first}.{second}"
    return {"level": level, "title": VERDICT_TITLES[group][level], "text": text}


# --------------------------------------------------------------------------- cards
def _card(label, value, level, note):
    return {"label": label, "value": value, "level": level, "note": note}


def _farmer_cards(features):
    cards = []
    drought = drought_index(features)
    moisture = _num(features, "soil_moisture_change_pct")
    if drought is not None:
        note = f"Soil moisture {moisture:+.0f}% compared with earlier years." if moisture is not None else "From vegetation and soil data."
        cards.append(_card("Drought vulnerability", f"{drought}%", _level(drought), note))
    rain, total = _num(features, "rain_anomaly_pct"), _num(features, "rain_12m_mm")
    if rain is not None:
        level = "high" if rain <= -15 else "medium" if (rain <= -5 or rain >= 30) else "low"
        word = "drier" if rain < 0 else "wetter"
        cards.append(_card("Rain vs normal", f"{rain:+.0f}%", level,
                           f"{int(total)} mm in the last 12 months, {abs(rain):.0f}% {word} than usual." if total is not None else f"{abs(rain):.0f}% {word} than usual."))
    trend = _num(features, "ndvi_trend_pct")
    if trend is not None:
        level = "high" if trend <= -15 else "medium" if trend <= -5 else "low"
        cards.append(_card("Crop greenness trend", f"{trend:+.0f}%", level, "Vegetation (NDVI) compared with 4 years ago."))
    change, now = _num(features, "ndwi_change"), _num(features, "ndwi_now")
    if change is not None:
        level = "high" if change <= -0.06 else "medium" if change <= -0.02 else "low"
        word = "Drying" if change <= -0.02 else "Wetter" if change >= 0.02 else "Stable"
        cards.append(_card("Plant water content", word, level, f"Water index {now:.2f}, change {change:+.2f} since 4 years ago." if now is not None else f"Change {change:+.2f} since 4 years ago."))
    runoff = runoff_index(features)
    slope, area = _num(features, "upstream_slope_deg"), _num(features, "upstream_area_km2")
    if runoff is not None:
        bits = [f"Slope {slope:.0f}°"] if slope is not None else []
        if area is not None:
            bits.append(f"{area:.1f} km² of land drains onto this parcel")
        cards.append(_card("Runoff from upslope", f"{runoff}%", _level(runoff), ", ".join(bits) + "." if bits else "Steepness and catchment size."))
    saturation = features.get("soil_saturation")
    if saturation:
        level = {"Extreme": "high", "High": "high", "Moderate": "medium"}.get(saturation, "low")
        cards.append(_card("Soil saturation", saturation, level, "How much more rain the ground can take."))
    return cards


def _homebuyer_cards(features):
    cards = []
    dist, hand = _num(features, "dist_to_river_m"), _num(features, "hand_m")
    flood = flood_exposure_index(features)
    if flood is not None and dist is not None:
        cards.append(_card("Flood exposure", f"{int(dist)} m", _level(flood), "Distance to the nearest river or water body."))
    if hand is not None:
        level = "high" if hand < 3 else "medium" if hand < 10 else "low"
        note = ("Low ground: rain water tends to collect here." if hand < 3 else
                "Somewhat low: check how the lot drains." if hand < 10 else "Sits well above the nearest drainage channel.")
        cards.append(_card("Rain water pooling", f"{hand:.1f} m", level, f"Height above the nearest channel. {note}"))
    lst, anomaly = _num(features, "lst_peak_c"), _num(features, "lst_anomaly_c")
    if lst is not None:
        level = "high" if lst >= 36 else "medium" if lst >= 30 else "low"
        extra = f" {abs(anomaly):.1f} °C {'hotter' if anomaly > 0 else 'cooler'} than in earlier years." if anomaly is not None and abs(anomaly) >= 0.3 else ""
        cards.append(_card("Summer heat", f"{lst:.0f} °C", level, f"Peak land surface temperature.{extra}"))
    built = _num(features, "built_up_pct")
    if built is not None:
        level = "high" if built >= 40 else "medium" if built >= 15 else "low"
        cards.append(_card("Concrete and buildings", f"{built:.0f}%", level, "Built-up land within 500 m. More paving means more heat and runoff."))
    green = ndvi_now(features)
    if green is not None:
        level = "low" if green >= 0.5 else "medium" if green >= 0.3 else "high"
        word = "Lots of greenery" if green >= 0.5 else "Some greenery" if green >= 0.3 else "Little greenery"
        cards.append(_card("Green space", f"{green:.2f}", level, f"{word} nearby (vegetation index, 0 to 1)."))
    slide, from_model = landslide_index(features)
    slope = _num(features, "upstream_slope_deg")
    if slide is not None:
        note = f"{'AI landslide index' if from_model else 'Slope-based estimate'}." + (f" Terrain slope about {slope:.0f}°." if slope is not None else "")
        cards.append(_card("Landslide and slope", f"{slide}%", _level(slide), note))
    return cards


def _investor_cards(features):
    cards = []
    flood = flood_exposure_index(features)
    dist, hand = _num(features, "dist_to_river_m"), _num(features, "hand_m")
    if flood is not None:
        bits = []
        if dist is not None:
            bits.append(f"river {int(dist)} m away")
        if hand is not None:
            bits.append(f"{hand:.1f} m above the nearest channel")
        cards.append(_card("Flood and water", f"{flood}%", _level(flood), (", ".join(bits) + ".").capitalize() if bits else "Water proximity."))
    slide, from_model = landslide_index(features)
    if slide is not None:
        cards.append(_card("Landslide", f"{slide}%", _level(slide), "AI model trained on past landslides." if from_model else "Slope-based estimate; the AI model was not available."))
    heat = heat_index(features)
    lst = _num(features, "lst_peak_c")
    if heat is not None:
        cards.append(_card("Heat stress", f"{heat}%", _level(heat), f"Peak land temperature {lst:.0f} °C." if lst is not None else "Heat and land cover."))
    rain, total = _num(features, "rain_anomaly_pct"), _num(features, "rain_12m_mm")
    if rain is not None:
        level = "high" if abs(rain) >= 30 else "medium" if abs(rain) >= 15 else "low"
        word = "drier" if rain < 0 else "wetter"
        cards.append(_card("Rainfall extremes", f"{rain:+.0f}%", level, f"Last 12 months were {abs(rain):.0f}% {word} than normal" + (f" ({int(total)} mm)." if total is not None else ".")))
    runoff = runoff_index(features)
    if runoff is not None:
        cards.append(_card("Terrain and runoff", f"{runoff}%", _level(runoff), "Steep ground and catchment size uphill."))
    built = _num(features, "built_up_pct")
    if built is not None:
        cards.append(_card("Built-up context", f"{built:.0f}%", "low" if built < 40 else "medium", "Share of built-up land within 500 m (existing infrastructure nearby)."))
    return cards


# --------------------------------------------------------------------------- checklists
def _farmer_checklist(features):
    items = []
    drought, runoff = drought_index(features), runoff_index(features)
    rain, trend, dist = _num(features, "rain_anomaly_pct"), _num(features, "ndvi_trend_pct"), _num(features, "dist_to_river_m")
    if drought is not None and drought >= 40:
        items.append("Choose drought-tolerant seed varieties and plan drip or deficit irrigation.")
    if runoff is not None and runoff >= 40:
        items.append("Dig swales or contour ditches along the upslope edge to slow runoff and keep the soil in place.")
    if rain is not None and rain <= -15:
        items.append("Rain is well below normal. Secure water storage and check your irrigation source early.")
    if rain is not None and rain >= 25:
        items.append("This was a wet year. Check drainage and watch for waterlogging and erosion.")
    if trend is not None and trend <= -10:
        items.append("Vegetation has been declining. Test the soil and look for erosion, pests or over-grazing.")
    if dist is not None and dist < 500:
        items.append("Keep stores and equipment away from the river strip; it floods first.")
    items.append("Check soil moisture every week in the dry season; a cheap probe is enough.")
    items.append("Keep drainage channels clear before the next rainy season.")
    return {"title": "Before the next season", "subtitle": "Practical steps based on this parcel's data.", "items": items[:6]}


def _homebuyer_checklist(features):
    items = []
    flood, hand, built = flood_exposure_index(features), _num(features, "hand_m"), _num(features, "built_up_pct")
    lst, slide, slope = _num(features, "lst_peak_c"), landslide_index(features)[0], _num(features, "upstream_slope_deg")
    dist = _num(features, "dist_to_river_m")
    if (flood is not None and flood >= 40) or (dist is not None and dist < 800):
        items.append("Ask about flood history and request the official flood-zone map for this address.")
        items.append("Get a flood-insurance quote before you make an offer.")
    if hand is not None and hand < 10:
        items.append("Check where rain water goes: look at the lowest point of the lot, the drains and the ground-floor level.")
    if (lst is not None and lst >= 32) or (heat_index(features) or 0) >= 40:
        items.append("Plan for summer heat: shade trees, insulation and cooling. Ask for last summer's energy bills.")
    if built is not None and built >= 40:
        items.append("The area is heavily paved. Ask about stormwater drains and how hot it gets in summer.")
    if (slide is not None and slide >= 40) or (slope is not None and slope >= 20):
        items.append("Ask for a slope-stability check, especially after heavy rain.")
    items.append("Visit after heavy rain to see how water behaves around the property.")
    items.append("Compare insurance quotes before you sign.")
    return {"title": "Ask before you buy", "subtitle": "Questions for the seller, agent or inspector, based on this place.", "items": items[:6]}


def _investor_checklist(features):
    items = []
    flood, slide = flood_exposure_index(features), landslide_index(features)[0]
    if flood is not None and flood >= 40:
        items.append("Commission a flood study and price flood cover into the business case.")
    if slide is not None and slide >= 40:
        items.append("Commission a slope-stability survey of the site and the access roads.")
    items.append("Plan alternative logistics routes and reinforced drainage so operations can continue in bad weather.")
    items.append("Review insurance exclusions for flood and landslide events.")
    items.append("Re-run this assessment every year and watch the trend.")
    return {"title": "Next steps for due diligence", "subtitle": "What a careful investor would do next.", "items": items[:6]}


# --------------------------------------------------------------------------- investor flags
def build_flags(features):
    flags = []
    flood, slide, heat = flood_exposure_index(features), landslide_index(features)[0], heat_index(features)
    runoff, rain = runoff_index(features), _num(features, "rain_anomaly_pct")
    dist, hand = _num(features, "dist_to_river_m"), _num(features, "hand_m")
    slope, lst = _num(features, "upstream_slope_deg"), _num(features, "lst_peak_c")

    def add(index, flag, evidence, action):
        if index is not None and index >= 40:
            flags.append({"level": _level(index), "flag": flag, "evidence": evidence, "action": action, "_v": index})

    ev = []
    if dist is not None:
        ev.append(f"river {int(dist)} m away")
    if hand is not None:
        ev.append(f"{hand:.1f} m above nearest channel")
    add(flood, "Flood and water proximity", ", ".join(ev).capitalize() or "Water proximity",
        "Commission a flood study; check insurance and drainage.")
    add(slide, "Landslide susceptibility", f"{slide}% AI index" + (f", slope {slope:.0f}°" if slope is not None else ""),
        "Survey slope stability on site and along access roads. Road-level landslide risk is not measured here.")
    add(runoff, "Runoff from higher ground", f"Runoff index {runoff}%", "Check culverts, ditches and drainage capacity.")
    add(heat, "Heat stress", f"Peak land temperature {lst:.0f} °C" if lst is not None else f"Heat index {heat}%",
        "Consider cooling load and worker conditions in the operating plan.")
    if rain is not None and abs(rain) >= 25:
        flags.append({"level": "medium", "flag": "Unusual rainfall year", "evidence": f"{rain:+.0f}% versus normal",
                      "action": "Check whether the last year was typical before relying on it.", "_v": abs(rain)})
    flags.sort(key=lambda f: f["_v"], reverse=True)
    for f in flags:
        del f["_v"]
    if not flags:
        flags.append({"level": "low", "flag": "No major flags", "evidence": "All measured factors are below the warning level.",
                      "action": "Keep monitoring once a year."})
    return flags


# --------------------------------------------------------------------------- notes
def build_notes(group, features):
    notes = []
    missing = [name for key, name in (("rain_anomaly_pct", "rainfall"), ("ndwi_change", "plant water"),
                                      ("built_up_pct", "built-up land"), ("hand_m", "terrain drainage")) if _num(features, key) is None]
    if missing:
        notes.append("Not available for this parcel: " + ", ".join(missing) + ". The page uses what is available.")
    notes.append("Soil moisture comes from an 11 km grid, so treat it as a regional hint, not a measurement of this parcel.")
    if group == "investor":
        notes.append("Land subsidence and road-by-road landslide risk are not measured in this version.")
    notes.append("These are screening indicators from satellite data, not an engineering, legal or insurance opinion.")
    return notes


# --------------------------------------------------------------------------- main entry
CHARTS = {"farmer": ["ndvi", "rain"], "homebuyer": ["lst", "ndvi"], "investor": ["rain", "lst"]}
CARD_BUILDERS = {"farmer": _farmer_cards, "homebuyer": _homebuyer_cards, "investor": _investor_cards}
CHECKLISTS = {"farmer": _farmer_checklist, "homebuyer": _homebuyer_checklist, "investor": _investor_checklist}


def build_persona_view(features, score, persona):
    group = PERSONA_GROUP.get(persona, "investor")
    features = features or {}
    factors = build_factors(features)
    charts = [c for c in CHARTS[group] if _chart_has_data(c, features)]
    return {
        "group": group,
        "question": QUESTIONS[group],
        "verdict": build_verdict(group, score, factors, features),
        "cards": CARD_BUILDERS[group](features),
        "factors": factors[:5],
        "checklist": CHECKLISTS[group](features),
        "flags": build_flags(features) if group == "investor" else [],
        "charts": charts,
        "notes": build_notes(group, features),
    }


def _chart_has_data(name, features):
    if name == "ndvi":
        return bool((features.get("ndvi_series") or {}).get("years"))
    if name == "lst":
        return bool((features.get("lst_series") or {}).get("average"))
    if name == "rain":
        return bool((features.get("rain_series") or {}).get("current"))
    return False
