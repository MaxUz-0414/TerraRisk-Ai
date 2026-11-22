from .base import HEADERS, ServiceTest, dead_client, registry

from tr_common.client import Client, ServiceError, ServiceUnavailable
from tr_common.service import create_service_app


class ServiceAppTests(ServiceTest):
    def setUp(self):
        super().setUp()
        self.app = create_service_app("demo", "9.9.9", readiness=lambda: {"db": True})

        @self.app.get("/boom")
        def boom():
            raise RuntimeError("secret internals")

        @self.app.get("/ok")
        def ok():
            return {"fine": True}

        self.http = self.app.test_client()

    def test_healthz_is_public(self):
        reply = self.http.get("/healthz")
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(reply.get_json()["status"], "ok")
        self.assertEqual(reply.get_json()["version"], "9.9.9")

    def test_other_paths_need_the_service_token(self):
        self.assertEqual(self.http.get("/ok").status_code, 401)
        self.assertEqual(self.http.get("/ok", headers={"X-Service-Token": "wrong"}).status_code, 401)
        self.assertEqual(self.http.get("/ok", headers=HEADERS).status_code, 200)

    def test_request_id_is_kept_or_created(self):
        self.assertEqual(self.http.get("/ok", headers={**HEADERS, "X-Request-ID": "abc123"}).headers["X-Request-ID"], "abc123")
        self.assertTrue(self.http.get("/ok", headers=HEADERS).headers["X-Request-ID"])

    def test_errors_are_json_and_hide_internals(self):
        reply = self.http.get("/boom", headers=HEADERS)
        self.assertEqual(reply.status_code, 500)
        self.assertEqual(reply.get_json()["error"], "internal_error")
        self.assertNotIn("secret", reply.get_data(as_text=True))
        missing = self.http.get("/nope", headers=HEADERS)
        self.assertEqual(missing.status_code, 404)
        self.assertIn("error", missing.get_json())

    def test_info_counts_requests_and_errors(self):
        self.http.get("/ok", headers=HEADERS)
        self.http.get("/boom", headers=HEADERS)
        info = self.http.get("/v1/info", headers=HEADERS).get_json()
        self.assertGreaterEqual(info["requests"], 2)
        self.assertGreaterEqual(info["errors"], 1)

    def test_failed_readiness_makes_healthz_503(self):
        app = create_service_app("sick", readiness=lambda: {"db": False})
        self.assertEqual(app.test_client().get("/healthz").status_code, 503)


class ClientTests(ServiceTest):
    def test_in_process_client_talks_to_the_app(self):
        app = create_service_app("demo")

        @app.get("/ok")
        def ok():
            return {"fine": True}

        client = Client("demo", token="test-token", app=app)
        self.assertEqual(client.get("/ok").json(), {"fine": True})

    def test_wrong_token_is_a_service_error(self):
        app = create_service_app("demo")
        client = Client("demo", token="nope", app=app)
        with self.assertRaises(ServiceError) as caught:
            client.get("/v1/info")
        self.assertEqual(caught.exception.status, 401)

    def test_unreachable_service_raises_unavailable(self):
        with self.assertRaises(ServiceUnavailable):
            dead_client("ghost").post("/v1/anything", json={})

    def test_circuit_opens_after_repeated_failures(self):
        client = Client("ghost", base_url="http://127.0.0.1:9", timeout=1, breaker_threshold=2, breaker_reset=60)
        for _ in range(2):
            with self.assertRaises(ServiceUnavailable):
                client.post("/x", json={})
        with self.assertRaises(ServiceUnavailable) as caught:
            client.post("/x", json={})
        self.assertIn("circuit open", str(caught.exception))

    def test_server_errors_are_not_swallowed(self):
        app = create_service_app("demo")

        @app.post("/crash")
        def crash():
            raise RuntimeError("x")

        with self.assertRaises(ServiceError) as caught:
            Client("demo", token="test-token", app=app).post("/crash", json={})
        self.assertEqual(caught.exception.status, 500)


class RegistryTests(ServiceTest):
    def test_every_service_has_a_working_in_process_client(self):
        for name in registry.SERVICES:
            health = registry.health(name)
            self.assertTrue(health["up"], f"{name}: {health}")

    def test_unknown_service_is_rejected(self):
        with self.assertRaises(KeyError):
            registry.client("payments")

    def test_health_reports_down_instead_of_raising(self):
        from .base import install

        install("risk", dead_client("risk"))
        health = registry.health("risk")
        self.assertFalse(health["up"])
        self.assertIn("error", health)
