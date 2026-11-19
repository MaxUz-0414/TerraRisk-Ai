# Integration Design

| | |
|---|---|
| **Owner** | Abduraimboy Murodullaev (Leader). Consulted: all members |
| **Version / date** | 1.0, 19 November 2026 |
| **Code** | `4-Implementation/config/`, `core/` (`services.py`, `views.py`, `urls.py`), `analysis/`, `services/analysis/`, `services/geocode/` |

## 1. The website as the single gateway (BFF)

The browser talks only to **web**. Web never imports service code: `core/services.py` is the only door. It turns HTTP
answers into plain data or two exceptions: `Unavailable` (service could not be reached or failed: show a message or degrade)
and `Rejected` (the service understood and said no: bad input, no searches left). This is enforced by a test
(`BoundaryTests`) and by the code rule in the Project Standards.

## 2. One analysis, step by step

```
browser -> web   POST /api/analyze/          (login required, geometry validated in analysis/geo.py)
web     -> billing  consume(key)             reserve one search first; refused => HTTP 503, nothing charged
web     -> analysis POST /v1/analyze         the orchestrator (services/analysis/tr_analysis/flow.py)
            1 satellite /v1/features         CRITICAL   the features everything else is computed from
            2 geocode   /v1/reverse          optional   place name (runs in the background)
            3 risk      /v1/score            CRITICAL   composite score + hazard cards
            4 risk      /v1/view             critical for the page: persona view, headline, scenarios
            5 advisory  /v1/advice           optional   written advice (templates if Gemini is down)
failure  -> web -> billing refund(key)       the same key; a failed analysis costs nothing
web     -> PostgreSQL INSERT parcel          failure => refund, HTTP 500
web     -> browser 201 {id, redirect}
```

## 3. Public endpoints of the website

| Route | View | Purpose |
|---|---|---|
| `/`, `/platform/`, `/pricing/`, `/pricing/checkout/<key>/`, `/support/`, `/terms/`, `/privacy/` | `core/views.py` | pages |
| `/chat/` | `ChatView` | browser → chatbot service |
| `/healthz/` | `HealthView` | public JSON for uptime monitors |
| `/console/` | `ConsoleRedirectView` | redirects to `/admin/` |
| `/api/analyze/` | `AnalyzeView` | run an analysis |
| `/api/places/search/`, `/api/places/reverse/`, `/api/map/config/` | `analysis/places.py` | place names (login and rate limits apply) |
| `/dashboard/<id>/`, `/parcels/`, `/parcels/<id>/satellite/<layer>/`, `/parcels/<id>/report/`, `/parcels/<id>/delete/` | `analysis/views.py` | results, saved parcels, pictures, PDF |
| `/accounts/signup/`, `/login/`, `/profile/`, `/logout/` | `accounts/` | accounts |
| `/admin/` | Django admin | the dashboard (home page) and every model |

## 4. Data owned by the website (PostgreSQL; SQLite when no database is configured)

| Model | App | Holds |
|---|---|---|
| `User` | accounts | email login, persona, cached copy of the billing balance (`free_searches`, `plan_key`, `unlimited_until`) |
| `Purchase` | accounts | what the website recorded at checkout time (for the revenue chart) |
| `LoginEvent` | accounts | every sign-in or failed attempt: time, IP, city and country, device |
| `Parcel` | analysis | the user's drawn area, score, features, hazards, advice, persona view snapshot, PDF |
| `SearchEvent` | analysis | what people searched for on the map |
| `SystemEvent` | analysis | errors and warnings from services, shown on the admin dashboard |

The billing numbers on `User` are a **cached copy**; the billing service is the source of truth.

## 5. Contracts between the website and the services

- JSON over HTTP, routes under `/v1/`, header `X-Service-Token`, `X-Request-ID` passed along for tracing.
- Errors are `{"error": "...", "message": "..."}` with 400, 401, 404, 502 or 503.
- Timeouts (s): analysis 170, satellite 130, report 120, advisory 30, chatbot 25, risk 15, geocode 10, billing 10.
- The request and answer shapes are documented at the top of each `services/<name>/tr_<name>/app.py`.

## 6. Failure behaviour

The full degrade matrix is `ARCHITECTURE.md` section 6; every row is a test in `analysis/tests.py` or `core/tests.py`
(RTM NFR-01). In short: satellite, risk, analysis or billing down → analysis refused, **no credit used**; advisory or geocode
down → analysis works with a missing piece; report down → message on the results page; chatbot down → the bubble apologises.

## 7. Decisions worth remembering

- *Why an orchestrator?* Without it the website would have to know the order of four calls and what to do when each fails.
  Cost: one extra hop (milliseconds). Accepted to keep the website thin.
- *Why not split accounts or parcels?* Sessions, CSRF and the admin are built around the user table; parcels are the user's
  own data.
