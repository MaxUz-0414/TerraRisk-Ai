"""Optional helper: ask Gemini when the trained model is not sure. Only used if GEMINI_API_KEY is set."""
import logging

import requests
from tr_common.config import env_str

logger = logging.getLogger(__name__)


def ask_gemini(question, knowledge_text, support_email):
    """Return a short answer based ONLY on our knowledge text, or None if anything goes wrong."""
    key = env_str("GEMINI_API_KEY")
    if not key:
        return None
    prompt = (
        "You are the support assistant of TerraRisk AI, a website that estimates climate and flood risk for land.\n"
        "Answer the user's question using ONLY the facts below. If the facts do not contain the answer, say you are not sure "
        f"and suggest emailing {support_email}. Use at most 3 short sentences and plain text.\n\n"
        f"FACTS:\n{knowledge_text}\n\nUSER QUESTION: {question}"
    )
    try:
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{env_str('GEMINI_MODEL') or 'gemini-3.5-flash-lite'}:generateContent",
            headers={"x-goog-api-key": key, "Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()[:600]
    except Exception:
        logger.exception("Gemini chatbot fallback failed")
        return None
