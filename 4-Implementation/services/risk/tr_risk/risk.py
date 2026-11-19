"""Pure helpers shared by views, templates, advice and PDF reports (no Django imports)."""
LEVEL_LABELS = {"low": "Low Risk", "medium": "Moderate Risk", "high": "High Risk"}

# Which advice/headline family each persona belongs to.
PERSONA_GROUP = {
    "farmer": "farmer",
    "homebuyer": "homebuyer",
    "investor": "investor",
    "developer": "investor",
    "analyst": "investor",
}


def risk_level(score):
    """Map a 0-100 score to 'low' / 'medium' / 'high'."""
    return "low" if score < 40 else "medium" if score < 65 else "high"
