# TerraRisk AI

Hyper-local climate and upstream-hazard analysis. A Django website plus **eight microservices** (satellite, risk, advisory,
report, billing, geocode, chatbot and an analysis orchestrator), deployable with Docker Compose on an Azure VM.
The design, the reasons for every boundary and the failure behaviour are in **[ARCHITECTURE.md](ARCHITECTURE.md)**.

## What works

| Feature | Notes |
|---|---|
| Landing page (visitors) | Hero, three persona cards (each opens signup with that persona selected), how it works, team |
| Home (signed-in users) | Replaces the sign-up marketing: stats, recent analyses with place names, "needs attention", tips for the user's persona, searches left, shortcuts, account menu in the navbar |
| Signup, login, profile | Email is the username. Every sign-in is recorded (with the visitor's city/country) for the admin |
| Plans (`/pricing/`) | Free 5, Starter 20, Plus 30, Pro 50, Business 100, Unlimited (30 days). Served by the **billing** service |
| Support, Terms, Privacy, chat assistant | FAQ and chat come from the **chatbot** service |
| Map platform | Draw polygon/rectangle/pin, 3-5 km buffer ring, place search, **place names on the map** (Esri labels, or Google tiles with a key), Run AI Diagnosis |
| Results page | Different page per user type. Satellite pictures at 1600x1000 (true colour, vegetation, heat, water) with boundary, scale bar and north arrow, "why this score" bars, checklist, written advice. Investors also get flags and what-if scenarios |
| PDF certificate | Multi-page: score, factors, **four satellite pictures**, hazard cards, charts, scenarios, checklists, method and limits. Built by the **report** service |
| Admin (`/admin/`, staff only) | The real Django admin. Its home page is a dashboard: users, growth, **where users sign in from** (map + countries + latest sign-ins), **most searched / analysed places**, risk mix, revenue, live service health, server CPU/memory, events |
| Health check (`/healthz/`) | Public JSON for uptime monitors |
| Docker, Nginx, Postgres, GitHub Actions | Push to `main` runs all tests and redeploys |

## Run it on your laptop (no Docker)

```bash
python -m venv .venv
source .venv/bin/activate                  # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt        # the website AND all services (they run inside Django in this mode)
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser           # username = your email; this account can open /admin/
python manage.py runserver                 # http://127.0.0.1:8000
```

**Tests:**

```bash
python -m unittest discover -s services/tests -t services     # the 8 services on their own (65 tests)
python manage.py test                                         # the website with the services in-process (105 tests)
```

### See the real microservice behaviour without Docker

```bash
python scripts/run_services.py             # terminal 1: starts the 8 services on ports 8101-8108, prints the .env lines
SERVICES_MODE=http python manage.py runserver     # terminal 2 (put the printed URL lines in .env or export them)
python scripts/e2e_check.py                # terminal 3: checks every service over real HTTP
```

Stop a service (for example `satellite`) and try an analysis: the website says so politely and no search is used.

### Run it with Docker

```bash
cp .env.example .env     # set INTERNAL_TOKEN (any long random text), DJANGO_SECRET_KEY, POSTGRES_PASSWORD
docker compose up -d --build
docker compose exec web python manage.py createsuperuser
docker compose ps        # all containers should become "healthy"
```

Only the `proxy` container publishes a port (80). The services are on a private network and refuse calls without the
`INTERNAL_TOKEN`.

## Things you will edit most

| What | Where |
|---|---|
| Team names, roles, photos, social links | `core/team.py` and `static/img/team/` |
| Footer email and social links | `.env`: `SUPPORT_EMAIL`, `INSTAGRAM_URL`, `TWITTER_URL`, `GITHUB_URL` |
| Plan sizes and prices | `services/billing/tr_billing/plans.py` **and** `accounts/plans.py` (the website's fallback copy; a test fails if they differ) |
| Persona text and pictures | `accounts/personas.py`, `static/img/personas/*.svg` |
| What the chatbot knows | `services/chatbot/tr_chatbot/knowledge.py`, then `cd services/chatbot && PYTHONPATH=../common:. python -m tr_chatbot.train` (prints a quality report) |
| Risk score weights, persona cards, scenarios | `services/risk/tr_risk/` |
| Satellite layers, colours, picture size | `services/satellite/tr_satellite/` |
| PDF layout | `services/report/tr_report/pdf.py` (bump `REPORT_VERSION` in `analysis/views.py` so old PDFs are rebuilt) |
| Admin dashboard numbers / look | `core/dashboard.py`, `templates/admin/terra_index.html`, `static/css/admin-dashboard.css`, `static/js/admin-dashboard.js` |

### Place names on the map
By default the map shows Esri satellite imagery with Esri's free *place-name* and *road* label layers, and place search
uses OpenStreetMap's Nominatim (through the geocode service, cached, 1 request per second as Nominatim asks).
**To use real Google Maps tiles** instead: create a Google Cloud project, enable **Map Tiles API**, turn on billing
(Google gives a monthly free allowance), create an API key restricted to that API, and set `GOOGLE_MAPS_API_KEY` in `.env`.
Google's terms require showing their attribution (the map does) and do not allow caching or downloading their tiles.
This path was written to Google's documentation but has not been run with a real key.

### Plans and payment
Checkout runs in **demo mode** (`PAYMENTS_DEMO=True`): the plan is activated and a purchase recorded, nobody is charged. For
real payments connect a provider (for example Stripe Checkout) inside the billing service (`checkout` in
`services/billing/tr_billing/app.py`), then set `PAYMENTS_DEMO=False`. Never store card numbers yourself.

### Rebuild the CSS (only if you add new Tailwind classes to templates)
The site uses a pre-built `static/css/tailwind.css`. If you write a Tailwind class that is not styled yet: either set
`TAILWIND_CDN=True` in `.env` while developing, or (needs Node.js) `npm install` then `npm run build:css`.

## Demo data vs real data

`USE_FAKE_DATA=True` (default) gives deterministic demo values and clearly labelled illustrations, so everything works
with no accounts or keys. The results page and the PDF say "Demo" whenever demo data was used.

**Real satellite data (Google Earth Engine)** is read by the **satellite** service:
1. Create a Google Cloud project and register it for Earth Engine (non-commercial use).
2. Create a service account with Earth Engine access and download its JSON key.
3. Save the key as `secrets/gee-key.json` (git-ignored) and set in `.env`: `GEE_PROJECT`, `GEE_SERVICE_ACCOUNT`,
   `GEE_KEY_FILE=/run/secrets/gee-key.json` (Docker) or the path on your laptop, and `USE_FAKE_DATA=False`.
4. Run an analysis. A query can take 10-60 seconds. If Earth Engine fails the user sees a clear message, no search is used,
   and the error appears on the admin dashboard.

Datasets: SRTM (slope), JRC Global Surface Water (river distance), MODIS MOD13Q1 (NDVI), MODIS MOD11A2 (land surface
temperature), ERA5-Land (soil moisture), CHIRPS (rain), MERIT Hydro, ESA WorldCover; pictures from Sentinel-2 and Landsat
over Esri World Imagery. **The Earth Engine code and the live Esri imagery path have never been run against the real
services while this was written; test them once with your credentials.** Check Esri's and Google's terms before using the
imagery commercially.

**Written advice:** set `GEMINI_API_KEY` (and optionally `GEMINI_MODEL`). Without it, built-in templates are used; if
Gemini fails, templates are used and a warning is logged. The key is read by the **advisory** and **chatbot** services
(`scripts/run_services.py` and Docker Compose pass it on from `.env`).

**Azure Blob (PDF reports):** set `AZURE_ACCOUNT_NAME`, `AZURE_ACCOUNT_KEY`, `AZURE_CONTAINER`.

## Deploy on an Azure VM

1. Create an Ubuntu VM (B2s or larger; there are 11 containers), open ports 22, 80, 443.
2. Install Docker, `git clone` the repo to `~/terrarisk`, copy `.env.example` to `.env` and set at least: `INTERNAL_TOKEN`,
   `DJANGO_DEBUG=False`, a long random `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS=your-domain,VM-IP`,
   `CSRF_TRUSTED_ORIGINS=https://your-domain`, a strong `POSTGRES_PASSWORD`, `SERVICES_MODE` is set to `http` by compose.
3. `docker compose up -d --build`, then `docker compose exec web python manage.py createsuperuser`.
4. GitHub repo, Settings, Secrets: `AZURE_VM_HOST`, `AZURE_VM_USER`, `AZURE_VM_SSH_KEY`. Every push to `main` runs the tests and redeploys.
5. Migrations are committed in `accounts/migrations` and `analysis/migrations`; the container runs `migrate` on start.

**Moving from the old monolith:** existing users keep their balance (the website sends it to billing the first time that
user is seen), existing parcels keep working (their persona view and place name are rebuilt the first time they are opened).
Billing data (balances) now lives in the billing volume: back it up (`billing_data`) together with Postgres.

**HTTPS:** put the domain on Cloudflare, A record to the VM, SSL/TLS mode "Full", `USE_HTTPS=True` in `.env`. Cloudflare
serves HTTPS; Nginx stays on port 80. The admin's "where users sign in from" uses the `CF-Connecting-IP` header Cloudflare
adds. Without Cloudflare the header can be forged by a visitor, so treat that chart as informational, never as security.

## Project map

```
accounts/   user model, plans (fallback copy), personas, signup, login, profile, LoginEvent, sign-in recording (signals.py)
core/       landing/home, pricing + checkout, support, chat BFF, map page, admin site + dashboard data (dashboard.py)
            services.py = the ONLY place that talks to the services; testing.py = helpers for the tests
analysis/   Parcel, SearchEvent, SystemEvent models, /api/analyze/, place search BFF, results page, saved parcels, PDF download
templates/  static/   pages, CSS, JS (map.js, dashboard.js, nav.js, admin-dashboard.js)
services/
  common/     tr_common: service skeleton (health, token, JSON errors), HTTP client (timeouts, retry, circuit breaker), registry
  analysis/   orchestrator            satellite/  Earth Engine, Esri imagery, pictures, cache
  risk/       models, score, persona views, scenarios (models/*.pkl)        advisory/  Gemini or templates
  report/     PDF                     billing/    accounts, credits, ledger (SQLite)
  geocode/    place search, names, IP lookup (SQLite cache)                 chatbot/   intent model
  tests/      65 tests, one file per service
scripts/    run_services.py (8 local processes), e2e_check.py (checks a running stack)
ml/         dataset building and model training (writes into services/risk/tr_risk/models/)
nginx/  docker-compose.yml  Dockerfile (web)  services/Dockerfile (all services)
```

## Landslide model (added by the AI member)

A second model scores **landslide susceptibility** (0-100) next to the flood-type score. The final risk score is
`0.5 x flood + 0.5 x landslide` (weights in `services/risk/tr_risk/scoring.py`). If `landslide_model.pkl` is missing the
site still works with the flood score only.

```
data/raw/Global_Landslide_Catalog_Export_rows.csv   NASA landslide catalog (raw)
ml/prepare_landslide_data.py   cleans the catalog       -> data/processed/landslide_events_clean.csv
ml/build_dataset.py            adds satellite features from Google Earth Engine (needs GEE login)
                                                         -> data/processed/landslide_satellite_features.csv
ml/train_landslide_model.py    trains + saves            -> services/risk/tr_risk/models/landslide_model.pkl
ml/train_model.py              flood model (see limits)  -> services/risk/tr_risk/models/hazard_model.pkl
```

Inputs (5): NDVI, peak land-surface temperature, soil moisture, slope, elevation. Retrain with the three commands above,
then rebuild the risk image (`docker compose up -d --build risk`). Honest limit: cross-validated AUC is about 0.70, so
treat the score as a relative index, not a probability.

## Known limits (be honest about these in your report)

- Never run against the real services in the sandbox that built this version: Earth Engine, Esri tiles, Google Map Tiles,
  Nominatim, ipwho.is, and the Docker image builds. See ARCHITECTURE.md section 10.
- The what-if scenarios show sensitivity; they are not forecasts. Land subsidence and road-level landslide risk are not measured.
- The flood model labels come from a formula plus noise (no public dataset maps these features to a risk score). Replace
  `make_dataset()` in `ml/train_model.py` with real flood or landslide records when you have them.
- The chatbot is a small intent model, not a general AI (about 8 in 10 fresh questions in the team's tests).
- Checkout is a demo: no real payment, invoice or automatic renewal.
- IP-based sign-in locations are city-level guesses.
