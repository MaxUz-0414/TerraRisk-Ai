"""Web-side tests for the analysis app: the API, the pages and the gateway behaviour when services misbehave.

The scoring, satellite, advice and PDF logic itself is tested in services/tests (each service on its own).
"""
from unittest import mock

from django.test import SimpleTestCase
from django.urls import reverse

from accounts.models import User
from core import services
from core.testing import PASSWORD, SQUARE, ServiceCase, dead_client, install

from .geo import area_ha, centroid, validate_geometry
from .models import Parcel, SearchEvent, SystemEvent, risk_level


class GeoTests(SimpleTestCase):
    def test_centroid_and_area(self):
        lat, lng = centroid(SQUARE)
        self.assertAlmostEqual(lat, 41.35, places=2)
        self.assertAlmostEqual(lng, 69.25, places=2)
        self.assertTrue(5000 < area_ha(SQUARE) < 100000)  # about 0.1 x 0.1 degrees

    def test_validation(self):
        validate_geometry(SQUARE)
        validate_geometry({"type": "Point", "coordinates": [10, 10]})
        with self.assertRaises(ValueError):
            validate_geometry({"type": "Point", "coordinates": [200, 10]})

    def test_risk_levels(self):
        self.assertEqual([risk_level(s) for s in (0, 39, 40, 64, 65, 100)], ["low", "low", "medium", "medium", "high", "high"])


class AnalyzeApiTests(ServiceCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(username="a@b.com", email="a@b.com", password=PASSWORD)

    def post(self, payload):
        return self.client.post(reverse("api-analyze"), payload, content_type="application/json")

    def test_requires_login(self):
        self.assertIn(self.post({"geometry": SQUARE}).status_code, (401, 403))

    def test_creates_parcel_with_place_and_uses_a_search(self):
        self.client.force_login(self.user)
        resp = self.post({"geometry": SQUARE, "buffer_km": 4, "nickname": "Test"})
        self.assertEqual(resp.status_code, 201, resp.content)
        parcel = Parcel.objects.get(owner=self.user)
        self.assertEqual(parcel.nickname, "Test")
        self.assertEqual((parcel.place, parcel.country_code), ("Yunusabad, Tashkent", "UZ"))
        self.assertEqual(parcel.data_mode, "demo")
        self.assertTrue(parcel.snapshot["view"] and parcel.snapshot["headline"])
        self.assertEqual(resp.json()["free_searches"], 4)
        self.user.refresh_from_db()
        self.assertEqual(self.user.free_searches, 4)

    def test_point_geometry_works(self):
        self.client.force_login(self.user)
        self.assertEqual(self.post({"geometry": {"type": "Point", "coordinates": [69.2, 41.3]}}).status_code, 201)

    def test_rejects_bad_geometry(self):
        self.client.force_login(self.user)
        self.assertEqual(self.post({"geometry": {"type": "LineString", "coordinates": []}}).status_code, 400)

    def test_blocks_when_no_searches_left(self):
        self.client.force_login(self.user)
        for _ in range(5):
            self.assertEqual(self.post({"geometry": SQUARE}).status_code, 201)
        resp = self.post({"geometry": SQUARE})
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["upgrade_url"], reverse("pricing"))
        self.assertEqual(Parcel.objects.count(), 5)

    def test_account_that_existed_before_billing_keeps_its_balance(self):
        """The first call creates the billing account with the balance the user already had (migration path from the monolith)."""
        self.user.free_searches = 2
        self.user.save()
        self.client.force_login(self.user)
        self.assertEqual(self.post({"geometry": SQUARE}).json()["free_searches"], 1)

    def test_analysis_failure_returns_502_logs_event_and_refunds(self):
        self.client.force_login(self.user)
        with mock.patch("core.services.analyze", side_effect=services.Unavailable("analysis", "satellite is down")):
            resp = self.post({"geometry": SQUARE})
        self.assertEqual(resp.status_code, 502)
        self.assertTrue(SystemEvent.objects.filter(source="analysis").exists())
        self.assertFalse(Parcel.objects.exists())
        self.user.refresh_from_db()
        self.assertEqual(self.user.free_searches, 5)  # a failed analysis costs nothing

    def test_rejected_input_from_the_analysis_service_refunds_too(self):
        self.client.force_login(self.user)
        with mock.patch("core.services.analyze", side_effect=services.Rejected("analysis", 400, "Geometry is outside the supported range")):
            resp = self.post({"geometry": SQUARE})
        self.assertEqual(resp.status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.free_searches, 5)

    def test_saving_failure_refunds(self):
        self.client.force_login(self.user)
        with mock.patch("analysis.views.Parcel.objects.create", side_effect=RuntimeError("disk full")):
            resp = self.post({"geometry": SQUARE})
        self.assertEqual(resp.status_code, 500)
        self.user.refresh_from_db()
        self.assertEqual(self.user.free_searches, 5)

    def test_billing_down_fails_closed_and_nothing_is_analysed(self):
        """If we cannot check the balance we must not hand out free analyses."""
        self.client.force_login(self.user)
        install("billing", dead_client("billing"))
        with mock.patch("core.services.analyze") as analyze:
            resp = self.post({"geometry": SQUARE})
        self.assertEqual(resp.status_code, 503)
        analyze.assert_not_called()
        self.assertFalse(Parcel.objects.exists())

    def test_geocoder_down_still_gives_an_analysis_without_a_place_name(self):
        """Place names are optional: the analysis service degrades, the user still gets a result, the admin sees a warning."""
        self.client.force_login(self.user)
        with mock.patch("tr_geocode.providers.fetch_json", side_effect=OSError("offline")):
            resp = self.post({"geometry": SQUARE})
        self.assertEqual(resp.status_code, 201)
        parcel = Parcel.objects.get()
        self.assertEqual(parcel.place, "")
        self.assertEqual(parcel.place_display, "")
        self.assertEqual(parcel.nickname, "Parcel 1")               # no place name to name it after
        self.assertTrue(SystemEvent.objects.filter(level="warning", source="geocode").exists())

    def test_advisory_service_down_still_gives_an_analysis(self):
        self.client.force_login(self.user)
        install("advisory", dead_client("advisory"))
        resp = self.post({"geometry": SQUARE})
        self.assertEqual(resp.status_code, 201)
        parcel = Parcel.objects.get()
        self.assertEqual(parcel.advisory, [])                       # no written advice, but scores, charts and checklist are complete
        self.assertTrue(parcel.snapshot["view"]["checklist"]["items"])
        self.assertTrue(SystemEvent.objects.filter(level="warning", source="advisory").exists())
        self.assertContains(self.client.get(reverse("dashboard", args=[parcel.pk])), "Advice is missing")


class PageTests(ServiceCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(username="a@b.com", email="a@b.com", password=PASSWORD, first_name="Alex")
        self.other = User.objects.create_user(username="c@d.com", email="c@d.com", password=PASSWORD)

    def make_parcel(self, owner=None):
        owner = owner or self.user
        self.client.force_login(owner)
        resp = self.client.post(reverse("api-analyze"), {"geometry": SQUARE, "nickname": "Field"}, content_type="application/json")
        self.assertEqual(resp.status_code, 201, resp.content)
        return Parcel.objects.get(pk=resp.json()["id"])

    def test_public_pages(self):
        for name in ("landing", "login", "signup", "health", "pricing", "support", "terms", "privacy"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_private_pages_redirect_when_logged_out(self):
        for name in ("platform", "saved", "profile"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 302, name)
        for url in (reverse("api-place-search"), reverse("api-map-config")):
            self.assertIn(self.client.get(url).status_code, (302, 401, 403), url)

    def test_signup_creates_account_with_persona(self):
        resp = self.client.post(reverse("signup"), {
            "first_name": "Sam", "email": "Sam@Example.com", "persona": "homebuyer",
            "password1": "Str0ng-pass!!", "password2": "Str0ng-pass!!"})
        self.assertEqual(resp.status_code, 302)
        user = User.objects.get(username="sam@example.com")
        self.assertEqual(user.persona, "homebuyer")

    def test_dashboard_saved_and_platform_render(self):
        parcel = self.make_parcel()
        page = self.client.get(reverse("dashboard", args=[parcel.pk]))
        self.assertContains(page, "Export PDF Report")
        self.assertContains(page, "Yunusabad, Tashkent")        # the place name is shown
        self.assertContains(page, "Demo mode")                  # demo mode is announced, never hidden
        self.assertContains(self.client.get(reverse("saved")), "Yunusabad")
        self.assertEqual(self.client.get(reverse("platform")).status_code, 200)

    def test_users_cannot_open_each_others_parcels(self):
        parcel = self.make_parcel()
        self.client.force_login(self.other)
        for name in ("dashboard", "report"):
            self.assertEqual(self.client.get(reverse(name, args=[parcel.pk])).status_code, 404, name)
        self.assertEqual(self.client.get(reverse("satellite", args=[parcel.pk, "ndvi"])).status_code, 404)

    def test_dashboard_shows_persona_view_for_each_group(self):
        for persona in ("farmer", "homebuyer", "investor"):
            self.user.persona = persona
            self.user.save()
            parcel = self.make_parcel()
            html = self.client.get(reverse("dashboard", args=[parcel.pk])).content.decode()
            self.assertIn("Why this score?", html, persona)
            self.assertIn("/satellite/truecolor/", html, persona)
            self.assertEqual("Due-diligence flags" in html, persona == "investor", persona)
            self.assertEqual("What if conditions get worse?" in html, persona == "investor", persona)

    def test_old_parcel_without_snapshot_or_place_still_renders(self):
        """Parcels saved by the old monolith have no snapshot, place or data mode: the risk and geocode services fill them in on first view."""
        parcel = self.make_parcel()
        Parcel.objects.filter(pk=parcel.pk).update(snapshot={}, place="", country="", country_code="", data_mode="")
        page = self.client.get(reverse("dashboard", args=[parcel.pk]))
        self.assertEqual(page.status_code, 200)
        parcel.refresh_from_db()
        self.assertTrue(parcel.snapshot["view"])
        self.assertEqual(parcel.place, "Yunusabad, Tashkent")
        self.assertEqual(parcel.data_mode, "legacy")

    def test_old_parcel_with_thin_features_renders(self):
        parcel = self.make_parcel()
        parcel.features = {k: v for k, v in parcel.features.items() if k in (
            "upstream_slope_deg", "dist_to_river_m", "ndvi_trend_pct", "lst_peak_c", "soil_moisture_change_pct",
            "siltation", "soil_saturation", "ndvi_series", "lst_series")}
        parcel.snapshot = {}
        parcel.save()
        self.assertEqual(self.client.get(reverse("dashboard", args=[parcel.pk])).status_code, 200)

    def test_dashboard_when_risk_service_is_down_redirects_with_message(self):
        parcel = self.make_parcel()
        Parcel.objects.filter(pk=parcel.pk).update(snapshot={})
        install("risk", dead_client("risk"))
        resp = self.client.get(reverse("dashboard", args=[parcel.pk]), follow=True)
        self.assertRedirects(resp, reverse("saved"))
        self.assertContains(resp, "not answering")

    # ---- PDF report
    def test_pdf_report_is_generated_and_cached(self):
        parcel = self.make_parcel()
        with self.settings(MEDIA_ROOT=self._tmp.name):
            resp = self.client.get(reverse("report", args=[parcel.pk]))
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp["Content-Type"], "application/pdf")
            body = b"".join(resp.streaming_content)
            self.assertTrue(body.startswith(b"%PDF"))
            parcel.refresh_from_db()
            self.assertTrue(parcel.report_size > 5000)
            self.assertEqual(parcel.report_version, 2)
            with mock.patch("core.services.render_report") as render:   # second download: served from storage, report service not called
                self.assertEqual(self.client.get(reverse("report", args=[parcel.pk])).status_code, 200)
            render.assert_not_called()

    def test_stored_pdf_of_an_old_layout_is_rebuilt(self):
        parcel = self.make_parcel()
        with self.settings(MEDIA_ROOT=self._tmp.name):
            self.client.get(reverse("report", args=[parcel.pk]))
            Parcel.objects.filter(pk=parcel.pk).update(report_version=1)
            with mock.patch("core.services.render_report", wraps=services.render_report) as render:
                self.assertEqual(self.client.get(reverse("report", args=[parcel.pk])).status_code, 200)
            render.assert_called_once()
            parcel.refresh_from_db()
            self.assertEqual(parcel.report_version, 2)

    def test_pdf_carries_the_place_and_satellite_pictures(self):
        parcel = self.make_parcel()
        with self.settings(MEDIA_ROOT=self._tmp.name), mock.patch("core.services.render_report", wraps=services.render_report) as render:
            self.client.get(reverse("report", args=[parcel.pk]))
        data = render.call_args.args[0]
        self.assertEqual(data["place"], "Yunusabad, Tashkent, Uzbekistan")
        self.assertIn("geometry", data)          # the report service fetches the 4 satellite layers itself from this
        self.assertIn("imagery_note", data)

    def test_pdf_failure_redirects_back_with_a_message(self):
        parcel = self.make_parcel()
        install("report", dead_client("report"))
        resp = self.client.get(reverse("report", args=[parcel.pk]), follow=True)
        self.assertRedirects(resp, reverse("dashboard", args=[parcel.pk]))
        self.assertContains(resp, "could not create the PDF")
        self.assertTrue(SystemEvent.objects.filter(source="report").exists())

    # ---- satellite pictures
    def test_satellite_layer_is_high_resolution_cached_private_and_validated(self):
        parcel = self.make_parcel()
        url = reverse("satellite", args=[parcel.pk, "ndvi"])
        first = self.client.get(url)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first["Content-Type"], "image/jpeg")
        self.assertTrue(first.content.startswith(b"\xff\xd8"))
        self.assertIn("private", first["Cache-Control"])
        from PIL import Image
        import io

        self.assertEqual(Image.open(io.BytesIO(first.content)).size, (1600, 1000))
        self.assertEqual(self.client.get(url).content, first.content)  # same picture again (satellite service cache)
        self.assertEqual(self.client.get(reverse("satellite", args=[parcel.pk, "nope"])).status_code, 404)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_every_layer_the_pages_offer_exists_in_the_satellite_service(self):
        from analysis.views import LAYERS

        parcel = self.make_parcel()
        for key in LAYERS:
            self.assertEqual(self.client.get(reverse("satellite", args=[parcel.pk, key])).status_code, 200, key)

    def test_satellite_failure_returns_placeholder_not_error(self):
        parcel = self.make_parcel()
        with mock.patch("core.services.satellite_layer", side_effect=services.Unavailable("satellite", "Earth Engine is down")):
            resp = self.client.get(reverse("satellite", args=[parcel.pk, "heat"]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "image/svg+xml")
        self.assertEqual(resp["Cache-Control"], "no-store")  # the placeholder must not stick in the browser cache
        self.assertTrue(SystemEvent.objects.filter(source="satellite").exists())

    # ---- small things
    def test_display_name_fallback(self):
        parcel = self.make_parcel()
        parcel.nickname = "IIIII"
        self.assertEqual(parcel.display_name, "Yunusabad, Tashkent")          # no real nickname: the place name
        parcel.place = ""
        self.assertTrue(parcel.display_name.startswith("Parcel at"))        # no place either: the coordinates
        parcel.nickname = "North field"
        self.assertEqual(parcel.display_name, "North field")

    def test_delete_parcel(self):
        parcel = self.make_parcel()
        self.client.post(reverse("parcel-delete", args=[parcel.pk]))
        self.assertFalse(Parcel.objects.filter(pk=parcel.pk).exists())

    def test_profile_update(self):
        self.client.force_login(self.user)
        self.client.post(reverse("profile"), {"first_name": "Alexander", "persona": "investor"})
        self.user.refresh_from_db()
        self.assertEqual((self.user.first_name, self.user.persona), ("Alexander", "investor"))


class PlaceEndpointTests(ServiceCase):
    """The map search box and the "what is this place called" call (BFF in front of the geocode service)."""

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(username="a@b.com", email="a@b.com", password=PASSWORD)
        self.client.force_login(self.user)

    def test_search_returns_names_and_coordinates(self):
        body = self.client.get(reverse("api-place-search"), {"q": "tashkent"}).json()
        top = body["results"][0]
        self.assertEqual((top["country_code"], top["lat"], top["lng"]), ("UZ", 41.3, 69.2))
        self.assertIn("Tashkent", top["short"])

    def test_typing_is_not_logged_but_pressing_enter_is(self):
        self.client.get(reverse("api-place-search"), {"q": "tashkent"})
        self.assertEqual(SearchEvent.objects.count(), 0)
        self.client.get(reverse("api-place-search"), {"q": "tashkent", "commit": "1"})
        event = SearchEvent.objects.get()
        self.assertEqual((event.user, event.query, event.country_code), (self.user, "tashkent", "UZ"))

    def test_short_query_is_ignored(self):
        self.assertEqual(self.client.get(reverse("api-place-search"), {"q": "a"}).json(), {"results": []})

    def test_search_is_rate_limited(self):
        codes = [self.client.get(reverse("api-place-search"), {"q": f"place {i}"}).status_code for i in range(43)]
        self.assertEqual(codes[0], 200)
        self.assertEqual(codes[-1], 429)

    def test_geocoder_down_gives_a_friendly_503(self):
        install("geocode", dead_client("geocode"))
        resp = self.client.get(reverse("api-place-search"), {"q": "tashkent"})
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.json()["results"], [])

    def test_reverse_returns_a_name(self):
        body = self.client.get(reverse("api-place-reverse"), {"lat": 41.3, "lng": 69.2}).json()
        self.assertEqual((body["name"], body["country_code"]), ("Yunusabad, Tashkent", "UZ"))

    def test_reverse_validates_and_never_breaks_the_map(self):
        self.assertEqual(self.client.get(reverse("api-place-reverse"), {"lat": "x", "lng": 1}).status_code, 400)
        self.assertEqual(self.client.get(reverse("api-place-reverse"), {"lat": 95, "lng": 1}).status_code, 400)
        install("geocode", dead_client("geocode"))
        resp = self.client.get(reverse("api-place-reverse"), {"lat": 41.3, "lng": 69.2})
        self.assertEqual((resp.status_code, resp.json()["name"]), (200, ""))

    def test_map_config_without_a_google_key_uses_the_free_labels(self):
        self.assertEqual(self.client.get(reverse("api-map-config")).json(), {"google": None})

    def test_map_config_with_a_google_key_opens_a_tile_session(self):
        reply = mock.Mock(status_code=200)
        reply.json.return_value = {"session": "abc123"}
        with self.settings(GOOGLE_MAPS_API_KEY="k"), mock.patch("requests.post", return_value=reply) as post:
            google = self.client.get(reverse("api-map-config")).json()["google"]
        self.assertIn("session=abc123", google["tiles"])
        self.assertEqual(post.call_args.kwargs["params"], {"key": "k"})

    def test_map_config_falls_back_when_google_refuses(self):
        with self.settings(GOOGLE_MAPS_API_KEY="k"), mock.patch("requests.post", side_effect=OSError("denied")):
            self.assertEqual(self.client.get(reverse("api-map-config")).json(), {"google": None})
