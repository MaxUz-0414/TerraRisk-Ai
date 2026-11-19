from .base import ServiceTest, registry

from tr_common.client import ServiceError


class BillingTests(ServiceTest):
    def setUp(self):
        super().setUp()
        self.billing = registry.client("billing")
        self._uid = abs(hash(self._testMethodName)) % 10**8 + 1000

    def account(self, **initial):
        return self.billing.request("PUT", f"/v1/accounts/{self._uid}", json={"email": "a@b.co", "initial": initial}).json()

    def post(self, suffix, body=None):
        return self.billing.post(f"/v1/accounts/{self._uid}/{suffix}", json=body or {}).json()

    def test_new_account_gets_free_searches(self):
        self.assertEqual(self.account()["free_searches"], 5)

    def test_existing_balance_is_kept_on_first_sight(self):
        self.assertEqual(self.account(free_searches=2, plan_key="plus")["free_searches"], 2)

    def test_consume_reduces_balance_and_zero_blocks(self):
        self.account(free_searches=1)
        self.assertEqual(self.post("consume", {"key": "k1"})["free_searches"], 0)
        with self.assertRaises(ServiceError) as caught:
            self.post("consume", {"key": "k2"})
        self.assertEqual(caught.exception.status, 402)

    def test_consume_is_idempotent_for_the_same_key(self):
        self.account(free_searches=3)
        self.post("consume", {"key": "same"})
        self.assertEqual(self.post("consume", {"key": "same"})["free_searches"], 2)

    def test_refund_gives_the_search_back_once(self):
        self.account(free_searches=3)
        self.post("consume", {"key": "r1"})
        self.assertEqual(self.post("refund", {"key": "r1"})["free_searches"], 3)
        self.assertEqual(self.post("refund", {"key": "r1"})["free_searches"], 3)

    def test_checkout_adds_searches_and_records_a_purchase(self):
        self.account(free_searches=0)
        account = self.post("checkout", {"plan_key": "plus"})
        self.assertEqual(account["free_searches"], 30)
        self.assertEqual(account["purchases"][0]["plan_key"], "plus")

    def test_unlimited_plan_is_not_charged_per_search(self):
        self.account(free_searches=0)
        self.post("checkout", {"plan_key": "unlimited"})
        account = self.post("consume", {"key": "u1"})
        self.assertTrue(account["unlimited"])
        self.assertEqual(account["free_searches"], 0)

    def test_unknown_plan_and_unknown_user(self):
        self.account()
        with self.assertRaises(ServiceError) as caught:
            self.post("checkout", {"plan_key": "gold"})
        self.assertEqual(caught.exception.status, 400)
        with self.assertRaises(ServiceError) as caught:
            self.billing.post("/v1/accounts/99999999/consume", json={})
        self.assertEqual(caught.exception.status, 404)

    def test_live_payments_are_refused_until_a_provider_is_connected(self):
        import os

        self.account()
        os.environ["PAYMENTS_DEMO"] = "False"
        try:
            with self.assertRaises(ServiceError) as caught:
                self.post("checkout", {"plan_key": "plus"})
            self.assertEqual(caught.exception.status, 501)
        finally:
            os.environ["PAYMENTS_DEMO"] = "True"

    def test_plans_and_stats(self):
        plans = self.billing.get("/v1/plans").json()
        self.assertEqual([p["key"] for p in plans["plans"]][:4], ["starter", "plus", "pro", "business"])
        self.assertTrue(any(p["key"] == "unlimited" for p in plans["plans"]))
        self.assertIsInstance(self.billing.get("/v1/stats").json(), dict)
