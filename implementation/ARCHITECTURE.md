# TerraRisk AI: architecture

TerraRisk started as one Django project (a monolith: pages, satellite code, the risk model, advice, PDF and billing all
inside one process). It is now **a website plus eight small services**, split with the *disaggregation* method from the
cloud-computing lectures (the "Disaggregating the Shopping App" example): find the functional boundaries inside the
monolith, give every boundary its own process, its own API and its own data, and keep one place that owns the user
interface.

This file explains what was split, **why the lines are where they are** (the granularity question), the two payment
designs we compared, what happens when a service dies, and how to run it. Every statement here describes code that is in
this repository; the last section lists what has **not** been tested.

---

## 1. The picture

```
                              internet
                                 |
                          +------v------+        only this container publishes a port (80)
                          |    proxy    |        nginx: static files, gzip, passes the visitor's real IP
                          +------+------+
 edge network                    |
 -------------------------------+----------------------------------------------------------------
 backend network (private)       |
                          +------v------+      +-----------+
                          |     web     +------>  Postgres |   users, parcels, sign-in log, search log, events
                          |   Django    |      +-----------+
                          | pages, auth |
                          | admin, BFF  |
                          +--+--+--+--+-+
        HTTP + JSON,         |  |  |  |  \
        X-Service-Token      |  |  |  |   +-------------------------+
                 +-----------+  |  |  +-----------+                 |
                 |              |  |              |                 |
          +------v-----+  +-----v--v---+   +------v-----+    +------v-----+
          |  analysis  |  |   billing  |   |   report   |    |  chatbot   |
          |orchestrator|  | credits,   |   | PDF        |    | help bot   |
          +--+--+--+---+  | purchases  |   | certificate|    +------------+
             |  |  |      | (SQLite)   |   +------+-----+
             |  |  |      +------------+          |
   +---------+  |  +---------+                    |
   |            |            |                    |
+--v------+ +---v----+ +-----v-----+       +------v-----+      +------------+
|satellite| |  risk  | | advisory  |       | satellite  |      |  geocode   |  <- also called by analysis and web
|GEE+Esri | | models,| | Gemini or |       | (pictures) |      | Nominatim, |
| (cache) | | views  | | templates |       +------------+      | ipwho.is   |
+---------+ +--------+ +-----------+                           | (SQLite)   |
                                                               +------------+
```

* **web** is the only thing a browser talks to. It owns the user interface, login, the Django admin and the database
  rows that describe *people and their parcels*. It never imports service code; it calls
  `core/services.py`, which turns HTTP answers into plain Python results or two exceptions (`Unavailable`, `Rejected`).
* **analysis** is the *orchestrator*: one call from the web ("analyse this polygon") fans out to satellite, risk,
  advisory and geocode and returns one combined answer.
* The other seven services each do exactly one job and own their data. Services call each other only where the arrows
  show; nothing calls `web`.

---

## 2. Disaggregating the monolith

Method (from the lecture): *(1)* list what the monolith does, *(2)* group it by things that change together and fail
together, *(3)* cut at those lines, *(4)* give every piece its own data, *(5)* decide how the pieces talk and what
happens when one of them is gone.

| In the monolith (old module) | Became | What moved with it |
|---|---|---|
| `analysis/services/gee_service.py`, `satellite.py` | **satellite** | Earth Engine features (slope, river distance, NDVI, heat, soil moisture, rainfall...), demo generator, satellite pictures, picture cache |
| `analysis/services/ml_service.py`, `persona_view.py`, `headline.py`, `scenarios.py`, `ml_models/*.pkl` | **risk** | flood + landslide models, the score, "what matters for you" per persona, what-if scenarios |
| `analysis/services/advisory_service.py` | **advisory** | Gemini call with template fallback |
| `analysis/reports.py` | **report** | PDF builder, charts for the PDF, satellite pictures in the PDF |
| `accounts/billing.py`, `accounts/plans.py` (credit logic) | **billing** | accounts, search credits, purchases, idempotent ledger |
| Nominatim calls in `map.js` (browser straight to a third party) | **geocode** | place search, "what is this place called", IP to country, a cache |
| `core/chatbot/*` | **chatbot** | intent model, knowledge file, optional Gemini fallback |
| `analysis/services/pipeline.py` | **analysis** | the workflow: which step is critical, which is optional |
| everything else (templates, views, models, login, admin) | **web** | unchanged in purpose; now talks to the services |

Package names are `tr_<service>` (for example `tr_risk`) so that two services can never shadow each other's modules.

---

## 3. The granularity question

*How big should a service be?* Too big and you have a monolith with extra steps; too small and every request becomes a
chain of network calls that can each fail. The rule we used: **cut where the failure behaviour, the data, or the rate of
change differs; do not cut where two parts always change and fail together.**

| Decision | Why |
|---|---|
| **satellite** is one service for features *and* pictures | Same Earth Engine session, same credentials, same cache, same "demo or live" switch. Splitting would duplicate all of that and the two halves are never useful alone. |
| **risk** is one service for score, persona view and scenarios | They are one model family and always change together (a new factor changes the score, the bars and the scenarios). The service is stateless, so it scales by running more copies. |
| **advisory** is separate from **risk** | Different failure mode: it calls an external LLM that is slow (seconds) and sometimes down. Isolating it means a Gemini outage only removes the written advice, never the score. |
| **billing** is separate and has its own database | Money and credits need strict consistency (one writer, a ledger); everything else is "best effort". It is also the part you must never lose, so it is the one with the smallest, most boring code. |
| **geocode** is separate | A third party with a policy (Nominatim: 1 request/second, identify yourself) and an answer that is perfect for caching. One place enforces the policy for the whole system. |
| **report** is separate | CPU-heavy, needs different libraries (ReportLab, Pillow), and a slow PDF must not block page requests. |
| **chatbot** is separate | Independent of everything else; if it is down, only the chat bubble apologises. |
| **analysis** exists at all | Without it, the *web* app would have to know the order of four calls and what to do when each fails. With it, the web asks one question. **Cost:** one extra network hop on every analysis (a few milliseconds locally) and one more service to run. We accepted that because it keeps the workflow in one place and keeps `web` thin. |

What we deliberately did **not** split: *accounts/login* (stays in Django, because sessions, CSRF and the admin are
built around the user table), *parcels* (the user's own data, owned by web), and *scoring vs. features* (the risk
service receives numbers, not satellite objects, so those two are already separated by a clear data contract).

Things that would be reasonable to split later if the project grows: persona views out of `risk` (if designers want to
change them without touching models), a queue in front of `report`.

---

## 4. Two designs for payment (and the one we chose)

Payment is where the lecture's "two alternative designs" matter most, because it is the one place where a wrong answer
costs real money. Both designs were considered for the search credits and the plan purchases:

**Design A: the web app owns the balance.** `User.free_searches` in the Django database is the truth; checkout and
"use one search" are ordinary Django code that updates that column.
* + One database transaction covers "create parcel" and "use one credit" together. Simple.
* - Payment logic is welded to the website: it cannot be reused, scaled or secured separately, and the web database
  (which many things can touch, including admins) is the money ledger.
* - A bug anywhere in the website's code can change balances.

**Design B: a billing service owns the balance.** The web asks billing to *consume*, *refund* and *checkout*. Billing
has its own database and an append-only **ledger**.
* + Small surface, one writer, auditable, replaceable by a real payment provider without touching the website.
* - Two databases mean you can no longer use one transaction: "use a credit" and "save the parcel" can disagree if
  something fails in between. This needs a compensating action (refund) and **idempotency keys**.
* - One more thing that can be down.

**Chosen: Design B**, with these mechanisms so the two-database problem is handled instead of ignored:

1. **Reserve first, work second.** `AnalyzeView` calls `billing.consume(key)` *before* doing the expensive analysis.
2. **Compensate on failure.** If the analysis fails, or saving the parcel fails, the same `key` is sent to `billing.refund`. A failed analysis costs nothing.
3. **Idempotency.** `ledger.idem_key` is `UNIQUE`: sending the same consume or refund twice (a retry after a timeout) changes the balance once. Covered by tests.
4. **Billing is the source of truth.** The `free_searches`, `plan_key` and `unlimited_until` columns on the web `User` are a *cached copy* refreshed after every billing call, so pages render without a network call. Editing the copy gives no free searches (tested).
5. **Fail closed.** If billing cannot be reached, analysis is **refused** with "nothing was charged" (HTTP 503). We never hand out free analyses because a service is down (tested).
6. **First contact migration.** The first time the web talks to billing about an existing user it passes the balance that user already had (`initial`), so accounts created by the old monolith keep their credits.
7. **Demo payments.** `PAYMENTS_DEMO=True` records a purchase without charging anyone. With `False`, checkout answers 501 until a real provider (for example Stripe Checkout) is connected inside the billing service. No card data ever touches our code.

Sequence of one analysis:

```
browser -> web: POST /api/analyze/
web     -> billing: PUT  /v1/accounts/7          (ensure account; passes the old balance once)
web     -> billing: POST /v1/accounts/7/consume  {key: "analysis:ab12"}      -> 4 left
web     -> analysis: POST /v1/analyze            (satellite, risk, advisory, geocode)
          failure?  -> web -> billing: POST /refund {key: "analysis:ab12"}   -> 5 left,  answer 502
web     -> Postgres: INSERT parcel               failure? -> refund, answer 500
web     -> browser: 201 {id, redirect}
```

---

## 5. How the services talk

* **Protocol:** HTTP + JSON over a private network. Every API route is under `/v1/...` so the API can evolve.
* **Trust:** every call carries `X-Service-Token` (the shared `INTERNAL_TOKEN`); a service answers 401 without it (except
  `/healthz`). No service port is published to the internet; only `proxy` is. The token is a second lock, not the first:
  the network is the first.
* **Tracing:** `X-Request-ID` is created at the edge and passed on, so one user action can be followed through all logs
  (`docker compose logs | grep <id>`). Every service logs one JSON line per request.
* **Every service exposes** `GET /healthz` (readiness: is my database/model/credentials OK?) and `GET /v1/info`
  (version, uptime, request and error counters, last error). The admin dashboard shows them live.
* **Errors:** always JSON `{"error": "...", "message": "..."}` with a proper status code (400 bad input, 401, 404, 502 a
  dependency failed, 503 unavailable). The web app translates them in one place (`core/services.py`).
* **The client** (`tr_common/client.py`) gives every call a timeout, retries a GET once, and has a **circuit breaker**:
  after 5 failures in a row the circuit opens for 15 seconds and calls fail immediately instead of piling up behind a dead
  service.
* **Timeouts** (seconds): analysis 170, satellite 130, report 120, advisory 30, chatbot 25, risk 15, geocode 10, billing 10.

### Service APIs

| Service | Routes | Owns |
|---|---|---|
| **analysis** | `POST /v1/analyze` | nothing (stateless) |
| **satellite** | `POST /v1/features`, `GET /v1/layers`, `POST /v1/layers/<truecolor\|ndvi\|heat\|water>` | picture cache (files) |
| **risk** | `POST /v1/score`, `POST /v1/view`, `GET /v1/model` | model files (read-only) |
| **advisory** | `POST /v1/advice` | nothing |
| **report** | `POST /v1/reports` | nothing (fetches the 4 satellite pictures in parallel) |
| **billing** | `GET /v1/plans`, `PUT/GET /v1/accounts/<id>`, `POST /v1/accounts/<id>/consume`, `/refund`, `/checkout`, `GET /v1/stats` | accounts, purchases, ledger (SQLite) |
| **geocode** | `GET /v1/search?q=`, `GET /v1/reverse?lat=&lng=`, `GET /v1/ip/<address>` | answer cache (SQLite) |
| **chatbot** | `POST /v1/chat`, `POST /v1/faq` | intent model |

The shapes of the requests and answers are documented at the top of each `services/<name>/tr_<name>/app.py`.

### Who owns which data (database per service)

| Data | Owner | Note |
|---|---|---|
| users, parcels (incl. the stored persona view), sign-in log, search log, system events | **web** (Postgres) | the user-facing record |
| balances, purchases, ledger | **billing** (SQLite file on a volume) | source of truth for money/credits |
| place-name and search cache | **geocode** (SQLite file) | can be deleted at any time |
| satellite pictures | **satellite** (files) | can be deleted at any time |
| models | **risk** (files, in the image) | built by `ml/` scripts |

No service reads another service's database. If you need billing numbers (the admin revenue chart shows purchases that
web recorded at checkout time), you ask billing's API.

---

## 6. When something breaks (the degrade matrix)

The orchestrator (`services/analysis/tr_analysis/flow.py`) decides what is **critical** (no answer without it) and what
is **optional** (answer without it, say what is missing).

| Service down | What the user sees | Admin sees |
|---|---|---|
| **satellite** | Analysis fails with a clear message, **no credit is used**. Existing results still open; pictures show a "try again" placeholder (not cached). | error event, red service row |
| **risk** | Analysis fails, no credit used. Saved parcels with a stored view still open; very old parcels cannot rebuild their view and the user is sent back to the list with a message. | error event |
| **billing** | Analysis and checkout are refused (**fail closed**), nothing charged. Browsing results, the pricing page (built-in plan copy) and everything else keep working. | error event |
| **advisory** | Analysis works; the written advice box says it is missing. | warning event |
| **geocode** | Analysis works; the place shows as coordinates. Map search says "not available right now, pan the map". Sign-ins are stored without a location. | warning event |
| **report** | PDF button returns to the results page with a message. | error event |
| **chatbot** | The chat bubble answers "taking a short break, email us". Support page shows contact details without FAQ. | none |
| **analysis** | Analysis fails, no credit used. | error event |

Each row above is a test in `analysis/tests.py` or `core/tests.py`.

---

## 7. The website (BFF) and the admin

* **Pages:** landing (visitors) / home (signed-in users), map platform, results, saved parcels, pricing and checkout,
  support, profile.
* **Place names on the map:** the browser asks `GET /api/places/search` and `/api/places/reverse` on the website (login
  and rate limits apply, and pressing Enter in the search box is logged); the website asks the geocode service.
  The map draws Esri satellite imagery plus Esri's free *place-name* and *road* label layers. With
  `GOOGLE_MAPS_API_KEY` it uses Google's Map Tiles API instead (see README).
* **Admin = the real Django admin** at `/admin/`. Its home page is the TerraRisk dashboard (users, growth, sign-in
  map and countries, most searched and analysed places, risk mix, revenue, services and server health, events), and every
  Django model page (users, parcels, purchases, sign-in log, search log, system events) is one click away. The old
  `/console/` address redirects there. Only staff users can open it.
* **Sign-in locations:** a Django signal stores every sign-in (and failed attempt) with the visitor's IP (from
  `CF-Connecting-IP` or `X-Real-IP`); a background thread asks the geocode service (ipwho.is) for the city/country so
  signing in never waits. Private addresses are never sent to the outside.

---

## 8. Deployment

`docker-compose.yml` defines **11 containers**: `proxy`, `web`, `db` and the 8 services. Two networks: `edge`
(proxy to web) and `backend` (everything else, nothing published). Each service has a health check, a restart policy,
log rotation, and a volume only if it owns files. The services use gunicorn with **one worker and eight threads** on
purpose: they keep counters and caches in memory and SQLite wants one writer; scale by running more containers.

```bash
cp .env.example .env                      # set INTERNAL_TOKEN, DJANGO_SECRET_KEY, POSTGRES_PASSWORD, ...
docker compose up -d --build
docker compose exec web python manage.py createsuperuser
docker compose ps                         # every service should become "healthy"
```

Three ways to run the *same code*:

| Mode | How | Use for |
|---|---|---|
| in-process | `SERVICES_MODE=inprocess` (default), `python manage.py runserver` | laptops, unit tests: nothing else to start |
| separate processes | `python scripts/run_services.py` then `SERVICES_MODE=http python manage.py runserver` | seeing the real HTTP behaviour without Docker |
| containers | `docker compose up -d --build` | production |

The in-process transport calls the Flask apps directly (no sockets) through the same client class, so the two modes
cannot drift apart.

---

## 9. Testing

| What | Command | Count |
|---|---|---|
| each service on its own (API contract, failure behaviour, the PDF) | `python -m unittest discover -s services/tests -t services` | 65 |
| the website with services in-process (pages, billing flow, degrade matrix, admin dashboard, login recording) | `python manage.py test` | 105 |
| a running stack over real HTTP | `python scripts/e2e_check.py` (and `--web http://localhost:8000 --email ... --password ...`) | about 25 checks |

Contract tests worth knowing: the plans in the billing service and the web app's built-in fallback copy must match; the
satellite layer names the pages offer must exist in the satellite service; web code may not import another service's
package (only `tr_common`).

CI (`.github/workflows/deploy.yml`) runs all of the above plus `makemigrations --check` and `docker compose config`
before it deploys.

---

## 10. Honest limits

* **Never run against the real thing here:** Google Earth Engine, Esri World Imagery tiles, Google Map Tiles, Nominatim
  and ipwho.is, a Docker daemon (so the images were not built and gunicorn was not started). Demo mode, in-process mode
  and separate HTTP processes (Flask's development server) were exercised, and the compose file and Dockerfiles were checked
  for syntax only. **The first `docker compose up` on a real machine is the first real test of the container build.**
* The admin sign-in and parcel *maps* need the internet (Leaflet from unpkg, Esri tiles). The map code was run against a
  stub of Leaflet and showed no errors, but was never drawn by real Leaflet in a browser.
* Billing uses SQLite on one volume: fine for this project, not for several billing replicas. Moving it to Postgres is a
  small change in `store.py`.
* Location from an IP address is a city-level guess; VPNs and mobile networks make it wrong sometimes.
* Scores are screening indices, not engineering or insurance opinions. The flood model is trained on labels made from a
  formula plus noise (see README); the landslide model has a cross-validated AUC of about 0.70.
* The services trust each other through a shared token on a private network. That is appropriate for one VM; for a
  public cloud with several hosts add mTLS or a service mesh.
* Not implemented: asynchronous jobs/queues (the PDF is built while the user waits), distributed tracing beyond the
  request id, autoscaling.
