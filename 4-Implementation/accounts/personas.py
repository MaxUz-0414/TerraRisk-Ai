"""Text and pictures for each persona (landing cards and the signup page)."""
from django.templatetags.static import static

PERSONAS = {
    "farmer": {
        "title": "Farmer",
        "headline": "Protect your fields from what flows downhill",
        "blurb": "See how slope, rivers and soil moisture upstream of your land can affect your crops, and get a plan for each season.",
        "bullets": ["Crop yield analysis", "Weather patterns", "Water stress detection"],
        "image": "img/personas/farmer.svg",
    },
    "homebuyer": {
        "title": "Homebuyer",
        "headline": "Know the land before you buy the house",
        "blurb": "Check flood exposure, heat and nearby hazards for any address before you sign, and compare homes with a risk score.",
        "bullets": ["Flood and fire risk assessment", "Property vulnerability", "Future-proofing"],
        "image": "img/personas/homebuyer.svg",
    },
    "investor": {
        "title": "Commercial Investor",
        "headline": "Put a physical-risk score on every asset",
        "blurb": "Screen land and property portfolios for climate risk, track resilience over time and back decisions with a PDF certificate.",
        "bullets": ["Portfolio analysis", "Physical risk scores", "Infrastructure health"],
        "image": "img/personas/investor.svg",
    },
}
ALIASES = {"developer": "investor", "analyst": "investor"}  # no own picture, so they share the investor one


def persona_info(key):
    return PERSONAS[ALIASES.get(key, key)]


def persona_cards():
    """The three cards on the landing page."""
    return [{"key": key, **info, "image_url": static(info["image"])} for key, info in PERSONAS.items()]


def persona_json():
    """Everything the signup page needs to swap the picture when the dropdown changes."""
    return {
        key: {
            "title": persona_info(key)["title"],
            "headline": persona_info(key)["headline"],
            "blurb": persona_info(key)["blurb"],
            "image": static(persona_info(key)["image"]),
        }
        for key in ("farmer", "homebuyer", "investor", "developer", "analyst")
    }
