"""Web tests for the core app: landing/home, billing through the billing service, chatbot BFF, login recording, the admin dashboard."""
import json
from datetime import timedelta
from unittest import mock

from django.conf import settings
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import LoginEvent, Purchase, User
from accounts.plans import PLANS, get_plan
from analysis.models import Parcel, SearchEvent, SystemEvent
from tr_common import registry

from . import dashboard, services
from .team import TEAM, team_members
from .testing import PASSWORD, SQUARE, ServiceCase, dead_client, install


def make_user(**extra):
    return User.objects.create_user(username="a@b.com", email="a@b.com", password=PASSWORD, first_name="Alex", **extra)


def make_staff():
    return User.objects.create_user(username="s@t.com", email="s@t.com", password=PASSWORD, is_staff=True, is_superuser=True, first_name="Sam")


# ---------------------------------------------------------------- landing for visitors
class LandingTests(ServiceCase):
    def test_persona_cards_lead_to_signup_with_persona(self):
        html = self.client.get(reverse("landing")).content.decode()
        self.assertIn("Choose your path", html)
        for persona in ("farmer", "homebuyer", "investor"):
            self.assertIn(f"?persona={persona}", html)
        for image in ("farmer.svg", "homebuyer.svg", "investor.svg"):
            self.assertIn(image, html)

    def test_team_section_has_six_members_with_roles(self):
        self.assertEqual(len(TEAM), 6)
        html = self.client.get(reverse("landing")).content.decode()
        self.assertEqual(html.count("<article"), 6)
        self.assertIn("Geospatial Data Engineer", html)
        self.assertEqual(len(team_members()), 6)
        self.assertTrue(all(m["initials"] for m in team_members()))

    def test_footer_has_email_and_social_links(self):
        html = self.client.get(reverse("landing")).content.decode()
        self.assertIn(f"mailto:{settings.SUPPORT_EMAIL}", html)
        self.assertIn(settings.INSTAGRAM_URL, html)
        self.assertIn(settings.TWITTER_URL, html)
        self.assertIn(reverse("support"), html)

    def test_signup_preselects_persona_from_link(self):
        html = self.client.get(reverse("signup") + "?persona=homebuyer").content.decode()
        self.assertIn('value="homebuyer" selected', html)
        self.assertIn("homebuyer.svg", html)

    def test_chat_widget_is_on_every_page(self):
        self.client.force_login(make_user())
        for name in ("landing", "pricing", "support", "terms", "privacy", "platform", "saved", "profile"):
            self.assertContains(self.client.get(reverse(name)), 'id="chat"', msg_prefix=name)
        self.client.logout()
        for name in ("login", "signup"):
            self.assertContains(self.client.get(reverse(name)), 'id="chat"', msg_prefix=name)

    def test_support_page_lists_faq_from_the_chatbot_service(self):
        resp = self.client.get(reverse("support"))
        self.assertContains(resp, "How do I run my first analysis?")
        self.assertContains(resp, settings.SUPPORT_EMAIL)

    def test_support_page_survives_a_chatbot_outage(self):
        install("chatbot", dead_client("chatbot"))
        resp = self.client.get(reverse("support"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, settings.SUPPORT_EMAIL)


# ---------------------------------------------------------------- landing for signed-in users
class HomeTests(ServiceCase):
    def setUp(self):
        super().setUp()
        self.user = make_user(persona="investor")

    def analyse(self, nickname="Field"):
        return self.client.post(reverse("api-analyze"), {"geometry": SQUARE, "nickname": nickname}, content_type="application/json")

    def test_signed_in_users_do_not_see_the_signup_marketing(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse("landing")).content.decode()
        self.assertIn("Welcome back, Alex", html)
        for marketing in ("Choose your path", "Get Started", "?persona=farmer"):
            self.assertNotIn(marketing, html, marketing)

    def test_navbar_has_an_account_menu_for_signed_in_users_only(self):
        self.assertNotIn('class="usermenu"', self.client.get(reverse("landing")).content.decode())
        self.client.force_login(self.user)
        html = self.client.get(reverse("landing")).content.decode()
        self.assertIn('class="usermenu"', html)
        self.assertIn(reverse("saved"), html)
        self.assertNotIn("um-admin", html)    # regular users never see the admin link

    def test_new_user_sees_how_to_start(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse("landing")).content.decode()
        self.assertIn("Draw your first piece of land", html)
        self.assertIn(reverse("platform"), html)

    def test_home_shows_recent_analyses_with_place_and_stats(self):
        self.client.force_login(self.user)
        self.assertEqual(self.analyse("North field").status_code, 201)
        self.assertEqual(self.analyse("South field").status_code, 201)
        html = self.client.get(reverse("landing")).content.decode()
        for expected in ("North field", "South field", "Yunusabad, Tashkent", "Saved analyses", "Needs attention", "Your highest-risk parcel"):
            self.assertIn(expected, html, expected)
        home = self.client.get(reverse("landing")).context["home"]
        self.assertEqual((home["parcel_count"], home["countries"]), (2, 1))

    def test_other_users_parcels_never_appear_on_my_home(self):
        other = User.objects.create_user(username="c@d.com", email="c@d.com", password=PASSWORD)
        self.client.force_login(other)
        self.analyse("Secret field")
        self.client.force_login(self.user)
        self.assertNotIn("Secret field", self.client.get(reverse("landing")).content.decode())

    def test_staff_get_a_link_to_the_real_admin(self):
        self.client.force_login(make_staff())
        html = self.client.get(reverse("landing")).content.decode()
        self.assertIn('href="/admin/"', html)

    def test_balance_card_reflects_the_billing_service(self):
        self.client.force_login(self.user)
        self.analyse()
        html = self.client.get(reverse("landing")).content.decode()
        self.assertIn("4", html)
        self.user.refresh_from_db()
        self.assertEqual(self.user.free_searches, 4)


# ---------------------------------------------------------------- billing through the billing service
class BillingTests(ServiceCase):
    def setUp(self):
        super().setUp()
        self.user = make_user()

    def analyze(self):
        return self.client.post(reverse("api-analyze"), {"geometry": SQUARE}, content_type="application/json")

    def test_pricing_page_lists_every_plan(self):
        resp = self.client.get(reverse("pricing"))
        for plan in PLANS:
            self.assertContains(resp, plan.name)
        self.assertEqual([p["searches"] for p in services.plans()["plans"]], [20, 30, 50, 100, None])

    def test_billing_service_and_the_web_fallback_agree(self):
        """Contract test: if someone changes a plan in one place and not the other, this fails."""
        live = services.plans()
        self.assertTrue(live["live"])
        cache.clear()
        install("billing", dead_client("billing"))
        fallback = services.plans()
        self.assertFalse(fallback["live"])
        keys = ("key", "name", "searches", "price", "popular", "is_unlimited")
        self.assertEqual([{k: p[k] for k in keys} for p in live["plans"]], [{k: p[k] for k in keys} for p in fallback["plans"]])
        self.assertEqual(live["unlimited_days"], fallback["unlimited_days"])

    def test_pricing_page_still_works_when_billing_is_down(self):
        install("billing", dead_client("billing"))
        resp = self.client.get(reverse("pricing"))
        self.assertEqual(resp.status_code, 200)
        for plan in PLANS:
            self.assertContains(resp, plan.name)

    def test_pill_in_navbar_links_to_pricing(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse("platform")).content.decode()
        self.assertIn(f'href="{reverse("pricing")}" class="pill"', html)

    def test_checkout_requires_login(self):
        self.assertEqual(self.client.get(reverse("checkout", args=["pro"])).status_code, 302)

    def test_unknown_plan_is_404(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("checkout", args=["nope"])).status_code, 404)

    def test_buying_credits_adds_searches_and_records_purchase(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("checkout", args=["plus"])).status_code, 200)
        resp = self.client.post(reverse("checkout", args=["plus"]))
        self.assertRedirects(resp, reverse("platform"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.free_searches, 5 + 30)
        purchase = Purchase.objects.get(user=self.user)
        self.assertEqual((purchase.plan_key, purchase.searches), ("plus", 30))

    def test_unlimited_plan_stops_deducting_searches(self):
        self.client.force_login(self.user)
        self.client.post(reverse("checkout", args=["unlimited"]))
        self.user.refresh_from_db()
        self.assertTrue(self.user.has_unlimited)
        balance = self.user.free_searches
        self.assertEqual(self.analyze().status_code, 201)
        self.user.refresh_from_db()
        self.assertEqual(self.user.free_searches, balance)

    def test_unlimited_extends_when_bought_twice(self):
        self.client.force_login(self.user)
        self.client.post(reverse("checkout", args=["unlimited"]))
        self.user.refresh_from_db()
        first_end = self.user.unlimited_until
        self.client.post(reverse("checkout", args=["unlimited"]))
        self.user.refresh_from_db()
        self.assertGreater(self.user.unlimited_until, first_end)
        self.assertEqual(Purchase.objects.filter(user=self.user).count(), 2)

    def test_out_of_searches_points_to_pricing(self):
        self.user.free_searches = 0
        self.user.save()
        self.client.force_login(self.user)
        resp = self.analyze()
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["upgrade_url"], reverse("pricing"))

    def test_the_billing_service_is_the_source_of_truth(self):
        """Editing the cached copy on the web user does not give free searches."""
        self.client.force_login(self.user)
        self.assertEqual(self.analyze().status_code, 201)       # creates the billing account (5 -> 4)
        User.objects.filter(pk=self.user.pk).update(free_searches=99)
        self.analyze()
        self.user.refresh_from_db()
        self.assertEqual(self.user.free_searches, 3)

    def test_idempotent_consume_does_not_charge_twice(self):
        services.billing_account(self.user)
        services.consume_search(self.user, "same-key")
        services.consume_search(self.user, "same-key")
        self.assertEqual(self.user.free_searches, 4)
        services.refund_search(self.user, "same-key")
        services.refund_search(self.user, "same-key")
        self.assertEqual(self.user.free_searches, 5)

    @override_settings(PAYMENTS_DEMO=False)
    def test_checkout_is_blocked_when_real_payments_are_not_connected(self):
        self.client.force_login(self.user)
        self.client.post(reverse("checkout", args=["pro"]))
        self.user.refresh_from_db()
        self.assertEqual(self.user.free_searches, 5)
        self.assertFalse(Purchase.objects.exists())

    def test_checkout_when_billing_is_down_charges_nothing(self):
        self.client.force_login(self.user)
        install("billing", dead_client("billing"))
        resp = self.client.post(reverse("checkout", args=["pro"]), follow=True)
        self.assertRedirects(resp, reverse("pricing"))
        self.assertContains(resp, "nothing was charged")
        self.assertFalse(Purchase.objects.exists())
        self.assertTrue(SystemEvent.objects.filter(source="billing").exists())


# ---------------------------------------------------------------- chatbot (BFF in front of the chatbot service)
class ChatbotTests(ServiceCase):
    def setUp(self):
        super().setUp()
        registry.ensure_path("chatbot")

    def ask(self, text):
        return self.client.post(reverse("chat"), {"message": text}, content_type="application/json")

    def test_answers_common_questions(self):
        cases = [
            ("hello", "Hello"), ("how much does it cost", "Starter"), ("how do i download a pdf", "Export PDF Report"),
            ("who built this website", "team of six"), ("what does ndvi mean", "satellite measure"), ("how do i sign up", "Get Started"),
        ]
        for question, expected in cases:
            self.assertIn(expected, self.ask(question).json()["reply"], question)

    def test_replies_include_working_links(self):
        data = self.ask("how much does it cost").json()
        self.assertIn(reverse("pricing"), [link["url"] for link in data["links"]])

    def test_unknown_question_gets_polite_fallback(self):
        data = self.ask("zzzz qqqq xxxx").json()
        self.assertIn("not sure", data["reply"])
        self.assertTrue(data["suggestions"])
        self.assertTrue(SystemEvent.objects.filter(source="chatbot", message__startswith="Unanswered").exists())

    def test_off_topic_is_declined(self):
        self.assertIn("only know about TerraRisk", self.ask("tell me a joke").json()["reply"])

    def test_balance_is_personalised_without_the_chatbot_knowing_the_user(self):
        make_user()
        self.client.login(username="a@b.com", password=PASSWORD)
        self.assertIn("5 searches", self.ask("how many searches do i have left").json()["reply"])

    def test_anonymous_balance_asks_to_sign_in(self):
        self.assertIn("Sign in", self.ask("how many searches do i have left").json()["reply"])

    def test_bad_requests(self):
        self.assertEqual(self.ask("   ").status_code, 400)
        self.assertEqual(self.client.post(reverse("chat"), "not json", content_type="application/json").status_code, 400)

    def test_rate_limit(self):
        codes = [self.ask("hi").status_code for _ in range(22)]
        self.assertEqual(codes[0], 200)
        self.assertEqual(codes[-1], 429)

    def test_chatbot_outage_gives_a_friendly_answer(self):
        install("chatbot", dead_client("chatbot"))
        resp = self.ask("hello")
        self.assertEqual(resp.status_code, 503)
        self.assertIn(settings.SUPPORT_EMAIL, resp.json()["reply"])

    def test_knowledge_base_is_consistent(self):
        from tr_chatbot.knowledge import INTENTS

        ids = [i["id"] for i in INTENTS]
        self.assertEqual(len(ids), len(set(ids)), "duplicate intent id")
        for intent in INTENTS:
            self.assertTrue(intent["questions"] and intent["answer"], intent["id"])
            for _label, route in intent.get("links", []):
                reverse(route.split("#")[0])  # raises if a link points to a page that does not exist

    def test_model_understands_its_own_training_data(self):
        from tr_chatbot.engine import ChatModel
        from tr_chatbot.knowledge import INTENTS

        report = ChatModel(INTENTS).evaluate()
        self.assertGreater(report["accuracy"], 0.40)
        self.assertGreaterEqual(report["intents"], 30)


# ---------------------------------------------------------------- who signs in from where
class LoginEventTests(ServiceCase):
    def setUp(self):
        super().setUp()
        self.user = make_user()

    def test_login_is_recorded_with_the_real_visitor_ip_and_location(self):
        resp = self.client.post(reverse("login"), {"username": "a@b.com", "password": PASSWORD}, HTTP_CF_CONNECTING_IP="8.8.4.4",
                                HTTP_USER_AGENT="Mozilla/5.0 (Macintosh; Intel Mac OS X) Chrome/120")
        self.assertEqual(resp.status_code, 302)
        event = LoginEvent.objects.get()
        self.assertEqual((event.user, event.success, event.ip), (self.user, True, "8.8.4.4"))
        self.assertEqual((event.country_code, event.city), ("UZ", "Tashkent"))
        self.assertEqual((event.lat, event.lng), (41.3, 69.2))
        self.assertEqual(event.where, "Tashkent, Uzbekistan")

    def test_proxy_header_wins_over_the_proxy_address(self):
        self.client.post(reverse("login"), {"username": "a@b.com", "password": PASSWORD}, HTTP_X_REAL_IP="1.1.1.1", REMOTE_ADDR="172.18.0.4")
        self.assertEqual(LoginEvent.objects.get().ip, "1.1.1.1")

    def test_local_addresses_are_not_sent_to_the_lookup_service(self):
        with mock.patch("tr_geocode.providers.fetch_json") as fetch:
            self.client.post(reverse("login"), {"username": "a@b.com", "password": PASSWORD})
        fetch.assert_not_called()
        self.assertEqual(LoginEvent.objects.get().city, "Local network")

    def test_failed_login_is_recorded_without_a_user(self):
        self.client.post(reverse("login"), {"username": "a@b.com", "password": "wrong"}, HTTP_CF_CONNECTING_IP="8.8.4.4")
        event = LoginEvent.objects.get()
        self.assertEqual((event.user, event.success, event.email), (None, False, "a@b.com"))

    def test_location_lookup_failure_never_breaks_sign_in(self):
        with mock.patch("tr_geocode.providers.fetch_json", side_effect=OSError("offline")):
            resp = self.client.post(reverse("login"), {"username": "a@b.com", "password": PASSWORD}, HTTP_CF_CONNECTING_IP="8.8.4.4")
        self.assertEqual(resp.status_code, 302)
        event = LoginEvent.objects.get()
        self.assertTrue(event.success)
        self.assertEqual(event.country_code, "")

    def test_garbage_ip_header_never_breaks_sign_in(self):
        resp = self.client.post(reverse("login"), {"username": "a@b.com", "password": PASSWORD}, HTTP_CF_CONNECTING_IP="not-an-ip")
        self.assertEqual(resp.status_code, 302)


# ---------------------------------------------------------------- the admin: real Django admin with the dashboard on top
class AdminDashboardTests(ServiceCase):
    def setUp(self):
        super().setUp()
        self.staff = make_staff()
        self.user = make_user(persona="farmer")

    def seed(self):
        """A few days of realistic activity, made through the real endpoints."""
        self.client.force_login(self.user)
        for _ in range(2):
            self.client.post(reverse("api-analyze"), {"geometry": SQUARE, "nickname": "Field"}, content_type="application/json")
        self.client.get(reverse("api-place-search"), {"q": "tashkent", "commit": "1"})
        self.client.get(reverse("api-place-search"), {"q": "tashkent", "commit": "1"})
        self.client.post(reverse("checkout", args=["plus"]))
        self.client.logout()
        self.client.post(reverse("login"), {"username": "a@b.com", "password": PASSWORD}, HTTP_CF_CONNECTING_IP="8.8.4.4")
        SystemEvent.objects.create(level="error", source="satellite", message="Earth Engine timed out")
        self.client.logout()

    def test_admin_link_goes_to_the_real_admin_and_console_redirects_there(self):
        self.client.force_login(self.staff)
        self.assertRedirects(self.client.get(reverse("console")), reverse("admin:index"), fetch_redirect_response=False)
        self.assertEqual(reverse("admin:index"), "/admin/")

    def test_only_staff_can_open_it(self):
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 302)       # anonymous -> admin login
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 302)       # regular user -> admin login
        self.assertEqual(self.client.get(reverse("admin:terra-live")).status_code, 302)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)

    def test_dashboard_shows_real_numbers(self):
        self.seed()
        self.client.force_login(self.staff)
        resp = self.client.get(reverse("admin:index"))
        html = resp.content.decode()
        self.assertEqual(resp.status_code, 200)
        for expected in ("Dashboard", "Where users sign in from", "Most searched places", "Yunusabad, Tashkent", "Tashkent", "Uzbekistan",
                         "Earth Engine timed out", "Plus", "td-data", "admin-dashboard.js"):
            self.assertIn(expected, html, expected)
        terra = resp.context["terra"]
        kpis = {k["key"]: k for k in terra["kpis"]}
        self.assertEqual(kpis["users"]["value"], 2)
        self.assertEqual(kpis["analyses"]["value"], 2)
        self.assertEqual(terra["places"]["searched"][0]["count"], 2)
        self.assertEqual(terra["places"]["analysed"][0]["name"], "Yunusabad, Tashkent")
        self.assertEqual(terra["geo"]["countries"][0]["code"], "UZ")
        self.assertEqual(terra["geo"]["cities"][0]["city"], "Tashkent")
        self.assertEqual(terra["revenue"][0]["label"], "Plus")
        json.dumps(terra)    # the page embeds it as JSON: everything must be serialisable

    def test_dashboard_works_on_an_empty_database(self):
        self.client.force_login(self.staff)
        resp = self.client.get(reverse("admin:index"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "No searches yet")
        self.assertContains(resp, "No analysed places yet")
        self.assertContains(resp, "No located sign-ins yet")

    def test_the_usual_django_admin_pages_still_work(self):
        self.seed()
        self.client.force_login(self.staff)
        for name in ("accounts_user", "analysis_parcel", "accounts_loginevent", "analysis_searchevent", "accounts_purchase", "analysis_systemevent"):
            self.assertEqual(self.client.get(reverse(f"admin:{name}_changelist")).status_code, 200, name)
        self.assertContains(self.client.get(reverse("admin:index")), "Manage data")

    def test_live_endpoint_reports_every_service(self):
        self.client.force_login(self.staff)
        body = self.client.get(reverse("admin:terra-live")).json()
        self.assertEqual([s["name"] for s in body["services"]], ["analysis", "satellite", "risk", "advisory", "report", "billing", "geocode", "chatbot"])
        self.assertTrue(all(s["up"] for s in body["services"]), body["services"])
        self.assertTrue(body["database"]["ok"])
        self.assertEqual(body["mode"], "inprocess")

    def test_live_endpoint_shows_a_dead_service_without_failing(self):
        install("satellite", dead_client("satellite"))
        self.client.force_login(self.staff)
        body = self.client.get(reverse("admin:terra-live")).json()
        satellite = next(s for s in body["services"] if s["name"] == "satellite")
        self.assertFalse(satellite["up"])
        self.assertEqual(satellite["status"], "down")
        self.assertTrue(next(s for s in body["services"] if s["name"] == "risk")["up"])


class DashboardDataTests(ServiceCase):
    def test_flags(self):
        self.assertEqual(dashboard.flag("UZ"), "\U0001F1FA\U0001F1FF")
        self.assertEqual(dashboard.flag("us"), "\U0001F1FA\U0001F1F8")
        self.assertEqual((dashboard.flag(""), dashboard.flag("USA"), dashboard.flag(None)), ("", "", ""))

    def test_change_is_none_without_a_previous_period(self):
        self.assertIsNone(dashboard._change(5, 0))
        self.assertEqual(dashboard._change(15, 10), 50)
        self.assertEqual(dashboard._change(5, 10), -50)

    def test_heatmap_puts_sign_ins_in_the_right_weekday_and_hour(self):
        user = make_user()
        moment = timezone.now().replace(hour=14, minute=5)
        event = LoginEvent.objects.create(user=user, success=True)
        LoginEvent.objects.filter(pk=event.pk).update(created_at=moment)
        grid = dashboard.activity_heatmap()["grid"]
        self.assertEqual(grid[moment.weekday()][14], 1)
        self.assertEqual(sum(map(sum, grid)), 1)

    def test_time_series_cover_the_requested_days(self):
        make_user()
        growth = dashboard.growth(30)
        self.assertEqual(len(growth["labels"]), 30)
        self.assertEqual(sum(sum(s["values"]) for s in growth["series"]), 1)
        self.assertTrue(all(len(s["values"]) == 30 for s in growth["series"]))

    def test_old_events_fall_out_of_the_week_numbers(self):
        user = make_user()
        old = LoginEvent.objects.create(user=user, success=False)
        LoginEvent.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=20))
        security = next(k for k in dashboard.kpis() if k["key"] == "security")
        self.assertEqual(security["value"], 0)

    def test_shares_are_relative_to_the_biggest_row(self):
        rows = dashboard._shares([{"value": 10}, {"value": 5}, {"value": 0}])
        self.assertEqual([r["share"] for r in rows], [100, 50, 0])
        self.assertEqual(dashboard._shares([]), [])

    def test_device_names(self):
        self.assertEqual(dashboard._device("Mozilla/5.0 (iPhone; CPU iPhone OS 17) Safari/604"), "Safari · iPhone")
        self.assertEqual(dashboard._device("Mozilla/5.0 (Windows NT 10.0) Chrome/120 Edg/120"), "Edge · Windows")
        self.assertEqual(dashboard._device(""), "Unknown")


class TeamTests(SimpleTestCase):
    def test_team_data_is_complete(self):
        for member in team_members():
            self.assertTrue(member["name"] and member["role"] and member["initials"])


# ---------------------------------------------------------------- the web app must not depend on service internals
class BoundaryTests(SimpleTestCase):
    def test_web_code_only_talks_to_services_through_the_gateway(self):
        """Views, models and templates may import tr_common (the client library) but never a service's own package."""
        import pathlib
        import re

        root = pathlib.Path(settings.BASE_DIR)
        offenders = []
        for folder in ("accounts", "analysis", "core", "config"):
            for path in (root / folder).rglob("*.py"):
                if path.name in ("tests.py", "testing.py") or "migrations" in path.parts:
                    continue
                text = path.read_text()
                if re.search(r"^\s*(from|import)\s+tr_(analysis|satellite|risk|advisory|report|billing|geocode|chatbot)\b", text, re.M):
                    offenders.append(str(path.relative_to(root)))
        self.assertEqual(offenders, [])
