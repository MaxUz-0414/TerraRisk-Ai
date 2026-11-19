"""Turns a user message into a reply: match an intent, fill in personal details, add buttons.

The web app sends a `context` with everything personal (balance text, support email, demo flags), so this service
never needs to know who the user is.
"""
from . import engine, llm
from .knowledge import INTENTS

BY_ID = {intent["id"]: intent for intent in INTENTS}
DEFAULT_SUGGESTIONS = ["How do I start?", "What does the risk score mean?", "How does pricing work?", "Contact support"]


def fill(text, context):
    """Replace {placeholders} with real values from the context."""
    context = context or {}
    data_mode = (
        "This site is currently running in DEMO mode: the numbers you see are generated examples, not real satellite readings."
        if context.get("demo_data") else "This site is using live satellite data."
    )
    payments = (
        "Checkout is running in demo mode: pressing the button activates your plan but no money or card details are taken."
        if context.get("demo_payments", True) else "Payments are processed securely by our payment provider; we never see or store your card number."
    )
    values = {
        "{email}": context.get("support_email", "support@terrarisk.ai"), "{free}": str(context.get("free_searches", 5)),
        "{balance}": context.get("balance") or "Sign in to see how many searches you have left.",
        "{data_mode}": data_mode, "{payments}": payments,
    }
    for token, value in values.items():
        text = text.replace(token, value)
    return text


def _links(intent):
    """[{"label", "route"}]  route is a page name like "signup" or "landing#team"; the web app turns it into a URL."""
    return [{"label": label, "route": route} for label, route in intent.get("links", [])]


def _knowledge_text():
    return "\n".join(f"- {i['title']}: {i['answer']}" for i in INTENTS if i["id"] != "off_topic")


def answer(message, context=None):
    """Return {"reply", "links", "suggestions", "unanswered"}."""
    intent_id, score = engine.get_model(INTENTS).predict(message)
    if score >= engine.THRESHOLD:
        intent = BY_ID[intent_id]
        return {"reply": fill(intent["answer"], context), "links": _links(intent), "unanswered": False,
                "suggestions": DEFAULT_SUGGESTIONS if intent_id in ("greeting", "off_topic") else []}

    # The trained model is not sure. Try Gemini (if configured), otherwise admit it.
    email = (context or {}).get("support_email", "support@terrarisk.ai")
    generated = llm.ask_gemini(message, fill(_knowledge_text(), context), email)
    if generated:
        return {"reply": generated, "links": [{"label": "Contact support", "route": "support"}], "suggestions": [], "unanswered": True}
    return {
        "reply": fill("I'm not sure about that one yet. Try asking about the map, risk scores, PDF reports, plans or your account, or email the team at {email}.", context),
        "links": [{"label": "Contact support", "route": "support"}], "suggestions": DEFAULT_SUGGESTIONS, "unanswered": True,
    }


def faq(context=None):
    return [{"q": i["title"], "a": fill(i["answer"], context)} for i in INTENTS if i.get("faq")]
