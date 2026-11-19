"""HTTP API of the chatbot service.

POST /v1/chat  {message, context}  -> {reply, links: [{label, route}], suggestions, unanswered}
POST /v1/faq   {context}           -> {faq: [{q, a}]}
context (all optional): {balance, support_email, free_searches, demo_data, demo_payments}
"""
from flask import jsonify, request
from tr_common.service import create_service_app

from . import engine, logic
from .knowledge import INTENTS


def create_app():
    app = create_service_app("chatbot", "1.0.0", readiness=lambda: {"intents": len(INTENTS)})

    @app.post("/v1/chat")
    def chat():
        body = request.get_json(silent=True) or {}
        message = str(body.get("message", "")).strip()[:300]
        if not message:
            return jsonify(error="bad_request", message="Please type a question."), 400
        context = body.get("context") if isinstance(body.get("context"), dict) else {}
        return jsonify(logic.answer(message, context))

    @app.post("/v1/faq")
    def faq():
        body = request.get_json(silent=True) or {}
        context = body.get("context") if isinstance(body.get("context"), dict) else {}
        return jsonify({"faq": logic.faq(context)})

    return app
