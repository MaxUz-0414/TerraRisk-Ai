"""HTTP API of the billing service.

GET  /v1/plans
PUT  /v1/accounts/<user_id>            {email?, initial?: {free_searches, unlimited_until, plan_key}}  -> account (created on first call)
GET  /v1/accounts/<user_id>            -> account
POST /v1/accounts/<user_id>/consume    {key?}          -> account | 402 {"error": "no_searches"}
POST /v1/accounts/<user_id>/refund     {key}           -> account
POST /v1/accounts/<user_id>/checkout   {plan_key}      -> account   (501 when PAYMENTS_DEMO=False: no real provider connected)
GET  /v1/stats                         -> revenue and usage numbers for the admin dashboard
"""
from flask import jsonify, request
from tr_common.config import env_bool, env_int
from tr_common.service import create_service_app

from . import store
from .plans import PLANS, UNLIMITED_DAYS, get_plan


def create_app():
    def ready():
        with store.connect() as conn:
            conn.execute("SELECT 1")
        return {"database": "sqlite", "payments": "demo" if env_bool("PAYMENTS_DEMO", True) else "live"}

    app = create_service_app("billing", "1.0.0", readiness=ready)

    def not_found(user_id):
        return jsonify(error="not_found", message=f"No account for user {user_id}."), 404

    @app.get("/v1/plans")
    def plans():
        return jsonify({"plans": [p.as_dict() for p in PLANS], "unlimited_days": UNLIMITED_DAYS,
                        "free_searches": env_int("FREE_SEARCHES", 5), "demo": env_bool("PAYMENTS_DEMO", True)})

    @app.put("/v1/accounts/<int:user_id>")
    def ensure(user_id):
        body = request.get_json(silent=True) or {}
        return jsonify(store.ensure_account(user_id, str(body.get("email", ""))[:254], body.get("initial") if isinstance(body.get("initial"), dict) else None))

    @app.get("/v1/accounts/<int:user_id>")
    def get(user_id):
        account = store.get_account(user_id)
        return jsonify(account) if account else not_found(user_id)

    @app.post("/v1/accounts/<int:user_id>/consume")
    def consume(user_id):
        key = (request.get_json(silent=True) or {}).get("key")
        try:
            return jsonify(store.consume(user_id, str(key) if key else None))
        except store.NoSearchesLeft:
            return jsonify(error="no_searches", message="No searches left. Choose a plan to keep going."), 402
        except KeyError:
            return not_found(user_id)

    @app.post("/v1/accounts/<int:user_id>/refund")
    def refund(user_id):
        key = (request.get_json(silent=True) or {}).get("key")
        if not key:
            return jsonify(error="bad_request", message="'key' is required."), 400
        try:
            return jsonify(store.refund(user_id, str(key)))
        except KeyError:
            return not_found(user_id)

    @app.post("/v1/accounts/<int:user_id>/checkout")
    def checkout(user_id):
        plan_key = (request.get_json(silent=True) or {}).get("plan_key")
        if get_plan(plan_key) is None:
            return jsonify(error="bad_request", message="Unknown plan."), 400
        if not env_bool("PAYMENTS_DEMO", True):
            return jsonify(error="payments_not_connected", message="Online payments are not connected yet. Please contact support to buy a plan."), 501
        try:
            return jsonify(store.checkout(user_id, plan_key))
        except KeyError:
            return not_found(user_id)

    @app.get("/v1/stats")
    def stats():
        return jsonify(store.stats())

    return app
